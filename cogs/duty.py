# ── Jarcord: duty rota, recurring posts, and the daily chore list ──
# The point of this cog is that the faction keeps running on a week when the owner
# never opens Discord. Three parts:
#   1. recurring posts, so the recruitment advert goes out on its own
#   2. a duty rota, so exactly one named person is responsible each day
#   3. a chore list derived from live state, so nobody can tick a box that isn't true
# When the chores are still open hours later it escalates: next person in the rota,
# then the server owner. Nothing here needs the owner present.
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from cogs.ops import NUDGE_WINDOW
from cogs.verify import UNVERIFIED
from db import conn, get_setting, set_setting
from ui import COYOTE, NEUTRAL, OLIVE, RED, embed, is_officer, log_action, staff_check

DEFAULT_TZ = "Europe/Bucharest"
CHORE_HOUR = 12 * 60          # the "12h mark": minutes past local midnight
ESCALATE_AFTER = 4 * 3600     # nudge the next person in the rota
OWNER_AFTER = 8 * 3600        # then the server owner, once
STALE_TICKET = 12 * 3600      # an unclaimed ticket this old is a chore
CLOSE_GRACE = 2 * 3600        # an op this long past its start should have been closed


# ── Pure schedule maths (tested in test_duty.py) ──
def next_run(now_ts: int, at_minute: int, every_min: int, tzname: str = DEFAULT_TZ) -> int:
    """The next unix ts strictly after now_ts on this cadence, in local wall-clock terms.

    at_minute is minutes past local midnight for the first slot of the day; every_min is
    the gap between slots. Daily at noon is (720, 1440); twice a day is (720, 720).
    ponytail: wall-clock arithmetic, so a slot can land an hour early or late on the two
    DST changeovers a year. Anchor on UTC instead if that ever matters.
    """
    tz = ZoneInfo(tzname)
    now = datetime.fromtimestamp(now_ts, tz)
    every_min = max(int(every_min), 1)
    # start a day back, so a cadence whose slots straddle midnight is not missed
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    slot = midnight + timedelta(minutes=at_minute)
    for _ in range(2 * 1440 // every_min + 3):
        if slot.timestamp() > now_ts:
            return int(slot.timestamp())
        slot += timedelta(minutes=every_min)
    return int(slot.timestamp())


def todays_slot(now_ts: int, at_minute: int, tzname: str = DEFAULT_TZ) -> int:
    """Today's slot in local time, whether it has passed yet or not.

    Deliberately not next_run(): the chore list needs "has today's noon happened", and
    asking next_run for the slot after yesterday returns yesterday's, which fires the
    list just after midnight instead of at noon.
    """
    tz = ZoneInfo(tzname)
    midnight = datetime.fromtimestamp(now_ts, tz).replace(
        hour=0, minute=0, second=0, microsecond=0)
    return int((midnight + timedelta(minutes=at_minute)).timestamp())


def on_duty(rota: list[int], today: date, epoch: date, rotate_days: int = 1) -> int | None:
    """Whose turn it is, derived from the date rather than stored.

    Deriving it means the rota cannot drift out of step after downtime, and nothing has
    to be written when the day rolls over.
    """
    if not rota:
        return None
    turns = (today - epoch).days // max(rotate_days, 1)
    return rota[turns % len(rota)]


def chore_lines(advert_due: bool, ops_ahead: int, needs_closing: int,
                stale_tickets: int, unverified: int) -> list[tuple[str, bool, str]]:
    """(key, done, sentence) per chore, in the order they should be read.

    Pure, so the wording and the done/not-done rules are testable without a database.
    Each sentence says what to do, never just what is wrong.
    """
    return [
        ("advert", not advert_due,
         "Post the advert" if advert_due else "Advert posted"),
        ("ops", ops_ahead > 0,
         f"{ops_ahead} op{'s' if ops_ahead != 1 else ''} on the board"
         if ops_ahead else "Nothing on the board. Schedule one with /op create"),
        ("close", needs_closing == 0,
         "Every op is closed out" if not needs_closing
         else f"{needs_closing} op{'s' if needs_closing != 1 else ''} started and never closed. "
              "Record who turned up with /op close"),
        ("tickets", stale_tickets == 0,
         "No ticket waiting" if not stale_tickets
         else f"{stale_tickets} ticket{'s' if stale_tickets != 1 else ''} unclaimed for over 12 hours"),
        ("verify", unverified == 0,
         "Everyone is verified" if not unverified
         else f"{unverified} member{'s' if unverified != 1 else ''} never linked an account"),
    ]


# ── Settings-backed rota (no table: it is a short list of ids) ──
def rota_ids() -> list[int]:
    raw = get_setting("duty_rota") or ""
    return [int(part) for part in raw.split(",") if part.strip().isdigit()]


def rota_epoch() -> date:
    raw = get_setting("duty_epoch")
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError):
        return date(2026, 1, 1)


