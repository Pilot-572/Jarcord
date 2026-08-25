# ── Jarcord — member rating/feedback cog ──
import discord
from discord.ext import commands

from db import conn


class Rating(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # hybrid = both /rate and !rate from one definition
    @commands.hybrid_command(name="rate", description="Rate a member's op performance 1-5")
    async def rate(
        self,
        ctx: commands.Context,
        member: discord.Member,
        score: commands.Range[int, 1, 5],
        *,
        note: str = None,
    ):
        if member.bot:
            await ctx.send("Bots don't take feedback.")
            return
        conn.execute(
            "INSERT INTO ratings (user_id, rater_id, score, note) VALUES (?, ?, ?, ?)",
            (member.id, ctx.author.id, score, note),
        )
        conn.commit()
        msg = f"Rated {member.display_name} **{score}/5**."
        if note:
            msg += f" Note: {note}"
        await ctx.send(msg)

    @commands.hybrid_command(name="rating-history", description="Average score + recent notes for a member")
    async def rating_history(self, ctx: commands.Context, member: discord.Member):
        summary = conn.execute(
            "SELECT AVG(score) AS avg, COUNT(*) AS n FROM ratings WHERE user_id = ?",
            (member.id,),
        ).fetchone()
        if summary["n"] == 0:
            await ctx.send(f"No ratings for {member.display_name} yet.")
            return
        recent = conn.execute(
            """SELECT score, note, rater_id, rated_at FROM ratings
               WHERE user_id = ? ORDER BY id DESC LIMIT 5""",
            (member.id,),
        ).fetchall()
        lines = [f"**{member.display_name}** — avg **{summary['avg']:.2f}/5** over {summary['n']} rating(s)"]
        for r in recent:
            line = f"`{r['rated_at']}` {r['score']}/5 by <@{r['rater_id']}>"
            if r["note"]:
                line += f" — {r['note']}"
            lines.append(line)
        await ctx.send("\n".join(lines))


async def setup(bot: commands.Bot):
    await bot.add_cog(Rating(bot))
