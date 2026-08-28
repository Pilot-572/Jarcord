# ── Jarcord: member welcome ──
import discord
from discord.ext import commands

from db import get_setting, set_setting
from ui import ACCENT, embed, staff_check

DEFAULT_TEXT = "Good to have you, {user}. Three quick steps and you're in."


def render(text: str, member: discord.Member) -> str:
    # ponytail: str.format, not a template engine. Unknown keys raise, so fall back.
    try:
        return text.format(user=member.mention, name=member.display_name,
                           server=member.guild.name, count=member.guild.member_count)
    except (KeyError, IndexError):
        return DEFAULT_TEXT.format(user=member.mention, name=member.display_name,
                                   server=member.guild.name, count=member.guild.member_count)


def named(guild: discord.Guild, word: str):
    """First text channel whose name contains `word`, ignoring emoji and dividers."""
    return discord.utils.find(lambda c: word in c.name.casefold(), guild.text_channels)


def ordinal(n: int) -> str:
    # 11th, 12th, 13th are the exceptions to the 1st/2nd/3rd rule
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def welcome_embed(member: discord.Member) -> discord.Embed:
    guild = member.guild
    e = embed(
        title=f"{member.display_name} joined",
        description=render(get_setting("welcome_text") or DEFAULT_TEXT, member),
        colour=ACCENT,
    )
    e.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else discord.utils.MISSING)
    e.set_thumbnail(url=member.display_avatar.url)
    if guild.banner:
        e.set_image(url=guild.banner.url)

    steps = []
    rules = named(guild, "rules")
    if rules:
        steps.append(f"**1.** Read {rules.mention}.")
    verify = named(guild, "register") or named(guild, "verify")
    if verify:
        steps.append(f"**{len(steps) + 1}.** Hit **Verify** in {verify.mention}. It takes about a minute.")
    steps.append(f"**{len(steps) + 1}.** The rest of the server opens up and you're an Operator.")
    e.add_field(name="Start here", value="\n".join(steps), inline=False)

    if guild.member_count:
        e.add_field(name="Headcount", value=f"{ordinal(guild.member_count)} member", inline=True)
    e.add_field(name="Account age", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
    e.set_footer(text=str(member), icon_url=member.display_avatar.url)
    return e


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        channel_id = get_setting("welcome_channel_id")
        if not channel_id:
            return  # not configured, stay quiet
        channel = member.guild.get_channel(int(channel_id))
        if channel is None:
            print(f">> welcome channel {channel_id} is gone, run /welcome-setup")
            return
        try:
            await channel.send(content=member.mention, embed=welcome_embed(member))
        except discord.Forbidden:
            print(f">> can't post in #{channel.name}, no welcome sent for {member.id}")

    @commands.hybrid_command(name="welcome-setup", description="Set the welcome channel and message")
    @discord.app_commands.default_permissions(manage_guild=True)
    @staff_check(manage_guild=True)
    async def welcome_setup(self, ctx: commands.Context, channel: discord.TextChannel,
                            message: str = None):
        set_setting("welcome_channel_id", str(channel.id))
        msg = f"Welcome cards go to {channel.mention}."
        if message:
            set_setting("welcome_text", message)
            msg += " Message updated."
        msg += " Placeholders: `{user}`, `{name}`, `{server}`, `{count}`."
        await ctx.send(msg)

    @commands.hybrid_command(name="welcome-preview", description="See the welcome card without waiting for a join")
    @discord.app_commands.default_permissions(manage_guild=True)
    @staff_check(manage_guild=True)
    async def welcome_preview(self, ctx: commands.Context):
        await ctx.send(embed=welcome_embed(ctx.author), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
