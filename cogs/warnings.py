# ── Jarcord: warnings log ──
import discord
from discord.ext import commands

from db import conn, get_setting
from ui import ACCENT, ago, embed, staff_check

WARNED = discord.Colour(0xF59E0B)


def add_warning(user_id: int, officer_id: int, reason: str) -> int:
    cur = conn.execute(
        "INSERT INTO warnings (user_id, officer_id, reason) VALUES (?, ?, ?)",
        (user_id, officer_id, reason),
    )
    conn.commit()
    return cur.lastrowid


def warnings_for(user_id: int):
    return conn.execute(
        "SELECT * FROM warnings WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall()


def drop_warning(warning_id: int) -> bool:
    cur = conn.execute("DELETE FROM warnings WHERE id = ?", (warning_id,))
    conn.commit()
    return cur.rowcount > 0


def warning_embed(member: discord.Member, rows, latest=None) -> discord.Embed:
    e = embed(
        title=f"{member.display_name}: {len(rows)} warning{'s' if len(rows) != 1 else ''}",
        colour=WARNED if rows else ACCENT,
    )
    e.set_thumbnail(url=member.display_avatar.url)
    for r in rows[-10:]:  # ponytail: last ten is plenty, the rest stay in the database
        e.add_field(
            name=f"#{r['id']}",
            value=f"{r['reason']}\nby <@{r['officer_id']}> {ago(r['created_at'])}",
            inline=False,
        )
    if not rows:
        e.description = "Clean record."
    elif latest is not None:
        e.set_footer(text=f"Warning #{latest} just added")
    return e


class Warnings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx) -> bool:
        return ctx.guild is not None

    @commands.hybrid_command(name="warn", description="Warn a member and log it")
    @discord.app_commands.default_permissions(moderate_members=True)
    @staff_check(officer=True, moderate_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str):
        if member.bot:
            await ctx.send("Bots don't take warnings.")
            return
        warning_id = add_warning(member.id, ctx.author.id, reason)
        rows = warnings_for(member.id)

        notes = []
        try:
            await member.send(
                f"You've been warned in **{ctx.guild.name}**: {reason}\n"
                f"That's warning {len(rows)}. Take it up with Command in DMs if you disagree."
            )
        except discord.HTTPException:
            notes.append("their DMs are closed, so tell them yourself")

        channel_id = get_setting("records_channel_id")
        if channel_id:
            channel = ctx.guild.get_channel(int(channel_id))
            if channel is not None:
                try:
                    await channel.send(embed=warning_embed(member, rows, warning_id))
                except discord.Forbidden:
                    notes.append(f"couldn't file it in #{channel.name}")

        print(f">> warned {member.id} (#{warning_id}) by {ctx.author.id}: {reason}")
        msg = f"Warned {member.mention}. That's **{len(rows)}** on record (`#{warning_id}`)."
        if notes:
            msg += " Note: " + "; ".join(notes) + "."
        await ctx.send(msg, ephemeral=True)

    @commands.hybrid_command(name="warns", description="A member's warning history")
    @discord.app_commands.default_permissions(moderate_members=True)
    @staff_check(officer=True, moderate_members=True)
    async def warns(self, ctx: commands.Context, member: discord.Member):
        await ctx.send(embed=warning_embed(member, warnings_for(member.id)), ephemeral=True)

    @commands.hybrid_command(name="unwarn", description="Delete a warning by its number")
    @discord.app_commands.default_permissions(moderate_members=True)
    @staff_check(officer=True, moderate_members=True)
    async def unwarn(self, ctx: commands.Context, warning_id: int):
        if drop_warning(warning_id):
            print(f">> warning #{warning_id} deleted by {ctx.author.id}")
            await ctx.send(f"Warning `#{warning_id}` deleted.", ephemeral=True)
        else:
            await ctx.send(f"No warning with ID `{warning_id}`.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Warnings(bot))
