# ── Jarcord: new-member verification (Roblox callsign to Operator) ──
from datetime import datetime, timezone

import discord
from discord.ext import commands

from cogs.profile import resolve_roblox
from db import conn, get_setting, set_setting
from ui import ACCENT, embed

UNVERIFIED = "Unverified"
OPERATOR = "Operator"
# ponytail: channel names carry emoji and dividers ("📋｜register"), so an exact
# match is useless. Fall back to a normalized substring, in priority order.
CHANNEL_WORDS = ("operator-id", "verify", "register")


async def find_role(guild: discord.Guild, name: str, create: bool = False):
    """Existing role by exact name. Never modified. Created only if asked and missing."""
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
        name="How it works",
        value="Press **Verify** below and type your Roblox username. "
              "Nothing goes in chat. Only you see the form.",
        inline=False,
    )
    e.add_field(
        name="What happens next",
        value="Your nickname is set for you and the rest of the server opens up immediately.",
        inline=False,
    )
    if member is not None:
        e.set_thumbnail(url=member.display_avatar.url)
        e.set_footer(text=f"{member} · {member.id}")
    elif guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    return e


async def panel_live(channel: discord.TextChannel) -> bool:
    """True if a standing /verify-panel post still exists in this channel."""
    panel_id = get_setting("verify_panel_id")
    if not panel_id:
        return False
    try:
        await channel.fetch_message(int(panel_id))
        return True
    except discord.HTTPException:
        return False  # deleted, or posted somewhere else


async def clear_prompts(guild: discord.Guild, member: discord.Member) -> None:
    """Delete the bot's join prompts that ping this member. The standing panel has no
    content, so it never matches and survives."""
    channel = find_channel(guild)
    if channel is None:
        return
    try:
        async for msg in channel.history(limit=50):
            if msg.author == guild.me and str(member.id) in msg.content:
                await msg.delete()
    except discord.HTTPException:
        pass  # no history access, not worth failing the verification over


async def grant_operator(member: discord.Member) -> None:
    """Swap Unverified for Operator. Raises discord.Forbidden if the bot can't."""
    operator = await find_role(member.guild, OPERATOR, create=True)
    await member.add_roles(operator, reason="verified callsign")
    unverified = await find_role(member.guild, UNVERIFIED)
    if unverified is not None and unverified in member.roles:
        await member.remove_roles(unverified, reason="verified callsign")


class CallsignModal(discord.ui.Modal, title="Operator ID"):
    roblox = discord.ui.TextInput(
        label="Roblox username",
        placeholder="exactly as it appears on your profile",
        max_length=20,
    )
    callsign = discord.ui.TextInput(
        label="What should people call you?",
        placeholder="leave blank to use your Roblox name",
        required=False,
        max_length=24,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        member = interaction.user

        found = await resolve_roblox(str(self.roblox))
        if found is None:
            await interaction.followup.send(
                f"I couldn't find the Roblox user **{self.roblox}**. Check the spelling and try again.",
                ephemeral=True,
            )
            return
        rid, name = found

        conn.execute(
            """INSERT INTO profiles (user_id, roblox_name, roblox_id) VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET roblox_name = ?, roblox_id = ?""",
            (member.id, name, rid, name, rid),
        )
        conn.commit()

        nick = (str(self.callsign).strip() or name)[:32]
        note = ""
        try:
            await member.edit(nick=nick, reason="verified callsign")
        except discord.Forbidden:
            note = "\nI couldn't set your nickname. Set it yourself, or ask an admin."

        try:
            await grant_operator(member)
        except discord.Forbidden:
            print(f">> verify failed for {member.id}: missing Manage Roles or role hierarchy")
            await interaction.followup.send(
                f"Linked **{name}**, but I couldn't change your roles. I'm missing **Manage Roles**, "
                f"or my role sits below **{OPERATOR}**. Ping an admin.", ephemeral=True
            )
            return

        await clear_prompts(interaction.guild, member)

        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(f">> verified {member.id} as {nick!r} (roblox {name}/{rid}) at {stamp}")
        await interaction.followup.send(
            f"Verified as **{nick}**. Roblox account **{name}** linked. Welcome aboard, Operator.{note}",
            ephemeral=True,
        )


class VerifyView(discord.ui.View):
    """Persistent view. One static custom_id, the presser is the member being verified."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.success,
                       custom_id="jarcord:verify:confirm")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ponytail: no in-flight lock, role writes are idempotent, so a double-click
        # at worst repeats a no-op API call.
        operator = await find_role(interaction.guild, OPERATOR)
        if operator is not None and operator in interaction.user.roles:
            await interaction.response.send_message(
                "You're already verified. The rest of the server is open to you.", ephemeral=True
            )
            return
        await interaction.response.send_modal(CallsignModal())


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
            print(f">> {member.id} joined already holding {OPERATOR}, skipping verification")
            return

        try:
            unverified = await find_role(member.guild, UNVERIFIED, create=True)
            await member.add_roles(unverified, reason="awaiting verification")
        except discord.Forbidden:
            print(f">> couldn't assign {UNVERIFIED} to {member.id}: missing Manage Roles or hierarchy")

        channel = find_channel(member.guild)
        if channel is None:
            print(f">> no arrival channel found, run /verify-setup; no prompt sent for {member.id}")
            return
        try:
            if await panel_live(channel):
                # ponytail: the panel is already sitting there, so just point at it
                # instead of posting a second copy of the same card.
                await channel.send(
                    f"{member.mention} welcome to **{member.guild.name}**. "
                    "Press **Verify** on the panel above to unlock the server."
                )
            else:
                await channel.send(content=member.mention,
                                   embed=prompt_embed(member.guild, member), view=VerifyView())
        except discord.Forbidden:
            print(f">> can't post in #{channel.name}, no verification prompt sent for {member.id}")

    @commands.hybrid_command(name="verify-setup", description="Set the channel new members are greeted in")
    @commands.has_permissions(manage_guild=True)
    async def verify_setup(self, ctx: commands.Context, channel: discord.TextChannel):
        set_setting("verify_channel_id", str(channel.id))
        msg = f"New members will be prompted to verify in {channel.mention}."
        operator = await find_role(ctx.guild, OPERATOR)
        if operator is not None and operator >= ctx.guild.me.top_role:
            msg += ("\nWarning: " + f"**{OPERATOR}** sits above my role, so I won't be able to "
                    "assign it. Move Jarcord higher.")
        await ctx.send(msg)

    @commands.hybrid_command(name="verify-panel", description="Post a standing verification panel")
    @commands.has_permissions(manage_guild=True)
    async def verify_panel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        # ponytail: on_member_join only fires for new joins, so this covers everyone already here.
        target = channel or find_channel(ctx.guild) or ctx.channel
        try:
            msg = await target.send(embed=prompt_embed(ctx.guild), view=VerifyView())
        except discord.Forbidden:
            await ctx.send(f"I can't post in {target.mention}. Give me Send Messages there.")
            return
        set_setting("verify_panel_id", str(msg.id))
        if ctx.interaction:
            await ctx.send(f"Panel posted in {target.mention}.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Verify(bot))
