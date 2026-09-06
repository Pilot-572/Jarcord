# ── Jarcord: activity tracking cog ──
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from cogs.ops import attendance
from db import conn
from ui import ACTIVITY, ago, clerk, embed, is_me

SQLITE_FMT = "%Y-%m-%d %H:%M:%S"  # matches sqlite datetime('now'), which is UTC
FLUSH_EVERY = 30                  # seconds. ponytail: a crash loses at most this much counting

# user_id -> [messages since the last flush, last seen]. Counting here means a busy evening
# is one write every half minute rather than an INSERT and a commit per message on the loop.
pending: dict[int, list] = {}


# ── Counting ──
def note_message(user_id: int, when: datetime) -> None:
    entry = pending.setdefault(user_id, [0, None])
    entry[0] += 1
    entry[1] = when.strftime(SQLITE_FMT)


def flush() -> int:
    """Write everything counted since the last flush, one transaction. Returns rows written."""
    if not pending:
        return 0
    rows = [(uid, n, seen) for uid, (n, seen) in pending.items()]
    pending.clear()
    conn.executemany(
        """INSERT INTO activity (user_id, message_count, last_seen) VALUES (?, ?, ?)
           ON CONFLICT(user_id) DO UPDATE SET
               message_count = message_count + excluded.message_count,
               last_seen = excluded.last_seen""",
        rows,
    )
    conn.commit()
    return len(rows)


class Activity(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.flush_loop.start()

    async def cog_unload(self):
        self.flush_loop.cancel()
        flush()

    @tasks.loop(seconds=FLUSH_EVERY)
    async def flush_loop(self):
        flush()

    # ── Passive logging ──
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        note_message(message.author.id, message.created_at)

    # ── Commands ──
    @commands.hybrid_command(name="activity", description="Message count, ops attended, last seen")
    async def activity(self, ctx: commands.Context, member: discord.Member):
        if is_me(member):
            await ctx.send(clerk("activity"))
            return
        flush()  # so a message sent a second ago already counts
        row = conn.execute(
            "SELECT message_count, last_seen FROM activity WHERE user_id = ?", (member.id,)
        ).fetchone()
        came, _ = attendance(member.id)  # attended, not every RSVP ever pressed
        e = embed(title=member.display_name, colour=ACTIVITY)
        e.set_thumbnail(url=member.display_avatar.url)
        e.add_field(name="Messages", value=str(row["message_count"]) if row else "0", inline=True)
        e.add_field(name="Ops attended", value=str(came), inline=True)
        e.add_field(
            name="Last seen",
            value=ago(row["last_seen"]) if row else "Never",
            inline=True,
        )
        await ctx.send(embed=e)

    @commands.hybrid_command(name="inactive", description="List members inactive for N+ days")
    async def inactive(self, ctx: commands.Context, days: int = 14):
        flush()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(SQLITE_FMT)
        seen = {
            r["user_id"]: r["last_seen"]
            for r in conn.execute("SELECT user_id, last_seen FROM activity").fetchall()
        }
        stale = [
            m for m in ctx.guild.members
            if not m.bot and seen.get(m.id, "") < cutoff
        ]
        if not stale:
            await ctx.send(embed=embed(
                title="Inactivity report", description=f"Nobody inactive for {days}+ days.",
                colour=ACTIVITY,
            ))
            return
        lines = [
            f"<@{m.id}>, last seen {ago(seen[m.id])}" if m.id in seen
            else f"<@{m.id}>, never seen"
            for m in stale[:30]
        ]
        extra = f"\n*…and {len(stale) - 30} more.*" if len(stale) > 30 else ""
        e = embed(
            title="Inactivity report",
            description="\n".join(lines) + extra,
            colour=ACTIVITY,
        )
        e.set_footer(text=f"{len(stale)} member(s) inactive {days}+ days")
        await ctx.send(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Activity(bot))
