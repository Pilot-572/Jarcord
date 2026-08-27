# ── Jarcord: info panels (banner + section cards + link buttons) ──
import json
from pathlib import Path

import discord
from discord.ext import commands

from ui import ACCENT, embed

PANEL_DIR = Path(__file__).parent.parent / "panels"


def panel_names() -> list[str]:
    return sorted(p.stem for p in PANEL_DIR.glob("*.json"))


def load_panel(name: str) -> dict | None:
    # whitelist by listing, never build a path from user input
    if name not in panel_names():
        return None
    return json.loads((PANEL_DIR / f"{name}.json").read_text(encoding="utf-8"))


def build(panel: dict) -> tuple[list[discord.Embed], discord.ui.View | None]:
    colour = discord.Colour(int(panel["colour"], 16)) if panel.get("colour") else ACCENT
    embeds = []

    if panel.get("banner"):
        head = discord.Embed(colour=colour)
        head.set_image(url=panel["banner"])
        embeds.append(head)

    for section in panel.get("sections", [])[:9]:  # Discord allows 10 embeds/message
        e = embed(title=section.get("title"), description=section.get("body"), colour=colour)
        if section.get("thumbnail"):
            e.set_thumbnail(url=section["thumbnail"])
        e.timestamp = None  # panels are reference posts, not events
        embeds.append(e)

    buttons = panel.get("buttons", [])[:5]
    view = None
    if buttons:
        view = discord.ui.View()
        for b in buttons:
            view.add_item(discord.ui.Button(
                label=b["label"], url=b["url"], emoji=b.get("emoji"),
                style=discord.ButtonStyle.link,
            ))
    return embeds, view


class Panels(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="panel", description="Post an info panel (needs Manage Messages)")
    @commands.has_permissions(manage_messages=True)
    async def panel(self, ctx: commands.Context, name: str):
        panel = load_panel(name)
        if panel is None:
            await ctx.send(f"No panel called `{name}`. Available: {', '.join(panel_names()) or 'none'}")
            return
        embeds, view = build(panel)
        if not embeds:
            await ctx.send(f"Panel `{name}` has no banner or sections.")
            return
        await ctx.send(embeds=embeds, view=view)

    @commands.hybrid_command(name="panel-list", description="List available info panels")
    async def panel_list(self, ctx: commands.Context):
        names = panel_names()
        await ctx.send(embed=embed(
            title="Info panels",
            description="\n".join(f"`{n}`" for n in names) if names
            else "None yet. Drop a JSON file in `panels/`.",
        ))


async def setup(bot: commands.Bot):
    await bot.add_cog(Panels(bot))
