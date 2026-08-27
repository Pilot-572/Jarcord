# ── Jarcord: op signups (RSVP) cog ──
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from db import conn, get_setting, set_setting
from ui import ACCENT, app_staff_check, embed, is_officer

REMIND_BEFORE = 30 * 60  # ponytail: fixed 30-min reminder; make it per-op if anyone asks
WHEN_FORMATS = ("%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M", "%d.%m %H:%M")
# RSVP status -> (button label, embed heading)
STATUSES = {"in": ("Attending", "Attending"),
            "maybe": ("Maybe", "Maybe"),
            "out": ("Can't make it", "Not coming")}


# ── Time parsing ──
def parse_when(text: str) -> int | None:
    """Return a unix timestamp if `text` matches a known UTC format, else None."""
    for fmt in WHEN_FORMATS:
        try:
            dt = datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
        if dt.year == 1900:  # DD.MM without a year
            now = datetime.now(timezone.utc)
            dt = dt.replace(year=now.year)
            if dt.replace(tzinfo=timezone.utc) < now:
                dt = dt.replace(year=now.year + 1)
        return int(dt.replace(tzinfo=timezone.utc).timestamp())
    return None


def when_display(op) -> str:
    if op["when_ts"]:
        return f"<t:{op['when_ts']}:F> (<t:{op['when_ts']}:R>)"
    return op["when_text"]


