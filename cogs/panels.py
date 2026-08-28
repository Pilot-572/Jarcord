# ── Jarcord: info panels (banner + section cards + buttons) and the information hub ──
import json
import re
from pathlib import Path

import discord
from discord.ext import commands

from cogs.roles import code_text
from ui import ACCENT, embed, staff_check

PANEL_DIR = Path(__file__).parent.parent / "panels"
ASSET_DIR = PANEL_DIR / "assets"
CODE_PAGE = "code"  # ponytail: the one hub button that is not a panel file
ROLE_TOKEN = re.compile(r"\{role:([^}]+)\}")


def resolve_roles(panel: dict, guild: discord.Guild | None) -> dict:
    """{role:Name} becomes a clickable role pill when the guild has that role, bold text
    otherwise. Done on the JSON text so it works anywhere in a panel, and embeds never ping."""
    def sub(m):
        role = discord.utils.get(guild.roles, name=m.group(1)) if guild else None
        return f"<@&{role.id}>" if role else f"**{m.group(1)}**"
    return json.loads(ROLE_TOKEN.sub(sub, json.dumps(panel)))


def panel_names() -> list[str]:
    return sorted(p.stem for p in PANEL_DIR.glob("*.json"))


def load_panel(name: str) -> dict | None:
    # whitelist by listing, never build a path from user input
    if name not in panel_names():
        return None
    return json.loads((PANEL_DIR / f"{name}.json").read_text(encoding="utf-8"))


class HubButton(discord.ui.DynamicItem[discord.ui.Button],
                template=r"jarcord:hub:(?P<name>[a-z0-9-]+)"):
    """A hub button. The page it opens is in the custom_id, so restarts forget nothing and
    any panel file is a page without registering anything. Replies are ephemeral."""

    def __init__(self, name: str, label: str = None, emoji: str = None):
        super().__init__(discord.ui.Button(
            label=label, emoji=emoji, style=discord.ButtonStyle.secondary,
            custom_id=f"jarcord:hub:{name}",
        ))
        self.name = name

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match, /):
        return cls(match["name"])

    async def callback(self, interaction: discord.Interaction):
        if self.name == CODE_PAGE:
            await interaction.response.send_message(code_text(interaction.user), ephemeral=True)
            return
        panel = load_panel(self.name)
        if panel is None:
            await interaction.response.send_message("That page is missing. Tell Command.", ephemeral=True)
            return
        await interaction.response.send_message(**send_kwargs(panel, interaction.guild), ephemeral=True)


def build(panel: dict, guild: discord.Guild = None) -> tuple[list[discord.Embed], discord.ui.View | None, list[discord.File]]:
    panel = resolve_roles(panel, guild)
    colour = discord.Colour(int(panel["colour"], 16)) if panel.get("colour") else ACCENT
    embeds, files = [], []

    if panel.get("banner"):
        head = discord.Embed(colour=colour)
        src = panel["banner"]
        if src.startswith("file:"):  # shipped in panels/assets, attached, nothing to host
            name = src[len("file:"):]
            files.append(discord.File(ASSET_DIR / name, filename=name))
            head.set_image(url=f"attachment://{name}")
        else:
            head.set_image(url=src)
        embeds.append(head)

    # Discord allows 10 embeds per message, and the banner eats one of them
    for section in panel.get("sections", [])[:10 - len(embeds)]:
        e = embed(title=section.get("title"), description=section.get("body"), colour=colour)
        for f in section.get("fields", [])[:25]:
            e.add_field(name=f["name"], value=f["value"], inline=f.get("inline", False))
        if section.get("thumbnail"):
            e.set_thumbnail(url=section["thumbnail"])
        if section.get("image"):
            e.set_image(url=section["image"])  # also forces the card to full width
        e.timestamp = None  # panels are reference posts, not events
        embeds.append(e)

    buttons = panel.get("buttons", [])[:25]
    view = None
    if buttons:
        view = discord.ui.View(timeout=None)
        for b in buttons:
            if b.get("url"):
                view.add_item(discord.ui.Button(
                    label=b["label"], url=b["url"], emoji=b.get("emoji"),
                    style=discord.ButtonStyle.link,
                ))
            else:
                view.add_item(HubButton(b["panel"], label=b["label"], emoji=b.get("emoji")))
    return embeds, view, files


def send_kwargs(panel: dict, guild: discord.Guild = None) -> dict:
    """Keyword arguments for send(), only the ones that apply. Files are single use, so
    this builds fresh ones every call."""
    embeds, view, files = build(panel, guild)
    kw = {"embeds": embeds}
    if view is not None:
        kw["view"] = view
    if files:
        kw["files"] = files
    return kw


class Panels(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_dynamic_items(HubButton)  # hub buttons survive restarts

    @commands.hybrid_command(name="panel", description="Post an info panel (needs Manage Messages)")
    @discord.app_commands.default_permissions(manage_messages=True)
    @staff_check(officer=True, manage_messages=True)
    async def panel(self, ctx: commands.Context, name: str):
        panel = load_panel(name)
        if panel is None:
            await ctx.send(f"No panel called `{name}`. Available: {', '.join(panel_names()) or 'none'}")
            return
        kw = send_kwargs(panel, ctx.guild)
        if not kw["embeds"]:
            await ctx.send(f"Panel `{name}` has no banner or sections.")
            return
        await ctx.send(**kw)

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