def tzname() -> str:
    return get_setting("duty_tz") or DEFAULT_TZ


def local_today() -> date:
    return datetime.now(ZoneInfo(tzname())).date()


# ── Live state behind the chore list ──
def chore_state(guild: discord.Guild) -> dict:
    now = int(time.time())
    advert = conn.execute("SELECT * FROM posts WHERE name = 'advert'").fetchone()
    # last_run is cleared when a send fails, so NULL means the last attempt did not
    # go out, or nothing has gone out yet
    advert_due = bool(advert and advert["enabled"] and not advert["last_run"])
    stale = conn.execute(
        "SELECT channel_id FROM tickets WHERE status = 'open' AND claimed_by IS NULL "
        "AND opened_at < datetime('now', ?)",
        (f"-{STALE_TICKET} seconds",),
    ).fetchall()
    return {
        "advert_due": advert_due,
        "ops_ahead": conn.execute(
            "SELECT COUNT(*) FROM ops WHERE closed = 0 AND when_ts IS NOT NULL AND when_ts > ?",
            (now,),
        ).fetchone()[0],
        # bounded below: an op nobody closed months ago is history, same rule as ops.py
        "needs_closing": conn.execute(
            "SELECT COUNT(*) FROM ops WHERE closed = 0 AND when_ts IS NOT NULL "
            "AND when_ts < ? AND when_ts > ?",
            (now - CLOSE_GRACE, now - NUDGE_WINDOW),
        ).fetchone()[0],
        # a ticket whose channel is gone cannot be claimed, so it is not a chore
        "stale_tickets": sum(1 for r in stale if guild.get_channel(r["channel_id"] or 0)),
        # the role, not the profiles table: a row with no roblox_id can belong to
        # somebody who left, a guest, or a member who never went through the modal
        "unverified": sum(1 for m in guild.members
                          if not m.bot and any(r.name == UNVERIFIED for r in m.roles)),
    }


def chore_card(guild: discord.Guild, holder_id: int | None) -> tuple[discord.Embed, int]:
    """The card, and how many chores are still open."""
    chores = chore_lines(**chore_state(guild))
    open_count = sum(1 for _, done, _ in chores if not done)
    body = "\n".join(("~~" + text + "~~" if done else "**" + text + "**")
                     for _, done, text in chores)
    if open_count:
        colour = RED if open_count > 2 else COYOTE
        title = f"{open_count} thing{'s' if open_count != 1 else ''} to do today"
    else:
        colour, title = OLIVE, "Nothing outstanding today"
    e = embed(title=title, description=body, colour=colour)
    holder = guild.get_member(holder_id) if holder_id else None
    e.set_author(name=f"On duty: {holder.display_name}" if holder else "On duty: nobody set")
    e.set_footer(text="Ticks itself when the work is done. Nobody has to mark anything.")
    return e, open_count


