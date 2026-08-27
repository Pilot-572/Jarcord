# ── Jarcord: member rating/feedback cog ──
import discord
from discord.ext import commands

from db import conn
from ui import RATING, embed

STARS_FULL = "★"   # ★
STARS_EMPTY = "☆"  # ☆


def stars(score: float) -> str:
    n = round(score)
    return STARS_FULL * n + STARS_EMPTY * (5 - n)


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
        msg = f"{stars(score)} Rated **{member.display_name}** {score}/5."
        if note:
            msg += f"\n> {note}"
        await ctx.send(msg)

    @commands.hybrid_command(name="rating-history", description="Average score + recent notes for a member")
    async def rating_history(self, ctx: commands.Context, member: discord.Member):
        summary = conn.execute(
            "SELECT AVG(score) AS avg, COUNT(*) AS n FROM ratings WHERE user_id = ?",
            (member.id,),
        ).fetchone()
        if summary["n"] == 0:
            await ctx.send(embed=embed(
                description=f"No ratings for **{member.display_name}** yet.", colour=RATING,
            ))
            return
        recent = conn.execute(
            """SELECT score, note, rater_id, rated_at FROM ratings
               WHERE user_id = ? ORDER BY id DESC LIMIT 5""",
            (member.id,),
        ).fetchall()
        e = embed(
            title=member.display_name,
            description=f"{stars(summary['avg'])} **{summary['avg']:.2f} / 5** · {summary['n']} rating(s)",
            colour=RATING,
        )
        e.set_thumbnail(url=member.display_avatar.url)
        lines = []
        for r in recent:
            line = f"**{r['score']}/5** by <@{r['rater_id']}> · {r['rated_at']} UTC"
            if r["note"]:
                line += f"\n> {r['note']}"
            lines.append(line)
        e.add_field(name="Recent", value="\n".join(lines), inline=False)
        await ctx.send(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Rating(bot))
