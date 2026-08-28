# ── Jarcord: rank ladder (/promote, /demote, /ranks-setup) ──
import discord
from discord.ext import commands

from cogs.profile import save_profile, set_exclusive_role
from db import conn, get_setting, set_setting
from ui import ACCENT, embed, staff_check

# Lowest to highest. These are the Discord role names, so renaming here renames the ladder.
RANKS = (
    "Private 1", "Private 2", "Private 3",
    "Specialist 1", "Specialist 2",
    "Corporal 1", "Corporal 2",
    "Sergeant", "Staff Sergeant",
)
ABBREV = ("PVT1", "PVT2", "PVT3", "SPC1", "SPC2", "CPL1", "CPL2", "SGT", "SSG")
NCO = "NCO"  # marker role, held from Corporal 1 up, so a channel needs one permission line
NCO_FROM = RANKS.index("Corporal 1")
# Jobs, not ranks. /ranks-setup creates them, Command hands them out by hand.
POSITIONS = ("Media", "Op Planner", "JTAC", "Server Host")

PROMOTED = discord.Colour(0x22C55E)
DEMOTED = discord.Colour(0xF59E0B)


# ── Ladder helpers (pure, tested in test_ranks.py) ──
def step(rank: str | None, up: bool) -> str | None:
    """The next rank in that direction, or None at the end of the ladder.
    No rank counts as one below Private 1, so a first promotion lands there."""
    i = RANKS.index(rank) if rank in RANKS else -1
    j = i + 1 if up else i - 1
    return RANKS[j] if 0 <= j < len(RANKS) else None


def is_nco(rank: str | None) -> bool:
    return rank in RANKS and RANKS.index(rank) >= NCO_FROM


def current_rank(member: discord.Member) -> str | None:
    """The database first. Failing that, the highest rank role they actually hold, so a
    rank handed out by hand in Discord is stepped from rather than stripped."""
    row = conn.execute("SELECT rank FROM profiles WHERE user_id = ?", (member.id,)).fetchone()
    if row and row["rank"] in RANKS:
        return row["rank"]
    held = [r.name for r in member.roles if r.name in RANKS]
    return max(held, key=RANKS.index) if held else None


# ── Discord side ──
async def apply_rank(member: discord.Member, rank: str) -> bool:
    """Record the rank, swap the rank role, keep the NCO marker right. False if the bot
    could not touch roles; the database is still updated so /profile stays honest."""
    save_profile(member.id, rank=rank)
    if not await set_exclusive_role(member, rank, RANKS):
        return False
    try:
        marker = discord.utils.get(member.guild.roles, name=NCO)
        if marker is None:
            marker = await member.guild.create_role(name=NCO, reason="Jarcord rank ladder")
        if is_nco(rank) and marker not in member.roles:
            await member.add_roles(marker, reason=f"rank {rank}")
        elif not is_nco(rank) and marker in member.roles:
            await member.remove_roles(marker, reason=f"rank {rank}")
    except discord.Forbidden:
        return False
    return True


def rank_card(member: discord.Member, old: str | None, new: str, officer: discord.Member,
              reason: str | None, up: bool) -> discord.Embed:
    e = embed(
        title=f"{member.display_name}: {'promoted' if up else 'demoted'} to {new}",
        colour=PROMOTED if up else DEMOTED,
    )
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="From", value=old or "no rank", inline=True)
    e.add_field(name="To", value=new, inline=True)
    e.add_field(name="By", value=officer.mention, inline=True)
    if reason:
        e.add_field(name="Reason", value=reason, inline=False)
    return e


