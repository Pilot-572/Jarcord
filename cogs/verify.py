# ── Jarcord: new-member verification (Roblox callsign to Operator) ──
from datetime import datetime, timezone

import discord
from discord.ext import commands

from cogs.profile import CONTINENTS, resolve_roblox, save_profile, set_continent
from db import conn, get_setting, set_setting
from ui import ACCENT, embed, staff_check

UNVERIFIED = "Unverified"
OPERATOR = "Operator"
# ponytail: channel names carry emoji and dividers ("📋｜register"), so an exact
# match is useless. Fall back to a normalized substring, in priority order.
CHANNEL_WORDS = ("operator-id", "verify", "register")
# ponytail: fixed clock blocks, not "evenings". One person's evening is another's night.
PLAY_BLOCKS = ("00:00 to 04:00", "04:00 to 08:00", "08:00 to 12:00",
               "12:00 to 16:00", "16:00 to 20:00", "20:00 to 00:00")
HEARD_FROM = ("A friend", "Roblox group", "Server listing", "Advert", "Somewhere else")
AGE_GROUPS = ("13-15", "16-17", "18-20", "21 or older", "Rather not say")
STEP_TIMEOUT = 600  # ponytail: ten minutes to finish. Abandon it and just press Verify again.


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
        label="What do people call you in-game?",
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
        save_profile(member.id, roblox_name=name, roblox_id=rid)

        nick = (str(self.callsign).strip() or name)[:32]
        note = ""
        try:
            await member.edit(nick=nick, reason="verified callsign")
        except discord.Forbidden:
            note = "\nI couldn't set your nickname, so set it yourself or ask an admin."

        await interaction.followup.send(
            f"**{name}** linked and your nickname is now **{nick}**.{note}\nOne more step.",
            view=LocationStep(), ephemeral=True,
        )


