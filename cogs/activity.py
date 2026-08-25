# ── Jarcord — activity tracking cog ──
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from db import conn

SQLITE_FMT = "%Y-%m-%d %H:%M:%S"  # matches sqlite datetime('now'), which is UTC


class Activity(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Passive logging ──
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        conn.execute(
            """INSERT INTO activity (user_id, message_count, last_seen)
               VALUES (?, 1, datetime('now'))
               ON CONFLICT(user_id) DO UPDATE SET
                   message_count = message_count + 1,
                   last_seen = datetime('now')""",
            (message.author.id,),
        )
        conn.commit()

    # ── Commands ──
    @commands.hybrid_command(name="activity", description="Message count, ops attended, last seen")
    async def activity(self, ctx: commands.Context, member: discord.Member):
        row = conn.execute(
            "SELECT message_count, last_seen FROM activity WHERE user_id = ?", (member.id,)
        ).fetchone()
        ops = conn.execute(
            "SELECT COUNT(*) AS n FROM signups WHERE user_id = ?", (member.id,)
        ).fetchone()["n"]
        if row is None:
            await ctx.send(f"**{member.display_name}** — no messages logged yet, {ops} op(s) attended.")
            return
        await ctx.send(
            f"**{member.display_name}** — {row['message_count']} messages, "
            f"{ops} op(s) attended, last seen `{row['last_seen']}` UTC."
        )

    @commands.hybrid_command(name="inactive", description="List members inactive for N+ days")
    async def inactive(self, ctx: commands.Context, days: int = 14):
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
            await ctx.send(f"Nobody inactive for {days}+ days.")
            return
        lines = [
            f"{m.display_name} — last seen `{seen[m.id]}`" if m.id in seen
            else f"{m.display_name} — never seen"
            for m in stale[:30]
        ]
        extra = f"\n…and {len(stale) - 30} more." if len(stale) > 30 else ""
        await ctx.send(f"**Inactive {days}+ days ({len(stale)}):**\n" + "\n".join(lines) + extra)


async def setup(bot: commands.Bot):
    await bot.add_cog(Activity(bot))
