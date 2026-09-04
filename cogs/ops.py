# ── Jarcord: op signups (RSVP) cog ──
import time
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord
from discord import app_commands
from discord.ext import commands, tasks

from db import conn, get_setting, set_setting
from ui import ACCENT, app_staff_check, embed, is_officer, log_action

REMIND_BEFORE = 10 * 60  # ponytail: fixed 10-min reminder; make it per-op if anyone asks
OP_PLANNER = "Op Planner"  # position role that may post and run ops without being Command
CLOSE_NUDGE_AFTER = 60 * 60   # an hour after start, ask the host to close it
NUDGE_WINDOW = 7 * 86400      # ponytail: older unclosed ops are history, not a to-do
MILESTONES = (1, 5, 10, 25)   # ops attended worth a line in the thread
WHEN_FORMATS = ("%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M", "%d.%m %H:%M")
DEFAULT_TZ = "UTC"  # what op times are read as until /op-setup says otherwise
# RSVP status -> (button label, embed heading)
STATUSES = {"in": ("Attending", "Attending"),
            "maybe": ("Maybe", "Maybe"),
            "out": ("Can't make it", "Not coming")}


# ── Time parsing ──
def guild_tz() -> ZoneInfo:
    """The timezone op times are typed in. Cards still render per reader."""
    try:
        return ZoneInfo(get_setting("op_timezone") or DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TZ)  # stale setting, don't take ops down over it


def parse_when(text: str, tz: ZoneInfo = None) -> int | None:
    """Unix timestamp for a wall clock time typed in the guild timezone, else None."""
    tz = tz or guild_tz()
    for fmt in WHEN_FORMATS:
        try:
            dt = datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
        if dt.year == 1900:  # DD.MM with no year, take the next one to come round
            now = datetime.now(tz)
            dt = dt.replace(year=now.year, tzinfo=tz)
            if dt < now:
                dt = dt.replace(year=now.year + 1)
        else:
            dt = dt.replace(tzinfo=tz)
        return int(dt.timestamp())
    return None


def when_feedback(ts: int | None) -> str:
    """Echo back what the typed time actually became, so a wrong timezone is obvious."""
    if ts is None:
        return " I couldn't read that as a time, so it shows as written and gets no reminder."
    return f" Starts <t:{ts}:F>."


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


def who(guild, user_id: int) -> str:
    """A name for the card. Discord only renders <@id> inside an embed when that viewer's
    client already has the user cached, so a mention here shows as raw text to somebody
    who hasn't loaded them. Plain names always read. Pings still use mentions."""
    member = guild.get_member(user_id) if guild else None
    if member is not None:
        return member.display_name
    return f"<@{user_id}>"


