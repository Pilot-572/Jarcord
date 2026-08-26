# ── Jarcord — shared embed styling + user-facing error text ──
import discord
from discord import app_commands
from discord.ext import commands

ACCENT = discord.Colour(0x94A3B8)    # ops / default — steel
RATING = discord.Colour(0xE2E8F0)    # ratings — light steel
ACTIVITY = discord.Colour(0x64748B)  # activity — dark steel


def embed(title: str = None, description: str = None,
          colour: discord.Colour = ACCENT) -> discord.Embed:
    return discord.Embed(
        title=title, description=description, colour=colour,
        timestamp=discord.utils.utcnow(),
    )


def check_message(error) -> str | None:
    """Friendly text for permission/check failures, or None if not one."""
    if isinstance(error, (commands.MissingPermissions, app_commands.MissingPermissions)):
        return "You don't have permission to use that."
    if isinstance(error, (commands.BotMissingPermissions, app_commands.BotMissingPermissions)):
        missing = ", ".join(error.missing_permissions)
        return f"I'm missing the **{missing}** permission — add it in Server Settings → Roles."
    if isinstance(error, (commands.CheckFailure, app_commands.CheckFailure)):
        return "That command can't be used here."
    return None
