# ── Jarcord — shared embed styling ──
import discord

ACCENT = discord.Colour(0x6366F1)


def embed(title: str = None, description: str = None) -> discord.Embed:
    return discord.Embed(title=title, description=description, colour=ACCENT)
