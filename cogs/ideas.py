# ── Jarcord: the ideas board, one message per idea so Command argues with them one at a time ──
import json
from pathlib import Path

import discord
from discord.ext import commands

from ui import embed, log_action, staff_check

ROOT = Path(__file__).parent.parent
VOTES = ("👍", "👎")
# Discord's own limits, the only reason the loader validates anything
TITLE_MAX, BODY_MAX, FOOTER_MAX = 256, 4096, 2048


def board_names() -> list[str]:
    return sorted(p.stem for p in ROOT.glob("*ideas.json"))


def load_ideas(board: str = "ideas") -> dict:
    # whitelist by listing, never build a path from user input
    if board not in board_names():
        raise KeyError(board)
    return json.loads((ROOT / f"{board}.json").read_text(encoding="utf-8"))


def problems(data: dict) -> list[str]:
    """Everything wrong with the file, so a typo is caught before half a channel is posted."""
    out = []
    if not data.get("title"):
        out.append("no title")
    if len(data.get("intro", "")) > BODY_MAX:
        out.append("intro too long")
    if len(data.get("ping_note", "")) > BODY_MAX:
        out.append("ping note too long")
    ideas = data.get("ideas") or []
    if not ideas:
        out.append("no ideas")
    for i, idea in enumerate(ideas, 1):
        where = idea.get("title") or f"idea {i}"
        if not idea.get("title"):
            out.append(f"{where}: no title")
        if not idea.get("body"):
            out.append(f"{where}: no body")
        if len(idea.get("title", "")) > TITLE_MAX:
            out.append(f"{where}: title over {TITLE_MAX}")
        if len(idea.get("body", "")) > BODY_MAX:
            out.append(f"{where}: body over {BODY_MAX}")
        if len(idea.get("tag", "")) > FOOTER_MAX:
            out.append(f"{where}: tag over {FOOTER_MAX}")
    return out


def idea_embed(idea: dict) -> discord.Embed:
    e = embed(title=idea["title"], description=idea["body"])
    if idea.get("tag"):
        e.set_footer(text=idea["tag"])
    e.timestamp = None      # a board is a reference post, not an event
    return e


class Ideas(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="ideas",
        description="Post the ideas board, one message per idea (needs Manage Messages)")
    @discord.app_commands.describe(
        board="Which board to post. Defaults to ideas",
        channel="Where to post. Defaults to here",
        new_channel="Make a channel with this name first, in the same category as here",
        ping="Tag this member underneath, using the note in the board file")
    @discord.app_commands.default_permissions(manage_messages=True)
    @staff_check(officer=True, manage_messages=True)
    async def ideas(self, ctx: commands.Context, board: str = "ideas",
                    channel: discord.TextChannel = None,
                    new_channel: str = None, ping: discord.Member = None):
        try:
            data = load_ideas(board)
        except KeyError:
            await ctx.send(f"No board called `{board}`. Available: "
                           + ", ".join(f"`{b}`" for b in board_names()))
            return
        except (OSError, json.JSONDecodeError) as exc:
            await ctx.send(f"`{board}.json` will not load: {exc}")
            return
        wrong = problems(data)
        if wrong:
            await ctx.send(f"`{board}.json` has problems:\n"
                           + "\n".join(f"- {w}" for w in wrong[:10]))
            return
        if ping and not data.get("ping_note"):
            await ctx.send(f"`{board}.json` has no `ping_note`, so there is nothing to tag them with.")
            return

        await ctx.defer()
        if new_channel:
            if not ctx.guild.me.guild_permissions.manage_channels:
                await ctx.send("I need Manage Channels to make a channel.")
                return
            # the category the command was run in, so the new channel inherits its permissions
            where = ctx.channel.category or ctx.guild
            target = await where.create_text_channel(
                new_channel, reason=f"Ideas board, asked for by {ctx.author}")
        else:
            target = channel or ctx.channel

        mine = target.permissions_for(ctx.guild.me)
        if not (mine.send_messages and mine.embed_links and mine.add_reactions):
            await ctx.send(
                f"I need Send Messages, Embed Links and Add Reactions in {target.mention}.")
            return

        head = embed(title=data["title"], description=data.get("intro"))
        head.timestamp = None
        await target.send(embed=head)
        for idea in data["ideas"]:
            msg = await target.send(embed=idea_embed(idea))
            for vote in VOTES:
                await msg.add_reaction(vote)
        if ping:
            await target.send(
                data["ping_note"].format(mention=ping.mention),
                allowed_mentions=discord.AllowedMentions(users=[ping]))

        count = len(data["ideas"])
        await log_action(ctx.guild, "Ideas posted", ctx.author,
                         f"{board}: {count} in #{target.name}")
        await ctx.send(f"Posted {count} ideas in {target.mention}. React to vote on them.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Ideas(bot))
