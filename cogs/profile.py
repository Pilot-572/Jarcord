# ── Jarcord: member profiles (Roblox link + continent) cog ──
import asyncio
from typing import Literal, Optional

import aiohttp
import discord
from discord.ext import commands

from db import conn
from ui import ago, embed, is_officer, staff_check

CONTINENTS = ("Europe", "North America", "South America", "Asia", "Africa", "Oceania")
UNITS = ("Ground Unit", "Sniper Unit")
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


async def set_exclusive_role(member: discord.Member, chosen: str, family, create: bool = True) -> bool:
    """Give `chosen` and drop any other role from the same family. False if the bot
    can't manage roles, or the role doesn't exist and we were told not to create it."""
    try:
        role = discord.utils.get(member.guild.roles, name=chosen)
        if role is None:
            if not create:
                return False
            role = await member.guild.create_role(name=chosen, mentionable=True)
        old = [r for r in member.roles if r.name in family and r != role]
        if old:
            await member.remove_roles(*old)
        await member.add_roles(role)
        return True
    except discord.Forbidden:
        return False


async def set_continent(member: discord.Member, continent: str) -> bool:
    save_profile(member.id, continent=continent)
    return await set_exclusive_role(member, continent, CONTINENTS)


async def set_unit(member: discord.Member, unit: str) -> bool:
    save_profile(member.id, unit=unit)
    return await set_exclusive_role(member, unit, UNITS)


class RobloxDown(Exception):
    """The lookup itself failed. Not the same as a username that doesn't exist, and
    telling somebody to check their spelling during an outage sends them in circles."""


async def resolve_roblox(username: str):
    """Return (id, canonical_name), or None if the username doesn't exist.
    Raises RobloxDown when Roblox never answered."""
    timeout = aiohttp.ClientTimeout(total=8)  # ponytail: leaves room inside a modal defer
    last = None
    for attempt in (1, 2):  # one retry, Roblox blips for a second or two
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    ROBLOX_LOOKUP,
                    json={"usernames": [username], "excludeBannedUsers": True},
                ) as resp:
                    if resp.status == 429 or resp.status >= 500:
                        raise aiohttp.ClientError(f"roblox returned {resp.status}")
                    if resp.status != 200:
                        return None
                    data = (await resp.json()).get("data", [])
            return (data[0]["id"], data[0]["name"]) if data else None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last = e
            print(f">> roblox lookup attempt {attempt} failed: {e}")
            if attempt == 1:
                await asyncio.sleep(1)
    raise RobloxDown(str(last))


class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        return ctx.guild is not None  # nicknames/roles only exist in a guild

    @commands.hybrid_command(name="roblox", description="Link your Roblox account (sets your nickname)")
    async def roblox(self, ctx: commands.Context, username: str):
        try:
            found = await resolve_roblox(username)
        except RobloxDown:
            await ctx.send("Roblox isn't answering right now. Try again in a minute.")
            return
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
    @discord.app_commands.default_permissions(manage_nicknames=True)
    @staff_check(officer=True, manage_nicknames=True)
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

    @commands.hybrid_command(name="unit", description="Switch unit (swaps the role)")
    async def unit(self, ctx: commands.Context, unit: Literal["Ground Unit", "Sniper Unit"]):
        if await set_unit(ctx.author, unit):
            await ctx.send(f"You're in **{unit}** now.", ephemeral=True)
        else:
            await ctx.send(
                f"Saved **{unit}**, but I couldn't swap the role. Give me Manage Roles.", ephemeral=True
            )

    @commands.hybrid_command(name="profile", description="Member profile: Roblox, continent, ops, rating, activity")
    async def profile(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        member = member or ctx.author
        p = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (member.id,)).fetchone()
        act = conn.execute(
            "SELECT message_count, last_seen FROM activity WHERE user_id = ?", (member.id,)
        ).fetchone()
        turnout = conn.execute(
            """SELECT COUNT(*) AS signed, SUM(attended = 1) AS came, SUM(attended = 0) AS missed
               FROM signups WHERE user_id = ?""",
            (member.id,),
        ).fetchone()
        n_warnings = conn.execute(
            "SELECT COUNT(*) AS n FROM warnings WHERE user_id = ?", (member.id,)
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
        from cogs.ranks import current_rank  # lazy, ranks imports this module
        e.add_field(name="Rank", value=current_rank(member) or "*none yet*", inline=True)
        e.add_field(
            name="Unit",
            value=p["unit"] if p and p["unit"] else "*Not set*",
            inline=True,
        )
        e.add_field(
            name="Continent",
            value=p["continent"] if p and p["continent"] else "*Not set. Use /continent*",
            inline=True,
        )
        came, missed = turnout["came"] or 0, turnout["missed"] or 0
        e.add_field(
            name="Ops",
            value=(f"{turnout['signed']} signed up\n{came} attended, {missed} no-showed"
                   if turnout["signed"] else "none yet"),
            inline=True,
        )
        e.add_field(name="Warnings", value=str(n_warnings) if n_warnings else "none", inline=True)
        e.add_field(
            name="Rating",
            value=f"{rating['avg']:.2f}/5 ({rating['n']})" if rating["n"] else "n/a",
            inline=True,
        )
        e.add_field(name="Messages", value=str(act["message_count"]) if act else "0", inline=True)
        e.add_field(name="Last seen", value=ago(act["last_seen"]) if act else "Never", inline=True)
        # the extras include an age group, and 13-15 is a real answer. Yours, or staff only.
        if member == ctx.author or is_officer(ctx.author):
            for label, column in (("Usually online", "play_hours"), ("Age group", "age_group"),
                                  ("Found us via", "heard_from"), ("Experience", "experience")):
                if p and p[column]:
                    e.add_field(name=label, value=p[column], inline=False)
        await ctx.send(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Profile(bot))
