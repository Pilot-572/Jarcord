# ── Jarcord — server role utilities ──
import discord
from discord.ext import commands

DIVIDER = "─" * 32  # ponytail: fixed width — Discord truncates the role list anyway


class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx) -> bool:
        return ctx.guild is not None

    @commands.hybrid_command(name="dividers", description="Create blank divider roles for the role list")
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def dividers(self, ctx: commands.Context, count: commands.Range[int, 1, 25] = 10):
        await ctx.defer()
        made = 0
        for _ in range(count):
            try:
                await ctx.guild.create_role(
                    name=DIVIDER,
                    permissions=discord.Permissions.none(),
                    reason=f"divider role requested by {ctx.author}",
                )
            except discord.HTTPException as exc:
                print(f">> divider creation stopped at {made} in guild {ctx.guild.id}: {exc}")
                await ctx.send(f"Stopped after **{made}** — Discord refused the next one: {exc.text or exc}")
                return
            made += 1
        print(f">> created {made} divider roles in guild {ctx.guild.id}")
        await ctx.send(
            f"Created **{made}** divider roles at the bottom of the list — "
            "drag them between your groups in Server Settings → Roles."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Roles(bot))
