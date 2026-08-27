# ── Jarcord: member profiles (Roblox link + continent) cog ──
from typing import Literal, Optional

import aiohttp
import discord
from discord.ext import commands

from db import conn
from ui import embed

CONTINENTS = ("Europe", "North America", "South America", "Asia", "Africa", "Oceania")
ROBLOX_LOOKUP = "https://users.roblox.com/v1/usernames/users"


def save_profile(user_id: int, **fields) -> None:
    """Upsert whichever profile columns were passed. Column names are code literals,
    never user input, so building the statement from them is safe."""
    cols = ", ".join(fields)
    marks = ", ".join("?" * len(fields))
    sets = ", ".join(f"{c} = ?" for c in fields)
    values = list(fields.values())
    conn.execute(
        f"INSERT INTO profiles (user_id, {cols}) VALUES (?, {marks}) "
        f"ON CONFLICT(user_id) DO UPDATE SET {sets}",
        [user_id] + values + values,
    )
    conn.commit()


async def set_continent(member: discord.Member, continent: str) -> bool:
    """Store the continent and swap the role. False if the bot can't manage roles."""
    save_profile(member.id, continent=continent)
    try:
        role = discord.utils.get(member.guild.roles, name=continent)
        if role is None:
            role = await member.guild.create_role(name=continent, mentionable=True)
        old = [r for r in member.roles if r.name in CONTINENTS and r != role]
        if old:
            await member.remove_roles(*old)
        await member.add_roles(role)
        return True
    except discord.Forbidden:
        return False


async def resolve_roblox(username: str):
    """Return (id, canonical_name) or None if the username doesn't exist."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            ROBLOX_LOOKUP,
            json={"usernames": [username], "excludeBannedUsers": True},
        ) as resp:
            if resp.status != 200:
                return None
            data = (await resp.json()).get("data", [])
    if not data:
        return None
    return data[0]["id"], data[0]["name"]


class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        return ctx.guild is not None  # nicknames/roles only exist in a guild

    @commands.hybrid_command(name="roblox", description="Link your Roblox account (sets your nickname)")
    async def roblox(self, ctx: commands.Context, username: str):
        found = await resolve_roblox(username)
        if found is None:
            await ctx.send(f"No Roblox account called **{username}**. Check the spelling.")
            return
        rid, name = found
        conn.execute(
            """INSERT INTO profiles (user_id, roblox_name, roblox_id) VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET roblox_name = ?, roblox_id = ?""",
            (ctx.author.id, name, rid, name, rid),
        )
        conn.commit()
        msg = f"Linked to Roblox account **{name}** (`{rid}`)."
        try:
            await ctx.author.edit(nick=name)
            msg += f" Nickname set to **{name}**."
        except discord.Forbidden:
            msg += " Couldn't change your nickname (server owner, or I'm missing Manage Nicknames)."
        await ctx.send(msg)

    @commands.hybrid_command(
        name="nickname", aliases=["nick"],
        description="Set someone's nickname (needs Manage Nicknames)",
    )
    @commands.has_permissions(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    async def nickname(self, ctx: commands.Context, member: discord.Member, *, nickname: str = None):
        try:
            await member.edit(nick=nickname)
        except discord.Forbidden:
            await ctx.send(
                f"Can't rename {member.mention}. They're the server owner, or their top role "
                "sits above mine (Server Settings → Roles → drag Jarcord higher)."
            )
            return
        if nickname:
            await ctx.send(f"Renamed {member.mention} to **{nickname}**.")
        else:
            await ctx.send(f"Cleared {member.mention}'s nickname.")

    @commands.hybrid_command(name="continent", description="Set your continent (assigns the role)")
    async def continent(
        self,
        ctx: commands.Context,
        continent: Literal["Europe", "North America", "South America", "Asia", "Africa", "Oceania"],
    ):
        if await set_continent(ctx.author, continent):
            await ctx.send(f"You're set to **{continent}**. Role assigned.")
        else:
            await ctx.send(
                f"Saved **{continent}**, but I couldn't manage roles. Give me the Manage Roles permission."
            )

    @commands.hybrid_command(name="profile", description="Member profile: Roblox, continent, ops, rating, activity")
    async def profile(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        p = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (member.id,)).fetchone()
        act = conn.execute(
            "SELECT message_count, last_seen FROM activity WHERE user_id = ?", (member.id,)
        ).fetchone()
        n_ops = conn.execute(
            "SELECT COUNT(*) AS n FROM signups WHERE user_id = ?", (member.id,)
        ).fetchone()["n"]
        rating = conn.execute(
            "SELECT AVG(score) AS avg, COUNT(*) AS n FROM ratings WHERE user_id = ?", (member.id,)
        ).fetchone()

        e = embed(title=member.display_name)
        e.set_thumbnail(url=member.display_avatar.url)
        roblox = (
            f"[{p['roblox_name']}](https://www.roblox.com/users/{p['roblox_id']}/profile)"
            if p and p["roblox_name"] else "*Not linked. Use /roblox*"
        )
        e.add_field(name="Roblox", value=roblox, inline=True)
        e.add_field(
            name="Continent",
            value=p["continent"] if p and p["continent"] else "*Not set. Use /continent*",
            inline=True,
        )
        e.add_field(name="Ops attended", value=str(n_ops), inline=True)
        e.add_field(
            name="Rating",
            value=f"{rating['avg']:.2f}/5 ({rating['n']})" if rating["n"] else "n/a",
            inline=True,
        )
        e.add_field(name="Messages", value=str(act["message_count"]) if act else "0", inline=True)
        e.add_field(name="Last seen", value=f"{act['last_seen']} UTC" if act else "Never", inline=True)
        for label, column in (("Usually plays", "play_hours"), ("Age group", "age_group"),
                              ("Found us via", "heard_from"), ("Experience", "experience")):
            if p and p[column]:
                e.add_field(name=label, value=p[column], inline=False)
        await ctx.send(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Profile(bot))
