# ── Jarcord — op signups (RSVP) cog ──
import sqlite3
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from db import conn
from ui import embed

REMIND_BEFORE = 30 * 60  # ponytail: fixed 30-min reminder; make it per-op if anyone asks
WHEN_FORMATS = ("%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M", "%d.%m %H:%M")


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
def create_op(title: str, when: str, author_id: int, channel_id: int) -> int:
    cur = conn.execute(
        "INSERT INTO ops (title, when_text, created_by, when_ts, channel_id) VALUES (?, ?, ?, ?, ?)",
        (title, when, author_id, parse_when(when), channel_id),
    )
    conn.commit()
    return cur.lastrowid


def get_op(op_id: int):
    return conn.execute("SELECT * FROM ops WHERE id = ?", (op_id,)).fetchone()


def create_embed(op_id: int, author: discord.Member = None) -> discord.Embed:
    op = get_op(op_id)
    e = embed(title=op["title"])
    if author is not None:
        e.set_author(name=f"Op posted by {author.display_name}", icon_url=author.display_avatar.url)
    else:
        e.set_author(name="New op posted")
    e.add_field(name="When", value=when_display(op), inline=True)
    e.add_field(name="Join", value=f"`/op-join {op_id}`", inline=True)
    if op["when_ts"]:
        e.add_field(name="Reminder", value="Roster gets pinged 30 min before start.", inline=False)
    e.set_footer(text=f"Op ID {op_id}")
    return e


def join_op(op_id: int, user_id: int) -> str:
    op = get_op(op_id)
    if op is None:
        return f"No op with ID `{op_id}`."
    try:
        conn.execute("INSERT INTO signups (op_id, user_id) VALUES (?, ?)", (op_id, user_id))
        conn.commit()
    except sqlite3.IntegrityError:
        return f"You're already on the roster for **{op['title']}**."
    return f"You're on the roster for **{op['title']}** — {when_display(op)}."


def leave_op(op_id: int, user_id: int) -> str:
    op = get_op(op_id)
    if op is None:
        return f"No op with ID `{op_id}`."
    cur = conn.execute("DELETE FROM signups WHERE op_id = ? AND user_id = ?", (op_id, user_id))
    conn.commit()
    if cur.rowcount == 0:
        return f"You weren't on the roster for **{op['title']}**."
    return f"Removed you from **{op['title']}**."


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
        "SELECT user_id FROM signups WHERE op_id = ? ORDER BY signed_at", (op_id,)
    ).fetchall()
    e = embed(title=op["title"])
    e.add_field(name="When", value=when_display(op), inline=True)
    e.add_field(name="Signed up", value=str(len(rows)), inline=True)
    e.add_field(name="Posted by", value=f"<@{op['created_by']}>", inline=True)
    roster = (
        "\n".join(f"`{i:>2}` <@{r['user_id']}>" for i, r in enumerate(rows, 1))
        if rows else "*Nobody yet — be the first.*"
    )
    e.add_field(name="Roster", value=roster, inline=False)
    e.set_footer(text=f"Op ID {op_id} · /op-join {op_id}")
    return e


def list_embed() -> discord.Embed:
    rows = conn.execute(
        """SELECT o.*, COUNT(s.user_id) AS n
           FROM ops o LEFT JOIN signups s ON s.op_id = o.id
           GROUP BY o.id ORDER BY o.id DESC LIMIT 10"""
    ).fetchall()
    if not rows:
        return embed(title="Recent ops", description="No ops posted yet.")
    lines = "\n".join(
        f"`{r['id']:>3}` **{r['title']}** — {when_display(r)} · {r['n']} signed up" for r in rows
    )
    e = embed(title="Recent ops", description=lines)
    e.set_footer(text="Join with /op-join <id>")
    return e


class Ops(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
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
            roster = conn.execute(
                "SELECT user_id FROM signups WHERE op_id = ?", (op["id"],)
            ).fetchall()
            mentions = " ".join(f"<@{r['user_id']}>" for r in roster)
            e = embed(
                title=op["title"],
                description=f"Starts <t:{op['when_ts']}:R> — <t:{op['when_ts']}:F>",
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

    # ── Slash commands ──
    @app_commands.command(name="op-create", description="Post a new op and get its ID")
    @app_commands.describe(
        title="Op name",
        when="Free text, or 'YYYY-MM-DD HH:MM' / 'DD.MM HH:MM' in UTC to enable the 30-min reminder",
    )
    async def op_create(self, interaction: discord.Interaction, title: str, when: str):
        op_id = create_op(title, when, interaction.user.id, interaction.channel_id)
        await interaction.response.send_message(embed=create_embed(op_id, interaction.user))

    @app_commands.command(name="op-join", description="Sign up for an op")
    @app_commands.describe(op_id="The op ID")
    async def op_join(self, interaction: discord.Interaction, op_id: int):
        await interaction.response.send_message(join_op(op_id, interaction.user.id))

    @app_commands.command(name="op-leave", description="Take yourself off an op's roster")
    @app_commands.describe(op_id="The op ID")
    async def op_leave(self, interaction: discord.Interaction, op_id: int):
        await interaction.response.send_message(leave_op(op_id, interaction.user.id))

    @app_commands.command(name="op-cancel", description="Cancel an op (creator or Manage Server only)")
    @app_commands.describe(op_id="The op ID")
    async def op_cancel(self, interaction: discord.Interaction, op_id: int):
        officer = interaction.user.guild_permissions.manage_guild
        await interaction.response.send_message(cancel_op(op_id, interaction.user.id, officer))

    # ── Prefix commands: !op join / leave / cancel / roster / list ──
    @commands.group(name="op", invoke_without_command=True)
    async def op(self, ctx: commands.Context):
        await ctx.send("Usage: `op join <id>` | `op leave <id>` | `op cancel <id>` | `op roster <id>` | `op list`")

    @op.command(name="join")
    async def op_join_prefix(self, ctx: commands.Context, op_id: int):
        await ctx.send(join_op(op_id, ctx.author.id))

    @op.command(name="leave")
    async def op_leave_prefix(self, ctx: commands.Context, op_id: int):
        await ctx.send(leave_op(op_id, ctx.author.id))

    @op.command(name="cancel")
    async def op_cancel_prefix(self, ctx: commands.Context, op_id: int):
        officer = ctx.author.guild_permissions.manage_guild
        await ctx.send(cancel_op(op_id, ctx.author.id, officer))

    @op.command(name="roster")
    async def op_roster(self, ctx: commands.Context, op_id: int):
        await ctx.send(embed=roster_embed(op_id))

    @op.command(name="list")
    async def op_list(self, ctx: commands.Context):
        await ctx.send(embed=list_embed())


async def setup(bot: commands.Bot):
    await bot.add_cog(Ops(bot))
