# ── Jarcord: server setup and role utilities ──
import discord
from discord.ext import commands

from db import get_setting, set_setting
from ui import ACCENT, embed, staff_check

DIVIDER = "─" * 32  # ponytail: fixed width, Discord truncates the role list anyway

# (label, settings key, what it points at, the command that sets it)
SETTINGS = (
    ("Welcome channel",      "welcome_channel_id", "channel", "/welcome-setup"),
    ("Verification channel", "verify_channel_id",  "channel", "/verify-setup"),
    ("Verification panel",   "verify_panel_id",    "message", "/verify-panel"),
    ("Member records",       "records_channel_id", "channel", "/records-setup"),
    ("Ops channel",          "op_channel_id",      "channel", "/op-setup"),
    ("Ops ping role",        "op_ping_role_id",    "role",    "/op-setup"),
    ("Officer role",         "officer_role_id",    "role",    "/officer-role"),
)


class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx) -> bool:
        return ctx.guild is not None

    @commands.hybrid_command(name="setup", description="What Jarcord is configured for, and what it still needs")
    @discord.app_commands.default_permissions(manage_guild=True)
    @commands.has_permissions(manage_guild=True)
    async def setup_status(self, ctx: commands.Context):
        e = embed(title="Jarcord setup", colour=ACCENT)
        ready, missing = [], []
        for label, key, kind, how in SETTINGS:
            value = get_setting(key)
            if value:
                shown = {"channel": f"<#{value}>", "role": f"<@&{value}>"}.get(kind, f"`{value}`")
                ready.append(f"**{label}** {shown}")
            else:
                missing.append(f"**{label}** run `{how}`")
        e.add_field(name=f"Configured ({len(ready)})",
                    value="\n".join(ready) or "*nothing yet*", inline=False)
        e.add_field(name=f"Not set ({len(missing)})",
                    value="\n".join(missing) or "*all done*", inline=False)
        e.set_footer(text="Anything unset means that feature stays silent")
        await ctx.send(embed=e, ephemeral=True)

    @commands.hybrid_command(name="officer-role", description="Role that may run staff commands without Manage Server")
    @discord.app_commands.default_permissions(manage_guild=True)
    @commands.has_permissions(manage_guild=True)
    async def officer_role(self, ctx: commands.Context, role: discord.Role = None):
        if role is None:
            current = get_setting("officer_role_id")
            await ctx.send(f"Officer role is <@&{current}>." if current else "No officer role set.")
            return
        set_setting("officer_role_id", str(role.id))
        await ctx.send(
            f"**{role.name}** can now run Jarcord's staff commands. Pick which ones they actually "
            "see in Server Settings, Integrations, Jarcord."
        )

    @commands.hybrid_command(name="dividers", description="Create blank divider roles for the role list")
    @discord.app_commands.default_permissions(manage_guild=True)
    @staff_check(manage_guild=True)
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
                await ctx.send(f"Stopped after **{made}**. Discord refused the next one: {exc.text or exc}")
                return
            made += 1
        print(f">> created {made} divider roles in guild {ctx.guild.id}")
        await ctx.send(
            f"Created **{made}** divider roles at the bottom of the list. "
            "Drag them between your groups in Server Settings → Roles."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Roles(bot))