# ── DB helpers (shared by slash + prefix) ──
def create_op(title: str, when: str, author_id: int, channel_id: int, notes: str = None) -> int:
    cur = conn.execute(
        """INSERT INTO ops (title, when_text, created_by, when_ts, channel_id, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (title, when, author_id, parse_when(when), channel_id, notes),
    )
    conn.commit()
    return cur.lastrowid


def set_status(op_id: int, user_id: int, status: str) -> None:
    conn.execute(
        """INSERT INTO signups (op_id, user_id, status) VALUES (?, ?, ?)
           ON CONFLICT(op_id, user_id) DO UPDATE SET status = ?""",
        (op_id, user_id, status, status),
    )
    conn.commit()


def roster(op_id: int) -> dict:
    """{status: [user_id, ...]} in the order people replied."""
    out = {k: [] for k in STATUSES}
    for r in conn.execute(
        "SELECT user_id, status FROM signups WHERE op_id = ? ORDER BY signed_at", (op_id,)
    ):
        out.setdefault(r["status"], []).append(r["user_id"])
    return out


def get_op(op_id: int):
    return conn.execute("SELECT * FROM ops WHERE id = ?", (op_id,)).fetchone()


def create_embed(op_id: int, author: discord.Member = None) -> discord.Embed:
    """The op card. Rebuilt from the database every time somebody replies."""
    op = get_op(op_id)
    e = embed(title=op["title"], colour=ACCENT)
    if author is not None:
        e.set_author(name=f"Op posted by {author.display_name}", icon_url=author.display_avatar.url)
    else:
        e.set_author(name="New op posted")
    e.add_field(name="When", value=when_display(op), inline=False)
    if op["notes"]:
        e.add_field(name="Notes", value=op["notes"], inline=False)

    people = roster(op_id)
    for key, (_, heading) in STATUSES.items():
        ids = people.get(key, [])
        e.add_field(
            name=f"{heading} ({len(ids)})",
            value="\n".join(f"<@{u}>" for u in ids) if ids else "*nobody yet*",
            inline=True,
        )
    if op["closed"]:
        came = conn.execute(
            "SELECT COUNT(*) AS n FROM signups WHERE op_id = ? AND attended = 1", (op_id,)
        ).fetchone()["n"]
        missed = conn.execute(
            "SELECT COUNT(*) AS n FROM signups WHERE op_id = ? AND attended = 0", (op_id,)
        ).fetchone()["n"]
        e.add_field(name="Turned out", value=f"{came} attended, {missed} no-showed", inline=False)
        e.set_footer(text=f"Op ID {op_id} · closed")
    elif op["when_ts"]:
        e.set_footer(text=f"Op ID {op_id} · attending get pinged 30 min before start")
    else:
        e.set_footer(text=f"Op ID {op_id}")
    return e


class CloseView(discord.ui.View):
    """Ephemeral, one use. Pick who actually turned up, everyone else on the list missed it."""

    def __init__(self, bot, op_id: int):
        super().__init__(timeout=300)
        self.bot, self.op_id = bot, op_id

    @discord.ui.select(cls=discord.ui.UserSelect, min_values=0, max_values=25,
                       placeholder="who actually turned up")
    async def picked(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        msg = close_op(self.op_id, interaction.user.id, is_officer(interaction.user),
                       [u.id for u in select.values])
        await interaction.response.edit_message(content=msg, view=None)
        await sync_card(self.bot, self.op_id)


class OpView(discord.ui.View):
    """Persistent RSVP buttons. The op is found by the message they sit on."""

    def __init__(self):
        super().__init__(timeout=None)

    async def _reply(self, interaction: discord.Interaction, status: str):
        op = conn.execute(
            "SELECT * FROM ops WHERE message_id = ?", (interaction.message.id,)
        ).fetchone()
        if op is None:
            await interaction.response.send_message("This op is gone.", ephemeral=True)
            return
        set_status(op["id"], interaction.user.id, status)
        await interaction.response.edit_message(embed=create_embed(op["id"]), view=self)

    @discord.ui.button(label="Attending", style=discord.ButtonStyle.success,
                       custom_id="jarcord:op:in")
    async def rsvp_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._reply(interaction, "in")

    @discord.ui.button(label="Maybe", style=discord.ButtonStyle.secondary,
                       custom_id="jarcord:op:maybe")
    async def rsvp_maybe(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._reply(interaction, "maybe")

    @discord.ui.button(label="Can't make it", style=discord.ButtonStyle.danger,
                       custom_id="jarcord:op:out")
    async def rsvp_out(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._reply(interaction, "out")


async def sync_card(bot, op_id: int, ref: tuple = None) -> None:
    """Redraw the posted op card, or delete it once the op is gone. `ref` carries
    (channel_id, message_id) for an op whose row has already been removed."""
    op = get_op(op_id)
    channel_id, message_id = (op["channel_id"], op["message_id"]) if op else (ref or (None, None))
    if not channel_id or not message_id:
        return
    channel = bot.get_channel(channel_id)
    if channel is None:
        return
    try:
        msg = await channel.fetch_message(message_id)
        if op is None:
            await msg.delete()
        else:
            await msg.edit(embed=create_embed(op_id),
                           view=None if op["closed"] else OpView())
    except discord.HTTPException:
        pass  # card deleted by hand, nothing to keep in sync


def join_op(op_id: int, user_id: int) -> str:
    op = get_op(op_id)
    if op is None:
        return f"No op with ID `{op_id}`."
    already = conn.execute(
        "SELECT status FROM signups WHERE op_id = ? AND user_id = ?", (op_id, user_id)
    ).fetchone()
    if already and already["status"] == "in":
        return f"You're already on the roster for **{op['title']}**."
    set_status(op_id, user_id, "in")
    return f"You're on the roster for **{op['title']}**, {when_display(op)}."


def leave_op(op_id: int, user_id: int) -> str:
    op = get_op(op_id)
    if op is None:
        return f"No op with ID `{op_id}`."
    cur = conn.execute("DELETE FROM signups WHERE op_id = ? AND user_id = ?", (op_id, user_id))
    conn.commit()
    if cur.rowcount == 0:
        return f"You weren't on the roster for **{op['title']}**."
    return f"Removed you from **{op['title']}**."


def edit_op(op_id: int, user_id: int, is_officer: bool, what: str = None,
            when: str = None, notes: str = None) -> str:
    op = get_op(op_id)
    if op is None:
        return f"No op with ID `{op_id}`."
    if user_id != op["created_by"] and not is_officer:
        return "Only the op creator (or an officer) can edit it."

    changes = {}
    if what:
        changes["title"] = what
    if notes is not None:
        changes["notes"] = notes or None      # empty string clears them
    if when:
        changes["when_text"] = when
        changes["when_ts"] = parse_when(when)
        # ponytail: moving an op re-arms the reminder, otherwise a rescheduled op stays silent
        changes["reminded"] = 0
    if not changes:
        return "Nothing to change. Pass at least one of what, when or notes."

    sets = ", ".join(f"{c} = ?" for c in changes)   # column names are code literals
    conn.execute(f"UPDATE ops SET {sets} WHERE id = ?", [*changes.values(), op_id])
    conn.commit()
    return f"Updated **{changes.get('title', op['title'])}** (ID `{op_id}`)."


def close_op(op_id: int, user_id: int, is_officer: bool, attended_ids) -> str:
    """Record who actually turned up. Anyone who said they were coming and isn't in the
    list is a no-show. Anyone in the list who never replied still counts as attending."""
    op = get_op(op_id)
    if op is None:
        return f"No op with ID `{op_id}`."
    if user_id != op["created_by"] and not is_officer:
        return "Only the op creator (or an officer) can close it."
    if op["closed"]:
        return f"**{op['title']}** is already closed."

    conn.execute("UPDATE signups SET attended = 0 WHERE op_id = ? AND status = 'in'", (op_id,))
    for uid in attended_ids:
        conn.execute(
            """INSERT INTO signups (op_id, user_id, status, attended) VALUES (?, ?, 'in', 1)
               ON CONFLICT(op_id, user_id) DO UPDATE SET status = 'in', attended = 1""",
            (op_id, uid),
        )
    conn.execute("UPDATE ops SET closed = 1 WHERE id = ?", (op_id,))
    conn.commit()
    missed = conn.execute(
        "SELECT COUNT(*) AS n FROM signups WHERE op_id = ? AND attended = 0", (op_id,)
    ).fetchone()["n"]
    return f"Closed **{op['title']}**. {len(set(attended_ids))} attended, {missed} no-showed."


def attendance(user_id: int) -> tuple[int, int]:
    """(ops attended, ops missed after saying they were coming)."""
    row = conn.execute(
        """SELECT SUM(attended = 1) AS came, SUM(attended = 0) AS missed
           FROM signups WHERE user_id = ?""",
        (user_id,),
    ).fetchone()
    return (row["came"] or 0, row["missed"] or 0)


def cancel_op(op_id: int, user_id: int, is_officer: bool) -> str:
    op = get_op(op_id)
    if op is None:
        return f"No op with ID `{op_id}`."
    if user_id != op["created_by"] and not is_officer:
        return "Only the op creator (or someone with Manage Server) can cancel it."
    conn.execute("DELETE FROM signups WHERE op_id = ?", (op_id,))
    conn.execute("DELETE FROM ops WHERE id = ?", (op_id,))
    conn.commit()
    return f"Cancelled **{op['title']}** (ID `{op_id}`)."


def roster_embed(op_id: int) -> discord.Embed:
    op = get_op(op_id)
    if op is None:
        return embed(description=f"No op with ID `{op_id}`.")
    rows = conn.execute(
        "SELECT user_id FROM signups WHERE op_id = ? AND status = 'in' ORDER BY signed_at", (op_id,)
    ).fetchall()
    e = embed(title=op["title"])
    e.add_field(name="When", value=when_display(op), inline=True)
    e.add_field(name="Signed up", value=str(len(rows)), inline=True)
    e.add_field(name="Posted by", value=f"<@{op['created_by']}>", inline=True)
    roster = (
        "\n".join(f"`{i:>2}` <@{r['user_id']}>" for i, r in enumerate(rows, 1))
        if rows else "*Nobody yet. Be the first.*"
    )
    e.add_field(name="Roster", value=roster, inline=False)
    e.set_footer(text=f"Op ID {op_id}")
    return e


def list_embed() -> discord.Embed:
    rows = conn.execute(
        """SELECT o.*, COUNT(s.user_id) AS n
           FROM ops o LEFT JOIN signups s ON s.op_id = o.id AND s.status = 'in'
           GROUP BY o.id ORDER BY o.id DESC LIMIT 10"""
    ).fetchall()
    if not rows:
        return embed(title="Recent ops", description="No ops posted yet.")
    lines = "\n".join(
        f"`{r['id']:>3}` **{r['title']}**, {when_display(r)} · {r['n']} signed up" for r in rows
    )
    e = embed(title="Recent ops", description=lines)
    e.set_footer(text="RSVP on the op card, or use /op-join <id>")
    return e


class Ops(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(OpView())  # RSVP buttons survive restarts
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    # ── Reminders ──
    @tasks.loop(minutes=1)
    async def reminder_loop(self):
        now = int(time.time())
        due = conn.execute(
            "SELECT * FROM ops WHERE reminded = 0 AND when_ts IS NOT NULL AND when_ts <= ?",
            (now + REMIND_BEFORE,),
        ).fetchall()
        for op in due:
            conn.execute("UPDATE ops SET reminded = 1 WHERE id = ?", (op["id"],))
            conn.commit()
            if op["when_ts"] < now or not op["channel_id"]:
                continue  # already started (bot was down) or nowhere to post
            channel = self.bot.get_channel(op["channel_id"])
            if channel is None:
                continue
            going = conn.execute(
                "SELECT user_id FROM signups WHERE op_id = ? AND status = 'in'", (op["id"],)
            ).fetchall()
            mentions = " ".join(f"<@{r['user_id']}>" for r in going)
            e = embed(
                title=op["title"],
                description=f"Starts <t:{op['when_ts']}:R> (<t:{op['when_ts']}:F>)",
            )
            e.set_author(name="Op reminder")
            e.set_footer(text=f"Op ID {op['id']}")
            try:
                await channel.send(content=mentions or None, embed=e)
                print(f">> reminder sent for op {op['id']} ({op['title']})")
            except discord.HTTPException as exc:
                print(f">> reminder failed for op {op['id']}: {exc!r}")

    @reminder_loop.before_loop
    async def before_reminders(self):
        await self.bot.wait_until_ready()

    # ── Slash commands: everything lives under /op ──
    op = app_commands.Group(name="op", description="Post ops and manage who's coming")

    @op.command(name="create", description="Post an op with RSVP buttons")
    @app_commands.describe(
        what="Op name",
        when="Free text, or '29.08 21:00' / '2026-08-29 21:00' for a real time and a reminder",
        who="Role to ping. Defaults to whatever /op-setup configured",
        notes="Loadout, meeting point, anything else",
    )
    @app_staff_check(officer=True, manage_events=True)
    async def op_create(self, interaction: discord.Interaction, what: str, when: str,
                        who: discord.Role = None, notes: str = None):
        channel = interaction.channel
        configured = get_setting("op_channel_id")
        if configured:
            channel = interaction.guild.get_channel(int(configured)) or interaction.channel

        ping = who
        if ping is None:
            role_id = get_setting("op_ping_role_id")
            if role_id:
                ping = interaction.guild.get_role(int(role_id))

        op_id = create_op(what, when, interaction.user.id, channel.id, notes)
        try:
            msg = await channel.send(
                content=ping.mention if ping else None,
                embed=create_embed(op_id, interaction.user),
                view=OpView(),
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
        except discord.Forbidden:
            cancel_op(op_id, interaction.user.id, True)
            await interaction.response.send_message(
                f"I can't post in {channel.mention}. Give me Send Messages there.", ephemeral=True
            )
            return
        conn.execute("UPDATE ops SET message_id = ? WHERE id = ?", (msg.id, op_id))
        conn.commit()
        await interaction.response.send_message(
            f"Op `{op_id}` posted in {channel.mention}. {msg.jump_url}", ephemeral=True
        )

    @app_commands.command(name="op-setup", description="Set the ops channel and the role to ping")
    @app_commands.describe(channel="Where op cards get posted", ping_role="Role pinged on every op")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def op_setup(self, interaction: discord.Interaction, channel: discord.TextChannel,
                       ping_role: discord.Role = None):
        set_setting("op_channel_id", str(channel.id))
        msg = f"Ops will be posted in {channel.mention}."
        if ping_role:
            set_setting("op_ping_role_id", str(ping_role.id))
            msg += f" Every op pings **{ping_role.name}**."
        await interaction.response.send_message(msg, ephemeral=True)

    @op.command(name="join", description="Sign up for an op")
    @app_commands.describe(op_id="The op ID")
    async def op_join(self, interaction: discord.Interaction, op_id: int):
        await interaction.response.send_message(join_op(op_id, interaction.user.id), ephemeral=True)
        await sync_card(self.bot, op_id)

    @op.command(name="leave", description="Take yourself off an op's roster")
    @app_commands.describe(op_id="The op ID")
    async def op_leave(self, interaction: discord.Interaction, op_id: int):
        await interaction.response.send_message(leave_op(op_id, interaction.user.id), ephemeral=True)
        await sync_card(self.bot, op_id)

    @op.command(name="edit", description="Change an op's name, time or notes")
    @app_commands.describe(
        op_id="The op ID",
        what="New name",
        when="New time. Rescheduling re-arms the 30 minute reminder",
        notes="New notes. Pass a single space to clear them",
    )
    async def op_edit(self, interaction: discord.Interaction, op_id: int, what: str = None,
                      when: str = None, notes: str = None):
        msg = edit_op(op_id, interaction.user.id, is_officer(interaction.user),
                      what, when, notes.strip() if notes is not None else None)
        await interaction.response.send_message(msg, ephemeral=True)
        await sync_card(self.bot, op_id)

    @op.command(name="close", description="Record who turned up and close the op")
    @app_commands.describe(op_id="The op ID")
    async def op_close(self, interaction: discord.Interaction, op_id: int):
        op = get_op(op_id)
        if op is None:
            await interaction.response.send_message(f"No op with ID `{op_id}`.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"**{op['title']}**: pick everyone who actually turned up. "
            "Anyone who said they were coming and isn't picked counts as a no-show.",
            view=CloseView(self.bot, op_id), ephemeral=True,
        )

    @op.command(name="cancel", description="Cancel an op (creator or an officer)")
    @app_commands.describe(op_id="The op ID")
    async def op_cancel(self, interaction: discord.Interaction, op_id: int):
        officer = is_officer(interaction.user)
        op = get_op(op_id)
        ref = (op["channel_id"], op["message_id"]) if op else None
        await interaction.response.send_message(cancel_op(op_id, interaction.user.id, officer))
        await sync_card(self.bot, op_id, ref)

    @op.command(name="roster", description="Who is attending an op")
    @app_commands.describe(op_id="The op ID")
    async def op_roster_slash(self, interaction: discord.Interaction, op_id: int):
        await interaction.response.send_message(embed=roster_embed(op_id), ephemeral=True)

    @op.command(name="list", description="The last 10 ops and their IDs")
    async def op_list_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=list_embed(), ephemeral=True)

    # ── Prefix commands: !op join / leave / cancel / roster / list ──
    @commands.group(name="op", invoke_without_command=True)
    async def op_prefix(self, ctx: commands.Context):
        await ctx.send("Usage: `op join <id>` | `op leave <id>` | `op cancel <id>` | `op roster <id>` | `op list`")

    @op_prefix.command(name="join")
    async def op_join_prefix(self, ctx: commands.Context, op_id: int):
        await ctx.send(join_op(op_id, ctx.author.id))
        await sync_card(self.bot, op_id)

    @op_prefix.command(name="leave")
    async def op_leave_prefix(self, ctx: commands.Context, op_id: int):
        await ctx.send(leave_op(op_id, ctx.author.id))
        await sync_card(self.bot, op_id)

    @op_prefix.command(name="cancel")
    async def op_cancel_prefix(self, ctx: commands.Context, op_id: int):
        officer = is_officer(ctx.author)
        op = get_op(op_id)
        ref = (op["channel_id"], op["message_id"]) if op else None
        await ctx.send(cancel_op(op_id, ctx.author.id, officer))
        await sync_card(self.bot, op_id, ref)

    @op_prefix.command(name="roster")
    async def op_roster(self, ctx: commands.Context, op_id: int):
        await ctx.send(embed=roster_embed(op_id))

    @op_prefix.command(name="list")
    async def op_list(self, ctx: commands.Context):
        await ctx.send(embed=list_embed())


async def setup(bot: commands.Bot):
    await bot.add_cog(Ops(bot))
