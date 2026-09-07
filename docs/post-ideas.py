"""Post the ideas board through Jarcord, from the command line.

Does what `/ideas` does, for when nobody is at a keyboard in Discord to run it.

    venv/bin/python docs/post-ideas.py                       # dry run, changes nothing
    venv/bin/python docs/post-ideas.py --category <id>       # dry run, in that category
    venv/bin/python docs/post-ideas.py --category <id> --ping <member id> --post

Dry run is the default and prints exactly what a real run would do. Nothing is
created, posted or pinged without --post. Reads the token the way the bot does
and never prints it.
"""

import argparse
import asyncio
import sys
import traceback
import json
import os
from pathlib import Path

import discord
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from cogs.panels import load_panel, send_kwargs  # noqa: E402

ROOT = Path(__file__).parent.parent
VOTES = ("👍", "👎")

ap = argparse.ArgumentParser()
ap.add_argument("--board", default="ideas", help="which <board>.json to post")
ap.add_argument("--panel", help="post this panels/<name>.json instead of a board")
ap.add_argument("--allow-role", type=int, action="append", default=[],
                help="role id that may also see the new channel, repeatable")
ap.add_argument("--name", default="ideas", help="channel to create")
ap.add_argument("--into", type=int, help="post into this existing channel instead")
ap.add_argument("--edit", action="store_true",
                help="with --into, edit my last message there rather than adding one")
ap.add_argument("--category", type=int, help="category id to create it in")
ap.add_argument("--ping", type=int, help="member id to tag underneath")
ap.add_argument("--post", action="store_true", help="actually do it")
args = ap.parse_args()

load_dotenv(ROOT / ".env")
data = None if args.panel else json.loads(
    (ROOT / f"{args.board}.json").read_text(encoding="utf-8"))

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)


def card(idea: dict) -> discord.Embed:
    e = discord.Embed(title=idea["title"], description=idea["body"],
                      colour=discord.Colour(0x6B7B5E))
    if idea.get("tag"):
        e.set_footer(text=idea["tag"])
    return e


@client.event
async def on_ready():
    try:
        guild = client.get_guild(int(os.environ["GUILD_ID"]))
        print(f">> guild: {guild.name}, {guild.member_count} members")
        if args.panel:
            if load_panel(args.panel) is None:
                print(f"!! no panel called {args.panel}")
                return
            print(f">> panel: {args.panel}")
        else:
            print(f">> board: {args.board}, {len(data['ideas'])} ideas")

        if args.category is None:
            print(">> categories, pick one with --category <id>:")
            for c in guild.categories:
                print(f"     {c.id}  {c.name}  ({len(c.channels)} channels)")
        category = guild.get_channel(args.category) if args.category else None
        if args.category and not isinstance(category, discord.CategoryChannel):
            print(f"!! {args.category} is not a category in this server")
            return

        into = guild.get_channel(args.into) if args.into else None
        if args.into and not isinstance(into, discord.TextChannel):
            print(f"!! {args.into} is not a text channel here")
            return
        clash = None if into else discord.utils.get(guild.text_channels, name=args.name)
        if clash:
            print(f"!! #{clash.name} already exists ({clash.id}). "
                  f"Delete it or pass a different --name.")
            return

        member = guild.get_member(args.ping) if args.ping else None
        if args.ping and member is None:
            print(f"!! no member {args.ping} in this server")
            return
        if args.ping:
            print(f">> ping: {member.display_name} ({member.name}), "
                  f"roles {[r.name for r in member.roles if r.name != '@everyone']}")
            # a ping in a channel they cannot open is a ping they never see
            if category:
                seen = category.permissions_for(member).view_channel
                print(f">> can {member.display_name} see {category.name}? {seen}")
        else:
            print(">> ping: nobody. Candidates whose name looks like Amazon:")
            for m in guild.members:
                if "amazon" in f"{m.name}{m.nick or ''}{m.display_name}".lower():
                    print(f"     {m.id}  {m.display_name} ({m.name})")

        where = category.name if category else "no category, top of the list"
        extra = [guild.get_role(r) for r in args.allow_role]
        if any(r is None for r in extra):
            print("!! one of --allow-role is not a role in this server")
            return
        if into:
            print(f">> would {'edit my last message in' if args.edit else 'post into'} "
                  f"#{into.name}")
        else:
            print(f">> would create #{args.name} in {where}")
        for r in extra:
            print(f">> would let {r.name} ({len(r.members)} members) see it")
        if args.panel:
            print(f">> would post the {args.panel} panel, one message")
        else:
            count = len(data["ideas"])
            print(f">> would post 1 header + {count} ideas"
                  + (" + 1 ping" if member else "")
                  + f", and add {len(VOTES)} reactions to each idea")

        if not args.post:
            print(">> dry run, nothing done. Add --post to go.")
            return

        if into:
            channel = into
        else:
            channel = await (category or guild).create_text_channel(
                args.name, reason="Ideas board")
            print(f">> created #{channel.name} ({channel.id})")
        for r in extra:
            await channel.set_permissions(
                r, view_channel=True, send_messages=True, add_reactions=True,
                read_message_history=True, reason="Ideas board")
            print(f">> {r.name} can now see #{channel.name}")

        if args.panel:
            kw = send_kwargs(load_panel(args.panel), guild)
            if args.edit:
                mine = [m async for m in channel.history(limit=30)
                        if m.author.id == client.user.id]
                if not mine:
                    print("!! nothing of mine to edit in there")
                    return
                kw["attachments"] = kw.pop("files", [])
                await mine[0].edit(**kw)
                print(f">> edited my message {mine[0].id} in #{channel.name}")
            else:
                await channel.send(**kw)
                print(f">> posted the {args.panel} panel")
            print(f">> done, #{channel.name}")
            return

        count = len(data["ideas"])
        await channel.send(embed=discord.Embed(
            title=data["title"], description=data["intro"],
            colour=discord.Colour(0x6B7B5E)))
        for i, idea in enumerate(data["ideas"], 1):
            msg = await channel.send(embed=card(idea))
            for vote in VOTES:
                await msg.add_reaction(vote)
            print(f"   {i}/{count} {idea['title']}")
        if member:
            await channel.send(
                data["ping_note"].format(mention=member.mention),
                allowed_mentions=discord.AllowedMentions(users=[member]))
            print(f">> pinged {member.display_name}")
        print(f">> done, #{channel.name}")
    except Exception:
        traceback.print_exc()
    finally:
        await client.close()


client.run(os.environ["DISCORD_TOKEN"], log_handler=None)
