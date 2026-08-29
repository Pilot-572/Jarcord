# ── Jarcord: server setup and role utilities ──
import discord
from discord.ext import commands

from cogs.verify import OPERATOR
from db import get_setting, set_setting
from ui import ACCENT, embed, is_officer, log_action, staff_check

DIVIDER = "─" * 32  # ponytail: fixed width, Discord truncates the role list anyway
SERVER_HOST = "Server Host"  # whoever owns the private server, may change the code without being Command

# (label, settings key, what it points at, the command that sets it)
SETTINGS = (
    ("Welcome channel",      "welcome_channel_id", "channel", "/welcome-setup"),
    ("Verification channel", "verify_channel_id",  "channel", "/verify-setup"),
    ("Verification panel",   "verify_panel_id",    "message", "/verify-panel"),
    ("Member records",       "records_channel_id", "channel", "/records-setup"),
    ("Ops channel",          "op_channel_id",      "channel", "/op-setup"),
    ("Ops ping role",        "op_ping_role_id",    "role",    "/op-setup"),
    ("Op timezone",          "op_timezone",        "text",    "/op-setup"),
    ("Officer role",         "officer_role_id",    "role",    "/officer-role"),
    ("Promotions channel",   "promotions_channel_id", "channel", "/promotions-setup"),
    ("Log channel",          "log_channel_id",     "channel", "/logs-setup"),
    ("Server code",          "server_code",        "secret",  "/code-set"),
)


def has_role(member: discord.Member, name: str) -> bool:
    return any(r.name == name for r in member.roles)


def code_text(member: discord.Member) -> str:
    """What /code and the hub's key button say. Verified members only, visitors get told why."""
    if not (has_role(member, OPERATOR) or is_officer(member)):
        return "Verify first, then the code is yours."
    code = get_setting("server_code")
    if not code:
        return "No server code set yet. Command sets it with `/code-set`."
    return f"Private server code: `{code}`\nKeep it inside this server."


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
                # secrets never render here, /setup can be run as a public prefix command
                shown = {"channel": f"<#{value}>", "role": f"<@&{value}>",
                         "secret": "`set`"}.get(kind, f"`{value}`")
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

    @commands.hybrid_command(name="logs-setup", description="Channel where Jarcord writes what it did")
    @discord.app_commands.default_permissions(manage_guild=True)
    @commands.has_permissions(manage_guild=True)
    async def logs_setup(self, ctx: commands.Context, channel: discord.TextChannel):
        set_setting("log_channel_id", str(channel.id))
        await log_action(ctx.guild, "Logging started", ctx.author, f"Logs go to {channel.mention}")
        await ctx.send(
            f"Logging to {channel.mention}: verifications, promotions, warnings, ops, "
            "message clears and code changes. Keep it Command only, it names members.",
            ephemeral=True)

    @commands.hybrid_command(name="c", description="Clear the last N messages in this channel")
    @discord.app_commands.describe(count="How many messages to delete, 1 to 100")
    @discord.app_commands.default_permissions(manage_messages=True)
    @staff_check(officer=True, manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True, read_message_history=True)
    async def clear(self, ctx: commands.Context, count: commands.Range[int, 1, 100]):
        # Pinned messages are the panels and the hub, so they are never in the sweep.
        # ponytail: Discord's own cap is 100 per bulk delete, so the range is the cap.
        if ctx.interaction is not None:
            await ctx.defer(ephemeral=True)
            limit = count
        else:
            limit = count + 1  # the "!c 5" message itself is one of the last messages
        try:
            gone = await ctx.channel.purge(limit=limit, check=lambda m: not m.pinned)
        except discord.HTTPException as exc:
            await ctx.send(
                "Couldn't clear those. Discord only bulk deletes messages under 14 days old, "
                f"and it said: {exc.text or exc}", ephemeral=True)
            return
        n = max(len(gone) - (0 if ctx.interaction else 1), 0)
        print(f">> {ctx.author.id} cleared {n} messages in #{ctx.channel.name}")
        await log_action(ctx.guild, "Messages cleared", ctx.author,
                         f"{n} message(s) in {ctx.channel.mention}")
        # ponytail: no receipt in the channel. A slash interaction still has to be
        # answered or Discord shows a failure, and only the caller sees that.
        if ctx.interaction is not None:
            await ctx.send(f"Done, {n} gone.", ephemeral=True)

    @commands.hybrid_command(name="code", description="The current private server code")
    async def code(self, ctx: commands.Context):
        if ctx.interaction is None:  # a prefix reply is public, and the whole point is that this is not
            await ctx.send("Use `/code` so only you see it.")
            return
        await ctx.send(code_text(ctx.author), ephemeral=True)

    @commands.hybrid_command(name="code-set", description="Change the private server code (Command or Server Host)")
    async def code_set(self, ctx: commands.Context, *, code: str):
        if not (is_officer(ctx.author) or has_role(ctx.author, SERVER_HOST)):
            await ctx.send(f"Command or the **{SERVER_HOST}** role only.", ephemeral=True)
            return
        set_setting("server_code", code.strip())
        print(f">> server code changed by {ctx.author.id}")
        # the code itself never goes in the log, only that it moved
        await log_action(ctx.guild, "Server code changed", ctx.author)
        await ctx.send("Server code updated. `/code` and the information hub show it live.", ephemeral=True)

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