class Snooze(discord.ui.View):
    """One button, so a legitimate quiet day does not wake the whole chain of command."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Nothing needed today", style=discord.ButtonStyle.secondary,
                       custom_id="jarcord:duty:snooze")
    async def snooze(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (is_officer(interaction.user) or interaction.user.id in rota_ids()):
            await interaction.response.send_message(
                "Only whoever is on the rota, or an officer, can hold the list.",
                ephemeral=True)
            return
        set_setting("duty_escalated", f"{local_today().isoformat()}:99")
        await interaction.response.send_message(
            "Held for today. Nobody else gets pinged about it.", ephemeral=True)
        print(f">> duty snoozed by {interaction.user.id}")


class Duty(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx) -> bool:
        return ctx.guild is not None

    async def cog_load(self):
        self.bot.add_view(Snooze())
        self.duty_loop.start()

    def cog_unload(self):
        self.duty_loop.cancel()

    # ── The one loop ──
    @tasks.loop(minutes=1)
    async def duty_loop(self):
        await self.run_due_posts()
        await self.run_chores()

    @duty_loop.before_loop
    async def before_duty_loop(self):
        await self.bot.wait_until_ready()

    async def run_due_posts(self):
        """Recurring posts. Mark before sending, same as the op reminders: a post that
        fails is skipped rather than retried every minute forever."""
        now = int(time.time())
        due = conn.execute(
            "SELECT * FROM posts WHERE enabled = 1 AND next_ts IS NOT NULL AND next_ts <= ?",
            (now,),
        ).fetchall()
        for post in due:
            conn.execute(
                "UPDATE posts SET last_run = datetime('now'), next_ts = ? WHERE name = ?",
                (next_run(now, post["at_minute"] or 0, post["every_min"], tzname()), post["name"]),
            )
            conn.commit()
            if not await self.send_post(post):
                conn.execute("UPDATE posts SET last_run = NULL WHERE name = ?", (post["name"],))
                conn.commit()

    async def send_post(self, post) -> bool:
        channel = self.bot.get_channel(post["channel_id"] or 0)
        if channel is None:
            print(f">> post '{post['name']}' has no reachable channel, skipped")
            return False
        try:
            await channel.send(post["body"])
            print(f">> posted '{post['name']}' to #{channel.name}")
            return True
        except discord.HTTPException as exc:
            print(f">> post '{post['name']}' failed: {exc!r}")
            return False

    async def run_chores(self):
        """Post the chore list once a day at the configured hour, then escalate while it
        is still open. Every decision is derived from the clock and from live state, so a
        restart mid-day picks up exactly where it left off."""
        rota = rota_ids()
        channel_id = get_setting("duty_channel_id")
        if not channel_id:
            return
        channel = self.bot.get_channel(int(channel_id))
        if channel is None or channel.guild is None:
            return

        today = local_today()
        now = int(time.time())
        hour = int(get_setting("duty_hour") or CHORE_HOUR)
        due_ts = todays_slot(now, hour, tzname())
        if now < due_ts:
            return  # today's slot has not come round yet

        holder = on_duty(rota, today, rota_epoch(),
                         int(get_setting("duty_rotate_days") or 1))
        posted_day = get_setting("duty_posted")
        stamp = get_setting("duty_escalated") or ""
        day_part, _, count_part = stamp.partition(":")
        escalated = int(count_part) if day_part == today.isoformat() and count_part.isdigit() else 0

        if posted_day != today.isoformat():
            e, open_count = chore_card(channel.guild, holder)
            mention = f"<@{holder}>" if holder else None
            try:
                await channel.send(content=mention, embed=e, view=Snooze(),
                                   allowed_mentions=discord.AllowedMentions(users=True))
                set_setting("duty_posted", today.isoformat())
                set_setting("duty_posted_ts", str(now))
                set_setting("duty_escalated", f"{today.isoformat()}:0")
                print(f">> chore list posted, {open_count} open, on duty {holder}")
            except discord.HTTPException as exc:
                print(f">> chore list failed: {exc!r}")
            return

        # already posted today, so this is the escalation path
        if escalated >= 2:
            return
        _, open_count = chore_card(channel.guild, holder)
        if open_count == 0:
            return
        elapsed = now - int(get_setting("duty_posted_ts") or due_ts)
        if escalated == 0 and elapsed >= ESCALATE_AFTER and len(rota) > 1:
            nxt = on_duty(rota, today, rota_epoch(),
                          int(get_setting("duty_rotate_days") or 1))
            backup = rota[(rota.index(nxt) + 1) % len(rota)] if nxt in rota else rota[0]
            await self.nudge(channel, backup,
                             f"{open_count} thing{'s' if open_count != 1 else ''} still open "
                             f"four hours after the list went up. Covering for today?")
            set_setting("duty_escalated", f"{today.isoformat()}:1")
        elif escalated <= 1 and elapsed >= OWNER_AFTER:
            await self.nudge(channel, channel.guild.owner_id,
                             f"{open_count} thing{'s' if open_count != 1 else ''} still open "
                             "eight hours on, and the rota has not picked it up.")
            set_setting("duty_escalated", f"{today.isoformat()}:2")

    async def nudge(self, channel, user_id: int, text: str) -> None:
        e = embed(title="Still outstanding", description=text, colour=RED)
        e.set_footer(text="Run /duty today to see the list.")
        try:
            await channel.send(content=f"<@{user_id}>", embed=e,
                               allowed_mentions=discord.AllowedMentions(users=True))
            print(f">> escalated to {user_id}")
        except discord.HTTPException as exc:
            print(f">> escalation failed: {exc!r}")

    # ── /duty ──
    @commands.hybrid_group(name="duty", description="Who is on duty, and what is left to do")
    async def duty(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await self.today(ctx)

    @duty.command(name="today", description="Today's chore list")
    async def today(self, ctx: commands.Context):
        holder = on_duty(rota_ids(), local_today(), rota_epoch(),
                         int(get_setting("duty_rotate_days") or 1))
        e, _ = chore_card(ctx.guild, holder)
        await ctx.send(embed=e, ephemeral=True)

    @duty.command(name="rota", description="Set the rotation, in order")
    @staff_check(officer=True, manage_guild=True)
    @app_commands.describe(members="The people who take a turn, in rotation order",
                           rotate_days="Days each person holds duty. 1 by default",
                           channel="Where the daily list is posted")
    async def rota(self, ctx: commands.Context, members: commands.Greedy[discord.Member],
                   rotate_days: int = 1, channel: discord.TextChannel = None):
        if not members:
            ids = rota_ids()
            names = ", ".join(f"<@{i}>" for i in ids) or "nobody yet"
            await ctx.send(f"Rota: {names}", ephemeral=True,
                           allowed_mentions=discord.AllowedMentions.none())
            return
        set_setting("duty_rota", ",".join(str(m.id) for m in members))
        set_setting("duty_epoch", local_today().isoformat())
        set_setting("duty_rotate_days", str(max(rotate_days, 1)))
        if channel is not None:
            set_setting("duty_channel_id", str(channel.id))
        holder = on_duty([m.id for m in members], local_today(), local_today(), rotate_days)
        where = get_setting("duty_channel_id")
        await ctx.send(
            f"Rota set, {len(members)} people, {max(rotate_days, 1)} day"
            f"{'s' if rotate_days != 1 else ''} each. <@{holder}> has it today."
            + (f" The list posts in <#{where}>." if where
               else " Name a channel with /duty rota so the list has somewhere to go."),
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        await log_action(ctx.guild, "Duty rota set", ctx.author,
                        f"{len(members)} people, {max(rotate_days, 1)} day(s) each")

    # ── /advert ──
    # A check on a hybrid group only gates its prefix form. The slash subcommands run
    # their own checks and nothing else, so each one carries the gate itself.
    @commands.hybrid_group(name="advert", description="The recruitment post that goes out on its own")
    @staff_check(officer=True, manage_guild=True)
    async def advert(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await self.advert_show(ctx)

    @advert.command(name="show", description="What is set, and when it next goes out")
    @staff_check(officer=True, manage_guild=True)
    async def advert_show(self, ctx: commands.Context):
        row = conn.execute("SELECT * FROM posts WHERE name = 'advert'").fetchone()
        if row is None:
            await ctx.send("No advert set. Write one with /advert set.", ephemeral=True)
            return
        when = f"<t:{row['next_ts']}:F> (<t:{row['next_ts']}:R>)" if row["next_ts"] else "not scheduled"
        e = embed(
            title="Advert" if row["enabled"] else "Advert, switched off",
            description=row["body"][:3900],
            colour=OLIVE if row["enabled"] else NEUTRAL,
        )
        e.add_field(name="Goes to", value=f"<#{row['channel_id']}>" if row["channel_id"] else "nowhere yet")
        e.add_field(name="Next", value=when)
        e.add_field(name="Every", value=f"{row['every_min'] // 60} hours", inline=False)
        await ctx.send(embed=e, ephemeral=True)

    @advert.command(name="set", description="Write the advert and schedule it")
    @staff_check(officer=True, manage_guild=True)
    @app_commands.describe(channel="Where it goes", body="The post itself",
                           hour="Local hour to post, 0 to 23. 12 by default",
                           every_hours="Hours between posts. 24 by default")
    async def advert_set(self, ctx: commands.Context, channel: discord.TextChannel,
                         body: str, hour: int = 12, every_hours: int = 24):
        if not 0 <= hour <= 23:
            await ctx.send("The hour has to be 0 to 23.", ephemeral=True)
            return
        if len(body) > 2000:
            await ctx.send(f"That is {len(body)} characters and a message holds 2000. "
                           "Trim it and set it again.", ephemeral=True)
            return
        if not 1 <= every_hours <= 168:
            await ctx.send("Post it somewhere between every hour and once a week.", ephemeral=True)
            return
        at_minute, every_min = hour * 60, every_hours * 60
        nxt = next_run(int(time.time()), at_minute, every_min, tzname())
        conn.execute(
            "INSERT INTO posts (name, channel_id, body, every_min, at_minute, enabled, next_ts) "
            "VALUES ('advert', ?, ?, ?, ?, 1, ?) "
            "ON CONFLICT(name) DO UPDATE SET channel_id = ?, body = ?, every_min = ?, "
            "at_minute = ?, enabled = 1, next_ts = ?",
            (channel.id, body, every_min, at_minute, nxt,
             channel.id, body, every_min, at_minute, nxt),
        )
        conn.commit()
        await ctx.send(
            f"Advert set for <#{channel.id}>, every {every_hours} hours at {hour:02d}:00 "
            f"{tzname()}. First one <t:{nxt}:R>.",
            ephemeral=True)
        await log_action(ctx.guild, "Advert scheduled", ctx.author,
                        f"#{channel.name}, every {every_hours}h at {hour:02d}:00")

    @advert.command(name="now", description="Post it immediately, without changing the schedule")
    @staff_check(officer=True, manage_guild=True)
    async def advert_now(self, ctx: commands.Context):
        row = conn.execute("SELECT * FROM posts WHERE name = 'advert'").fetchone()
        if row is None:
            await ctx.send("No advert set. Write one with /advert set.", ephemeral=True)
            return
        await ctx.defer(ephemeral=True)
        if await self.send_post(row):
            conn.execute("UPDATE posts SET last_run = datetime('now') WHERE name = ?",
                         (row["name"],))
            conn.commit()
            await ctx.send(f"Posted in <#{row['channel_id']}>.", ephemeral=True)
        else:
            await ctx.send(
                "That didn't post. Check Jarcord can send messages in "
                f"<#{row['channel_id']}>.", ephemeral=True)

    @advert.command(name="off", description="Stop posting it")
    @staff_check(officer=True, manage_guild=True)
    async def advert_off(self, ctx: commands.Context):
        changed = conn.execute(
            "UPDATE posts SET enabled = 0, next_ts = NULL WHERE name = 'advert'").rowcount
        conn.commit()
        await ctx.send("Advert switched off. /advert set turns it back on."
                       if changed else "There was no advert set.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Duty(bot))
