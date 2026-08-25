# ── Jarcord — shared embed styling ──
import discord

ACCENT = discord.Colour(0x6366F1)    # ops / default — indigo
RATING = discord.Colour(0xF59E0B)    # ratings — amber
ACTIVITY = discord.Colour(0x10B981)  # activity — emerald


def embed(title: str = None, description: str = None,
          colour: discord.Colour = ACCENT) -> discord.Embed:
    return discord.Embed(
        title=title, description=description, colour=colour,
        timestamp=discord.utils.utcnow(),
    )
