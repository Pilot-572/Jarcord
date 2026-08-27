# ── Jarcord — new-member verification (nickname → Operator) ──
from datetime import datetime, timezone

import discord
from discord.ext import commands

from db import get_setting, set_setting
from ui import ACCENT, embed

UNVERIFIED = "Unverified"
OPERATOR = "Operator"
# ponytail: channel names carry emoji and dividers ("📋｜register"), so an exact
# match is useless — fall back to a normalized substring, in priority order.
CHANNEL_WORDS = ("operator-id", "verify", "register")


def looks_unset(member: discord.Member) -> bool:
    """True if the nickname is empty or still just their Discord name."""
    nick = (member.nick or "").strip()
    if not nick:
        return True
    taken = {member.name.casefold()}
    if member.global_name:
        taken.add(member.global_name.casefold())
    return nick.casefold() in taken


async def find_role(guild: discord.Guild, name: str, create: bool = False):
    """Existing role by exact name — never modified. Created only if asked and missing."""
    role = discord.utils.get(guild.roles, name=name)
    if role is None and create:
        role = await guild.create_role(name=name, reason="Jarcord verification flow")
        print(f">> created role {name} in guild {guild.id}")
    return role


def find_channel(guild: discord.Guild):
    """Configured channel if /verify-setup ran, else the first arrival-ish channel."""
    cid = get_setting("verify_channel_id")
    if cid:
        channel = guild.get_channel(int(cid))
        if channel is not None:
            return channel
    for word in CHANNEL_WORDS:
        for channel in guild.text_channels:
            if word in channel.name.casefold():
                return channel
    return None


def prompt_embed(guild: discord.Guild, member: discord.Member = None) -> discord.Embed:
    e = embed(
        title="Operator ID required",
        colour=ACCENT,
        description=(
            f"Welcome to **{guild.name}**.\n"
            "Your access is restricted until you identify yourself."
        ),
    )
    e.add_field(
        name="1 · Set your nickname",
        value="Right-click your name → **Edit Server Profile** → set your nickname "
              "to your **exact Roblox username**.",
        inline=False,
    )
    e.add_field(
        name="2 · Confirm",
        value="Press **Confirm callsign** below. The rest of the server opens up immediately.",
        inline=False,
    )
    if member is not None:
        e.set_thumbnail(url=member.display_avatar.url)
        e.set_footer(text=f"{member} · {member.id}")
    else:
        e.set_thumbnail(url=guild.icon.url if guild.icon else discord.utils.MISSING)
    return e


class VerifyView(discord.ui.View):
    """Persistent — one static custom_id, the presser is the member being verified."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Confirm callsign", style=discord.ButtonStyle.success,
                       custom_id="jarcord:verify:confirm")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        # ponytail: no in-flight lock — add_roles/remove_roles are idempotent, so a
        # double-click at worst repeats a no-op API call.
        operator = await find_role(interaction.guild, OPERATOR)
        if operator is not None and operator in member.roles:
            await interaction.response.send_message(
                "You're already verified — the rest of the server is open to you.", ephemeral=True
            )
            return
        if looks_unset(member):
            await interaction.response.send_message(
                "Set your server nickname to your exact Roblox username first, then press this again.\n"
                "Right-click your name → **Edit Server Profile** → Nickname.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        try:
            operator = await find_role(interaction.guild, OPERATOR, create=True)
            await member.add_roles(operator, reason="verified callsign")
            unverified = await find_role(interaction.guild, UNVERIFIED)
            if unverified is not None and unverified in member.roles:
                await member.remove_roles(unverified, reason="verified callsign")
        except discord.Forbidden:
            print(f">> verify failed for {member.id}: missing Manage Roles or role hierarchy")
            await interaction.followup.send(
                f"I couldn't change your roles — I'm missing **Manage Roles**, or my role sits below "
                f"**{OPERATOR}**. Ping an admin.", ephemeral=True
            )
            return

        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(f">> verified {member.id} as {member.nick!r} at {stamp}")
        await interaction.followup.send(
            f"Verified as **{member.nick}** — welcome aboard, Operator.", ephemeral=True
        )


class Verify(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(VerifyView())  # survives restarts

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        operator = await find_role(member.guild, OPERATOR)
        if operator is not None and operator in member.roles:
            print(f">> {member.id} joined already holding {OPERATOR} — skipping verification")
            return

        try:
            unverified = await find_role(member.guild, UNVERIFIED, create=True)
            await member.add_roles(unverified, reason="awaiting verification")
        except discord.Forbidden:
            print(f">> couldn't assign {UNVERIFIED} to {member.id}: missing Manage Roles or hierarchy")

        channel = find_channel(member.guild)
        if channel is None:
            print(f">> no arrival channel found — run /verify-setup; no prompt sent for {member.id}")
            return
        try:
            await channel.send(content=member.mention,
                               embed=prompt_embed(member.guild, member), view=VerifyView())
        except discord.Forbidden:
            print(f">> can't post in #{channel.name} — no verification prompt sent for {member.id}")

    @commands.hybrid_command(name="verify-setup", description="Set the channel new members are greeted in")
    @commands.has_permissions(manage_guild=True)
    async def verify_setup(self, ctx: commands.Context, channel: discord.TextChannel):
        set_setting("verify_channel_id", str(channel.id))
        msg = f"New members will be prompted to verify in {channel.mention}."
        operator = await find_role(ctx.guild, OPERATOR)
        if operator is not None and operator >= ctx.guild.me.top_role:
            msg += ("\n⚠️ " + f"**{OPERATOR}** sits above my role — I won't be able to "
                    "assign it. Move Jarcord higher.")
        await ctx.send(msg)

    @commands.hybrid_command(name="verify-panel", description="Post a standing verification panel")
    @commands.has_permissions(manage_guild=True)
    async def verify_panel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        # ponytail: on_member_join only fires for new joins — this covers everyone already here.
        target = channel or find_channel(ctx.guild) or ctx.channel
        try:
            await target.send(embed=prompt_embed(ctx.guild), view=VerifyView())
        except discord.Forbidden:
            await ctx.send(f"I can't post in {target.mention} — give me Send Messages there.")
            return
        if ctx.interaction:
            await ctx.send(f"Panel posted in {target.mention}.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Verify(bot))