def create_embed(op_id: int, author: discord.Member = None, guild=None) -> discord.Embed:
    """The op card. Rebuilt from the database every time somebody replies."""
    op = get_op(op_id)
    guild = guild or (author.guild if author is not None else None)
    e = embed(title=op["title"], colour=ACCENT)
    if author is not None:
        e.set_author(name=f"Op posted by {author.display_name}", icon_url=author.display_avatar.url)
    else:
        e.set_author(name="New op posted")
    e.add_field(name="When", value=when_display(op), inline=False)
    if op["thread_id"]:
        e.add_field(name="Talk about it", value=f"<#{op['thread_id']}>", inline=False)
    if op["notes"]:
        e.add_field(name="Notes", value=op["notes"], inline=False)

    people = roster(op_id)
    for key, (_, heading) in STATUSES.items():
        ids = people.get(key, [])
        e.add_field(
            name=f"{heading} ({len(ids)})",
            value="\n".join(who(guild, u) for u in ids) if ids else "*nobody yet*",
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
        e.set_footer(text=f"Op {op_id}, closed")
    elif op["when_ts"]:
        e.set_footer(text=f"Op {op_id}. Attending get pinged 10 minutes before start.")
    else:
        e.set_footer(text=f"Op {op_id}")
    return e


class CloseView(discord.ui.View):
    """Ephemeral, one use. Pick who actually turned up, everyone else on the list missed it."""

    def __init__(self, bot, op_id: int):
        super().__init__(timeout=300)
        self.bot, self.op_id = bot, op_id
        # everyone marked Attending is pre-ticked, the host unticks the no-shows
        self.picked.default_values = [
            discord.SelectDefaultValue(id=u, type=discord.SelectDefaultValueType.user)
            for u in roster(op_id)["in"][:25]
        ]

    @discord.ui.select(cls=discord.ui.UserSelect, min_values=0, max_values=25,
                       placeholder="who actually turned up")
    async def picked(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        was_closed = (get_op(self.op_id) or {"closed": 1})["closed"]
        ids = [u.id for u in select.values]
        msg = close_op(self.op_id, interaction.user.id, is_officer(interaction.user, roles=(OP_PLANNER,)), ids)
        await interaction.response.edit_message(content=msg, view=None)
        await sync_card(self.bot, self.op_id)
        if not was_closed and get_op(self.op_id)["closed"]:
            await log_action(interaction.guild, "Op closed", interaction.user, msg)
            await post_turnout(self.bot, self.op_id, ids)


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
        await interaction.response.edit_message(
            embed=create_embed(op["id"], guild=interaction.guild), view=self)
        if status == "in":
            await add_to_thread(interaction.client, op, interaction.user)

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


async def get_thread(bot, thread_id):
    """The op thread, from cache or fetched. None if it is gone."""
    if not thread_id:
        return None
    thread = bot.get_channel(thread_id)
    if thread is None:
        try:
            thread = await bot.fetch_channel(thread_id)
        except discord.HTTPException:
            return None
    return thread


async def add_to_thread(bot, op, member) -> None:
    """Attending puts you in the op thread, so a plan or time change actually reaches you."""
    thread = await get_thread(bot, op["thread_id"])
    if thread is not None:
        try:
            await thread.add_user(member)
        except discord.HTTPException:
            pass  # archived or no permission, not worth failing the RSVP over


async def post_turnout(bot, op_id: int, attended_ids) -> None:
    """After a close: who came, milestones, a nudge to rate, then the thread archives."""
    op = get_op(op_id)
    thread = await get_thread(bot, op["thread_id"]) if op else None
    if thread is None:
        return
    ids = list(dict.fromkeys(attended_ids))
    missed = conn.execute(
        "SELECT COUNT(*) AS n FROM signups WHERE op_id = ? AND attended = 0", (op_id,)
    ).fetchone()["n"]
    lines = [f"**{op['title']}** is closed. {len(ids)} attended, {missed} no-showed."]
    if ids:
        lines.append("Turned up: " + " ".join(f"<@{u}>" for u in ids))
    for u in ids:
        came, _ = attendance(u)
        if came == 1:
            lines.append(f"🎖️ <@{u}>, first op with ROC.")
        elif came in MILESTONES:
            lines.append(f"🎖️ <@{u}> just hit op {came} with ROC.")
    if ids:
        lines.append("Rate who you played with: `/rate @name 1-5 note`")
    try:
        # names render as mentions either way, this just keeps eleven phones from buzzing
        await thread.send("\n".join(lines), allowed_mentions=discord.AllowedMentions.none())
        await thread.edit(archived=True)
    except discord.HTTPException as exc:
        print(f">> turnout post failed for op {op_id}: {exc!r}")


async def sync_card(bot, op_id: int, ref: tuple = None) -> None:
    """Redraw the posted op card, or delete it once the op is gone. `ref` carries
    (channel_id, message_id, thread_id) for an op whose row has already been removed."""
    op = get_op(op_id)
    if op:
        channel_id, message_id, thread_id = op["channel_id"], op["message_id"], None
    elif ref:
        channel_id, message_id, thread_id = (tuple(ref) + (None,))[:3]
    else:
        return
    if op is None and thread_id:  # cancelled, the thread goes with the card
        thread = await get_thread(bot, thread_id)
        if thread is not None:
            try:
                await thread.delete()
            except discord.HTTPException:
                pass
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
            await msg.edit(embed=create_embed(op_id, guild=channel.guild),
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
    line = f"Updated **{changes.get('title', op['title'])}** (ID `{op_id}`)."
    if when:
        line += when_feedback(changes["when_ts"])
    return line


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


def roster_embed(op_id: int, guild=None) -> discord.Embed:
    op = get_op(op_id)
    if op is None:
        return embed(description=f"No op with ID `{op_id}`.")
    rows = conn.execute(
        "SELECT user_id FROM signups WHERE op_id = ? AND status = 'in' ORDER BY signed_at", (op_id,)
    ).fetchall()
    e = embed(title=op["title"])
    e.add_field(name="When", value=when_display(op), inline=True)
    e.add_field(name="Signed up", value=str(len(rows)), inline=True)
    e.add_field(name="Posted by", value=who(guild, op["created_by"]), inline=True)
    roster = (
        "\n".join(f"`{i:>2}` {who(guild, r['user_id'])}" for i, r in enumerate(rows, 1))
        if rows else "*Nobody yet.*"
    )
    e.add_field(name="Roster", value=roster, inline=False)
    e.set_footer(text=f"Op {op_id}")
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
        f"`{r['id']:>3}` **{r['title']}**, {when_display(r)}, {r['n']} signed up" for r in rows
    )
    e = embed(title="Recent ops", description=lines)
    e.set_footer(text="RSVP on the op card, or use /op join <id>")
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
                "SELECT user_id, status FROM signups WHERE op_id = ? AND status IN ('in', 'maybe')",
                (op["id"],),
            ).fetchall()
            mentions = " ".join(f"<@{r['user_id']}>" for r in going if r["status"] == "in")
            maybe = " ".join(f"<@{r['user_id']}>" for r in going if r["status"] == "maybe")
            if maybe:  # the undecided are one nudge from turning up
                mentions += ("\n" if mentions else "") + f"Still on Maybe, last call: {maybe}"
            e = embed(
                title=op["title"],
                description=f"Starts <t:{op['when_ts']}:R> (<t:{op['when_ts']}:F>)",
            )
            e.set_author(name="Op reminder")
            e.set_footer(text=f"Op {op['id']}")
            try:
                await channel.send(content=mentions or None, embed=e)
                print(f">> reminder sent for op {op['id']} ({op['title']})")
            except discord.HTTPException as exc:
                print(f">> reminder failed for op {op['id']}: {exc!r}")

        # an hour after start, ask the host to close it. Once, and only for recent ops.
        stale = conn.execute(
            "SELECT * FROM ops WHERE closed = 0 AND reminded = 1 AND when_ts IS NOT NULL AND when_ts <= ?",
            (now - CLOSE_NUDGE_AFTER,),
        ).fetchall()
        for op in stale:
            conn.execute("UPDATE ops SET reminded = 2 WHERE id = ?", (op["id"],))
            conn.commit()
            if op["when_ts"] < now - NUDGE_WINDOW:
                continue
            target = await get_thread(self.bot, op["thread_id"]) or self.bot.get_channel(op["channel_id"] or 0)
            if target is None:
                continue
            try:
                await target.send(
                    f"<@{op['created_by']}> **{op['title']}** started <t:{op['when_ts']}:R>. "
                    f"Record who turned up: `/op close op_id:{op['id']}`. "
                    "Anyone marked Attending who didn't show gets a no-show.",
                    allowed_mentions=discord.AllowedMentions(users=True),
                )
                print(f">> close nudge sent for op {op['id']}")
            except discord.HTTPException as exc:
                print(f">> close nudge failed for op {op['id']}: {exc!r}")

    @reminder_loop.before_loop
    async def before_reminders(self):
        await self.bot.wait_until_ready()

    # ── Slash commands: everything lives under /op ──
    op = app_commands.Group(name="op", description="Post ops and manage who's coming")

    @op.command(name="create", description="Post an op with RSVP buttons")
    @app_commands.describe(
        what="Op name",
        when="Free text, or '29.08 21:00' / '2026-08-29 21:00', read in the server timezone",
        who="Role to ping. Defaults to whatever /op-setup configured",
        notes="Loadout, meeting point, anything else",
    )
    @app_staff_check(officer=True, manage_events=True, roles=(OP_PLANNER,))
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

        # A thread started FROM the card makes the card a starter message, and Discord
        # renders those read-only inside the thread, so the RSVP buttons go dead there.
        # ponytail: a standalone channel thread instead, linked from the card.
        thread_note = ""
        try:
            thread = await channel.create_thread(
                name=what[:100], type=discord.ChannelType.public_thread,
                auto_archive_duration=10080,
            )
            conn.execute("UPDATE ops SET thread_id = ? WHERE id = ?", (thread.id, op_id))
            conn.commit()
            await msg.edit(embed=create_embed(op_id, interaction.user), view=OpView())
            thread_note = f" Talk about it in {thread.mention}."
        except discord.HTTPException as e:
            print(f">> no thread for op {op_id}: {e}")
            thread_note = " I couldn't open a thread, check I have Create Public Threads there."

        await log_action(interaction.guild, f"Op posted: {what}", interaction.user,
                         f"Op `{op_id}` in {channel.mention}, {when}")
        await interaction.response.send_message(
            f"Op `{op_id}` posted in {channel.mention}.{when_feedback(get_op(op_id)['when_ts'])} "
            f"{msg.jump_url}{thread_note}", ephemeral=True
        )

    @app_commands.command(name="op-setup", description="Set the ops channel, the ping role and the timezone")
    @app_commands.describe(
        channel="Where op cards get posted",
        ping_role="Role pinged on every op",
        timezone="Timezone op times are typed in, e.g. Europe/Bucharest or Europe/London",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def op_setup(self, interaction: discord.Interaction,
                       channel: discord.TextChannel = None,
                       ping_role: discord.Role = None, timezone: str = None):
        lines = []
        if timezone:
            try:
                ZoneInfo(timezone)
            except (ZoneInfoNotFoundError, ValueError):
                await interaction.response.send_message(
                    f"`{timezone}` isn't a timezone I know. Use an IANA name like "
                    "`Europe/Bucharest`, `Europe/London` or `UTC`.", ephemeral=True)
                return
            set_setting("op_timezone", timezone)
            lines.append(f"Op times are now read as **{timezone}**. "
                         f"Right now that is <t:{int(time.time())}:t>.")
        if channel:
            set_setting("op_channel_id", str(channel.id))
            lines.append(f"Ops will be posted in {channel.mention}.")
        if ping_role:
            set_setting("op_ping_role_id", str(ping_role.id))
            lines.append(f"Every op pings **{ping_role.name}**.")
        if not lines:
            lines.append("Nothing changed. Pass a channel, a ping role or a timezone. "
                         "`/setup` shows what's already configured.")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @op.command(name="join", description="Sign up for an op")
    @app_commands.describe(op_id="The op ID")
    async def op_join(self, interaction: discord.Interaction, op_id: int):
        await interaction.response.send_message(join_op(op_id, interaction.user.id), ephemeral=True)
        await sync_card(self.bot, op_id)
        op = get_op(op_id)
        if op:
            await add_to_thread(self.bot, op, interaction.user)

    @op.command(name="leave", description="Take yourself off an op's roster")
    @app_commands.describe(op_id="The op ID")
    async def op_leave(self, interaction: discord.Interaction, op_id: int):
        await interaction.response.send_message(leave_op(op_id, interaction.user.id), ephemeral=True)
        await sync_card(self.bot, op_id)

    @op.command(name="edit", description="Change an op's name, time or notes")
    @app_commands.describe(
        op_id="The op ID",
        what="New name",
        when="New time, read in the server timezone. Rescheduling re-arms the 10 minute reminder",
        notes="New notes. Pass a single space to clear them",
    )
    async def op_edit(self, interaction: discord.Interaction, op_id: int, what: str = None,
                      when: str = None, notes: str = None):
        msg = edit_op(op_id, interaction.user.id, is_officer(interaction.user, roles=(OP_PLANNER,)),
                      what, when, notes.strip() if notes is not None else None)
        await interaction.response.send_message(msg, ephemeral=True)
        await sync_card(self.bot, op_id)

    @op.command(name="close", description="Record who turned up and close the op")
    @app_commands.describe(op_id="The op ID",
                           force="Skip the picker: everyone marked Attending counts as showed")
    async def op_close(self, interaction: discord.Interaction, op_id: int, force: bool = False):
        op = get_op(op_id)
        if op is None:
            await interaction.response.send_message(f"No op with ID `{op_id}`.", ephemeral=True)
            return
        if force:
            # trust the RSVPs: no no-shows, no picker, one command and it is done
            was_closed = op["closed"]
            ids = roster(op_id)["in"]
            msg = close_op(op_id, interaction.user.id, is_officer(interaction.user, roles=(OP_PLANNER,)), ids)
            await interaction.response.send_message(msg, ephemeral=True)
            await sync_card(self.bot, op_id)
            if not was_closed and get_op(op_id)["closed"]:
                await log_action(interaction.guild, "Op closed", interaction.user, msg)
                await post_turnout(self.bot, op_id, ids)
            return
        await interaction.response.send_message(
            f"**{op['title']}**: pick everyone who actually turned up. "
            "Anyone who said they were coming and isn't picked counts as a no-show.",
            view=CloseView(self.bot, op_id), ephemeral=True,
        )

    @op.command(name="cancel", description="Cancel an op (creator or an officer)")
    @app_commands.describe(op_id="The op ID")
    async def op_cancel(self, interaction: discord.Interaction, op_id: int):
        officer = is_officer(interaction.user, roles=(OP_PLANNER,))
        op = get_op(op_id)
        ref = (op["channel_id"], op["message_id"], op["thread_id"]) if op else None
        result = cancel_op(op_id, interaction.user.id, officer)
        await interaction.response.send_message(result)
        await log_action(interaction.guild, "Op cancelled", interaction.user, result)
        await sync_card(self.bot, op_id, ref)

    @op.command(name="roster", description="Who is attending an op")
    @app_commands.describe(op_id="The op ID")
    async def op_roster_slash(self, interaction: discord.Interaction, op_id: int):
        await interaction.response.send_message(
            embed=roster_embed(op_id, interaction.guild), ephemeral=True)

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
        op = get_op(op_id)
        if op:
            await add_to_thread(self.bot, op, ctx.author)

    @op_prefix.command(name="leave")
    async def op_leave_prefix(self, ctx: commands.Context, op_id: int):
        await ctx.send(leave_op(op_id, ctx.author.id))
        await sync_card(self.bot, op_id)

    @op_prefix.command(name="cancel")
    async def op_cancel_prefix(self, ctx: commands.Context, op_id: int):
        officer = is_officer(ctx.author, roles=(OP_PLANNER,))
        op = get_op(op_id)
        ref = (op["channel_id"], op["message_id"], op["thread_id"]) if op else None
        await ctx.send(cancel_op(op_id, ctx.author.id, officer))
        await sync_card(self.bot, op_id, ref)

    @op_prefix.command(name="roster")
    async def op_roster(self, ctx: commands.Context, op_id: int):
        await ctx.send(embed=roster_embed(op_id, ctx.guild))

    @op_prefix.command(name="list")
    async def op_list(self, ctx: commands.Context):
        await ctx.send(embed=list_embed())


async def setup(bot: commands.Bot):
    await bot.add_cog(Ops(bot))
