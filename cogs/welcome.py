# ── Jarcord: member welcome ──
import discord
from discord.ext import commands

from db import get_setting, set_setting
from ui import ACCENT, embed

DEFAULT_TEXT = "Good to have you, {user}. Get yourself squared away and you're in."


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


def welcome_embed(member: discord.Member) -> discord.Embed:
    e = embed(
        title=member.display_name,
        description=render(get_setting("welcome_text") or DEFAULT_TEXT, member),
        colour=ACCENT,
    )
    e.set_author(name=member.guild.name,
                 icon_url=member.guild.icon.url if member.guild.icon else discord.utils.MISSING)
    e.set_thumbnail(url=member.display_avatar.url)

    steps = []
    rules = named(member.guild, "rules")
    if rules:
        steps.append(f"Read {rules.mention}.")
    verify = named(member.guild, "register") or named(member.guild, "verify")
    if verify:
        steps.append(f"Verify in {verify.mention} to unlock the rest of the server.")
    if steps:
        e.add_field(name="Get started", value="\n".join(steps), inline=False)

    if member.guild.member_count:
        e.set_footer(text=f"Member #{member.guild.member_count}")
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
    @commands.has_permissions(manage_guild=True)
    async def welcome_setup(self, ctx: commands.Context, channel: discord.TextChannel,
                            message: str = None):
        set_setting("welcome_channel_id", str(channel.id))
        msg = f"New members will be welcomed in {channel.mention}."
        if message:
            set_setting("welcome_text", message)
            msg += " Message updated."
        msg += " Placeholders: `{user}`, `{name}`, `{server}`, `{count}`."
        await ctx.send(msg)

    @commands.hybrid_command(name="welcome-preview", description="See the welcome card without waiting for a join")
    @commands.has_permissions(manage_guild=True)
    async def welcome_preview(self, ctx: commands.Context):
        await ctx.send(embed=welcome_embed(ctx.author), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
