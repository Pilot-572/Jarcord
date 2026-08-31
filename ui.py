# ── Jarcord: shared embed styling + user-facing error text ──
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from db import get_setting

ACCENT = discord.Colour(0x94A3B8)    # ops / default, steel
RATING = discord.Colour(0xE2E8F0)    # ratings, light steel
ACTIVITY = discord.Colour(0x64748B)  # activity, dark steel


def ago(text: str) -> str:
    """Stored timestamps are UTC. Render them as Discord markup so every reader sees
    their own local time instead of having to do the conversion."""
    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return text
    return f"<t:{int(dt.timestamp())}:R>"


def embed(title: str = None, description: str = None,
          colour: discord.Colour = ACCENT) -> discord.Embed:
    return discord.Embed(
        title=title, description=description, colour=colour,
        timestamp=discord.utils.utcnow(),
    )


async def log_action(guild, action: str, actor=None, detail: str = None) -> None:
    """Write one line to the log channel, if /logs-setup named one. Never raises:
    a logging failure must not take the command that triggered it down."""
    channel_id = get_setting("log_channel_id")
    if not channel_id or guild is None:
        return
    channel = guild.get_channel(int(channel_id))
    if channel is None:
        return
    e = embed(title=action, description=detail, colour=ACTIVITY)
    if actor is not None:
        e.set_author(name=str(actor), icon_url=actor.display_avatar.url)
        e.set_footer(text=f"user {actor.id}")
    try:
        await channel.send(embed=e)
    except discord.HTTPException as exc:
        print(f">> couldn't log to channel {channel_id}: {exc!r}")


def _allowed(member, perms, officer: bool, roles=()) -> bool:
    """Admins always pass. So does anyone holding the named Discord permissions. The role
    set with /officer-role passes only on commands marked officer=True, and any role named
    in `roles` passes for that command alone (a position, like Op Planner on /op)."""
    mine = member.guild_permissions
    if mine.administrator or (perms and all(getattr(mine, p, False) for p in perms)):
        return True
    if officer:
        role_id = get_setting("officer_role_id")
        if role_id and any(r.id == int(role_id) for r in member.roles):
            return True
    return bool(roles) and any(r.name in roles for r in member.roles)


def is_officer(member, roles=()) -> bool:
    """Manage Server, or the configured officer role. For runtime branching, not gating."""
    return _allowed(member, {"manage_guild": True}, officer=True, roles=roles)


def staff_check(*, officer: bool = False, roles=(), **perms):
    """Gate for prefix and hybrid commands."""
    async def predicate(ctx) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        if _allowed(ctx.author, perms, officer, roles):
            return True
        raise commands.MissingPermissions(list(perms))
    return commands.check(predicate)


def app_staff_check(*, officer: bool = False, roles=(), **perms):
    """Same gate for slash-only commands."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.NoPrivateMessage()
        if _allowed(interaction.user, perms, officer, roles):
            return True
        raise app_commands.MissingPermissions(list(perms))
    return app_commands.check(predicate)


def check_message(error) -> str | None:
    """Friendly text for permission/check failures, or None if not one."""
    if isinstance(error, (commands.MissingPermissions, app_commands.MissingPermissions)):
        return "You don't have permission to use that."
    if isinstance(error, (commands.BotMissingPermissions, app_commands.BotMissingPermissions)):
        missing = ", ".join(error.missing_permissions)
        return f"I'm missing the **{missing}** permission. Add it in Server Settings → Roles."
    if isinstance(error, (commands.CheckFailure, app_commands.CheckFailure)):
        return "That command can't be used here."
    return None