class LocationModal(discord.ui.Modal, title="Where and when you play"):
    where = discord.ui.Label(
        text="Where are you based?",
        description="sets your continent role so ops can be timed around you",
        component=discord.ui.Select(
            placeholder="pick your continent",
            options=[discord.SelectOption(label=c) for c in CONTINENTS],
        ),
    )
    hours = discord.ui.Label(
        text="When are you usually online?",
        description="pick up to three",
        component=discord.ui.Select(
            placeholder="optional",
            required=False,
            min_values=0,
            max_values=3,
            options=[discord.SelectOption(label=b) for b in PLAY_BLOCKS],
        ),
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        member = interaction.user

        note = ""
        picked = self.where.component.values
        if picked and not await set_continent(member, picked[0]):
            note = f"\nSaved **{picked[0]}**, but I couldn't assign the continent role."
        if self.hours.component.values:
            save_profile(member.id, play_hours=", ".join(self.hours.component.values))

        await interaction.followup.send(
            f"Got it.{note}\nVerify now, or answer three optional questions first.",
            view=FinishStep(), ephemeral=True,
        )


class ExtrasModal(discord.ui.Modal, title="A few more questions"):
    heard = discord.ui.Label(
        text="How did you hear about us?",
        component=discord.ui.Select(
            placeholder="pick one",
            required=False,
            options=[discord.SelectOption(label=h) for h in HEARD_FROM],
        ),
    )
    age = discord.ui.Label(
        text="Age group",
        component=discord.ui.Select(
            placeholder="pick one",
            required=False,
            options=[discord.SelectOption(label=a) for a in AGE_GROUPS],
        ),
    )
    experience = discord.ui.TextInput(
        label="Previous experience",
        placeholder="other factions, roles you've held, how long you've played",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=300,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        answers = {}
        if self.heard.component.values:
            answers["heard_from"] = self.heard.component.values[0]
        if self.age.component.values:
            answers["age_group"] = self.age.component.values[0]
        if str(self.experience).strip():
            answers["experience"] = str(self.experience).strip()
        if answers:
            save_profile(interaction.user.id, **answers)
        await finish(interaction)


def record_embed(member: discord.Member) -> discord.Embed:
    """Everything a member told us, on one card for the records channel."""
    p = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (member.id,)).fetchone()
    e = embed(title=member.display_name, colour=ACCENT)
    e.set_author(name="Member record", icon_url=member.display_avatar.url)
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="Discord", value=f"{member.mention}\n`{member}`", inline=True)
    if p and p["roblox_name"]:
        e.add_field(
            name="Roblox",
            value=f"[{p['roblox_name']}](https://www.roblox.com/users/{p['roblox_id']}/profile)",
            inline=True,
        )
    e.add_field(name="Continent", value=(p["continent"] if p else None) or "not given", inline=True)
    for label, column in (("Usually online", "play_hours"), ("Age group", "age_group"),
                          ("Found us via", "heard_from"), ("Experience", "experience")):
        if p and p[column]:
            e.add_field(name=label, value=p[column], inline=False)
    warned = conn.execute(
        "SELECT COUNT(*) AS n FROM warnings WHERE user_id = ?", (member.id,)
    ).fetchone()["n"]
    if warned:
        e.add_field(name="Warnings", value=str(warned), inline=True)
    e.add_field(name="Account created", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
    if member.joined_at:
        e.add_field(name="Joined server", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
    e.set_footer(text=f"ID {member.id}")
    return e


async def post_record(member: discord.Member) -> None:
    channel_id = get_setting("records_channel_id")
    if not channel_id:
        return  # not configured, stay quiet
    channel = member.guild.get_channel(int(channel_id))
    if channel is None:
        print(f">> records channel {channel_id} is gone, run /records-setup")
        return
    try:
        await channel.send(embed=record_embed(member))
    except discord.Forbidden:
        print(f">> can't post in #{channel.name}, no record filed for {member.id}")


async def finish(interaction: discord.Interaction) -> None:
    """Last step of every path: grant the role, tidy up, confirm."""
    member = interaction.user
    row = conn.execute(
        "SELECT roblox_name FROM profiles WHERE user_id = ?", (member.id,)
    ).fetchone()
    name = row["roblox_name"] if row else "your account"

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
    await post_record(member)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f">> verified {member.id} as {member.display_name!r} (roblox {name}) at {stamp}")
    await interaction.followup.send(
        f"Verified as **{member.display_name}**. Welcome aboard, Operator.", ephemeral=True
    )


class LocationStep(discord.ui.View):
    """Modals can't chain, so a button carries them from step one to step two."""

    def __init__(self):
        super().__init__(timeout=STEP_TIMEOUT)

    @discord.ui.button(label="Where and when you play", style=discord.ButtonStyle.primary)
    async def go(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LocationModal())


class FinishStep(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=STEP_TIMEOUT)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.success)
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await finish(interaction)

    @discord.ui.button(label="A few more questions", style=discord.ButtonStyle.secondary)
    async def extras(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ExtrasModal())


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
    @discord.app_commands.default_permissions(manage_guild=True)
    @staff_check(manage_guild=True)
    async def verify_setup(self, ctx: commands.Context, channel: discord.TextChannel):
        set_setting("verify_channel_id", str(channel.id))
        msg = f"New members will be prompted to verify in {channel.mention}."
        operator = await find_role(ctx.guild, OPERATOR)
        if operator is not None and operator >= ctx.guild.me.top_role:
            msg += ("\nWarning: " + f"**{OPERATOR}** sits above my role, so I won't be able to "
                    "assign it. Move Jarcord higher.")
        await ctx.send(msg)

    @commands.hybrid_command(name="records-setup", description="Set the channel member records are filed in")
    @discord.app_commands.default_permissions(manage_guild=True)
    @staff_check(manage_guild=True)
    async def records_setup(self, ctx: commands.Context, channel: discord.TextChannel):
        set_setting("records_channel_id", str(channel.id))
        await ctx.send(f"Member records will be filed in {channel.mention}.")

    @commands.hybrid_command(name="record", description="Re-file a member's record")
    @discord.app_commands.default_permissions(manage_guild=True)
    @staff_check(officer=True, manage_guild=True)
    async def record(self, ctx: commands.Context, member: discord.Member):
        await ctx.send(embed=record_embed(member))

    @commands.hybrid_command(name="verify-panel", description="Post a standing verification panel")
    @discord.app_commands.default_permissions(manage_guild=True)
    @staff_check(officer=True, manage_guild=True)
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
