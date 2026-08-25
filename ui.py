# ── Jarcord — shared embed styling ──
import discord

ACCENT = discord.Colour(0x94A3B8)    # ops / default — steel
RATING = discord.Colour(0xE2E8F0)    # ratings — light steel
ACTIVITY = discord.Colour(0x64748B)  # activity — dark steel


def embed(title: str = None, description: str = None,
          colour: discord.Colour = ACCENT) -> discord.Embed:
    return discord.Embed(
        title=title, description=description, colour=colour,
        timestamp=discord.utils.utcnow(),
    )