class Ranks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx) -> bool:
        return ctx.guild is not None

    async def _move(self, ctx: commands.Context, member: discord.Member, reason: str | None, up: bool):
        if member.bot:
            await ctx.send("Bots don't hold rank.", ephemeral=True)
            return
        await ctx.defer(ephemeral=True)  # up to eight REST calls follow, the 3 s window is not enough
        old = current_rank(member)
        new = step(old, up)
        if new is None:
            where = "top" if up else "bottom"
            await ctx.send(f"{member.mention} is already at the {where} of the ladder.", ephemeral=True)
            return

        notes = []
        if not await apply_rank(member, new):
            notes.append("I couldn't change their roles, check Manage Roles and that my role "
                         "sits above the rank roles")

        verb = "promoted" if up else "moved down"
        try:
            await member.send(
                f"You've been {verb} to **{new}** in **{ctx.guild.name}**."
                + (f"\n{reason}" if reason else "")
            )
        except discord.HTTPException:
            notes.append("their DMs are closed, so tell them yourself")

        channel_id = get_setting("records_channel_id")
        if channel_id:
            channel = ctx.guild.get_channel(int(channel_id))
            if channel is not None:
                try:
                    await channel.send(embed=rank_card(member, old, new, ctx.author, reason, up))
                except discord.Forbidden:
                    notes.append(f"couldn't file it in #{channel.name}")

        # the public one carries no reason, that stays on the record
        channel_id = get_setting("promotions_channel_id")
        if channel_id:
            channel = ctx.guild.get_channel(int(channel_id))
            if channel is not None:
                try:
                    await channel.send(
                        content=member.mention,
                        embed=rank_card(member, old, new, ctx.author, None, up),
                        allowed_mentions=discord.AllowedMentions(users=True),
                    )
                except discord.Forbidden:
                    notes.append(f"couldn't post it in #{channel.name}")

        print(f">> {member.id} {verb} {old} -> {new} by {ctx.author.id}")
        msg = f"{member.mention} is now **{new}**."
        if notes:
            msg += " Note: " + "; ".join(notes) + "."
        await ctx.send(msg, ephemeral=True)

    @commands.hybrid_command(name="promote", description="Move a member one rank up the ladder")
    @discord.app_commands.default_permissions(manage_roles=True)
    @staff_check(officer=True, manage_roles=True)
    async def promote(self, ctx: commands.Context, member: discord.Member, *, reason: str = None):
        await self._move(ctx, member, reason, up=True)

    @commands.hybrid_command(name="demote", description="Move a member one rank down the ladder")
    @discord.app_commands.default_permissions(manage_roles=True)
    @staff_check(officer=True, manage_roles=True)
    async def demote(self, ctx: commands.Context, member: discord.Member, *, reason: str = None):
        await self._move(ctx, member, reason, up=False)

    @commands.hybrid_command(name="promotions-setup", description="Channel where every promotion and demotion is announced")
    @discord.app_commands.default_permissions(manage_guild=True)
    @commands.has_permissions(manage_guild=True)
    async def promotions_setup(self, ctx: commands.Context, channel: discord.TextChannel):
        set_setting("promotions_channel_id", str(channel.id))
        await ctx.send(f"Promotions and demotions will be announced in {channel.mention}.", ephemeral=True)

    @commands.hybrid_command(name="ranks-setup", description="Create the rank roles and put every verified member with no rank on Private 1")
    @discord.app_commands.default_permissions(manage_guild=True)
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def ranks_setup(self, ctx: commands.Context):
        from cogs.verify import OPERATOR  # lazy, verify imports this module
        await ctx.defer(ephemeral=True)  # fifteen role creations on a fresh server, well past 3 s

        # A new role lands at the bottom of the list, so on a fresh server creating the ladder
        # top down leaves it in order. Anything created earlier by verify sits wherever it was.
        wanted = [*POSITIONS, NCO, *reversed(RANKS)]
        have = {r.name for r in ctx.guild.roles}
        made = []
        for name in wanted:
            if name not in have:
                await ctx.guild.create_role(name=name, reason="Jarcord /ranks-setup")
                made.append(name)

        # members verified before the ladder existed have no rank, start them at the bottom
        started = 0
        operator = discord.utils.get(ctx.guild.roles, name=OPERATOR)
        for m in (operator.members if operator else []):
            if not m.bot and current_rank(m) is None and await apply_rank(m, RANKS[0]):
                started += 1

        e = embed(title="Rank roles", colour=ACCENT)
        e.add_field(name=f"Created ({len(made)})", value=", ".join(made) or "*nothing, all present*", inline=False)
        e.add_field(name="Started on Private 1", value=str(started), inline=False)
        e.add_field(name="Ladder, top to bottom", value="\n".join(
            f"`{a}` {r}" for a, r in zip(reversed(ABBREV), reversed(RANKS))
        ), inline=False)
        e.set_footer(text="Check the order in Server Settings, Roles, and keep Jarcord's role above all of these")
        await ctx.send(embed=e, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Ranks(bot))
