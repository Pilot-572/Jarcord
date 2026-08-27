# ── Jarcord: shared embed styling + user-facing error text ──
import discord
from discord import app_commands
from discord.ext import commands

from db import get_setting

ACCENT = discord.Colour(0x94A3B8)    # ops / default, steel
RATING = discord.Colour(0xE2E8F0)    # ratings, light steel
ACTIVITY = discord.Colour(0x64748B)  # activity, dark steel


def embed(title: str = None, description: str = None,
          colour: discord.Colour = ACCENT) -> discord.Embed:
    return discord.Embed(
        title=title, description=description, colour=colour,
        timestamp=discord.utils.utcnow(),
    )


def _allowed(member, perms, officer: bool) -> bool:
    """Admins always pass. So does anyone holding the named Discord permissions. The role
    set with /officer-role passes only on commands marked officer=True."""
    mine = member.guild_permissions
    if mine.administrator or (perms and all(getattr(mine, p, False) for p in perms)):
        return True
    if officer:
        role_id = get_setting("officer_role_id")
        if role_id and any(r.id == int(role_id) for r in member.roles):
            return True
    return False


def is_officer(member) -> bool:
    """Manage Server, or the configured officer role. For runtime branching, not gating."""
    return _allowed(member, {"manage_guild": True}, officer=True)


def staff_check(*, officer: bool = False, **perms):
    """Gate for prefix and hybrid commands."""
    async def predicate(ctx) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        if _allowed(ctx.author, perms, officer):
            return True
        raise commands.MissingPermissions(list(perms))
    return commands.check(predicate)


def app_staff_check(*, officer: bool = False, **perms):
    """Same gate for slash-only commands."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.NoPrivateMessage()
        if _allowed(interaction.user, perms, officer):
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
