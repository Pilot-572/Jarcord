# ── Jarcord: shared embed styling + user-facing error text ──
import io
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from db import get_setting

# ── Field Order accent strips ──
# Four states, each clearing 3:1 on both Discord themes. The steel palette these
# replaced sat at 1.9 to 2.6:1 on light theme, so half the readers saw nothing.
# Colour never carries state on its own: a Nitro theme flattens every strip to
# grey, so the state is always a word in the first line as well.
OLIVE = discord.Colour(0x8C8F5B)    # reference, and normal business
COYOTE = discord.Colour(0xA07A4A)   # needs attention
RED = discord.Colour(0xD64545)      # wrong, or done to a person
NEUTRAL = discord.Colour(0x7F8288)  # finished, archived, logged

ACCENT = OLIVE      # ops, profiles, panels, welcome, verification
RATING = OLIVE      # a rating is reference, not a sanction
ACTIVITY = NEUTRAL  # the audit log records things already done


def ago(text: str) -> str:
    """Stored timestamps are UTC. Render them as Discord markup so every reader sees
    their own local time instead of having to do the conversion."""
    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return text
    return f"<t:{int(dt.timestamp())}:R>"


def embed(title: str = None, description: str = None,
          colour: discord.Colour = ACCENT) -> discord.Embed:
    return discord.Embed(
        title=title, description=description, colour=colour,
        timestamp=discord.utils.utcnow(),
    )


def log_channel(guild, setting: str = "log_channel_id"):
    """The channel a log goes to, or None when nothing is configured or the channel is gone."""
    if guild is None:
        return None
    channel_id = get_setting(setting)
    if not channel_id:
        return None
    return guild.get_channel(int(channel_id))


async def log_action(guild, action: str, actor=None, detail: str = None) -> None:
    """Write one line to the log channel, if /logs-setup named one. Never raises:
    a logging failure must not take the command that triggered it down."""
    channel = log_channel(guild)
    if channel is None:
        return
    e = embed(title=action, description=detail, colour=ACTIVITY)
    if actor is not None:
        e.set_author(name=str(actor), icon_url=actor.display_avatar.url)
        e.set_footer(text=f"user {actor.id}")
    try:
        await channel.send(embed=e)
    except discord.HTTPException as exc:
        print(f">> couldn't log to channel {channel.id}: {exc!r}")


def one_line(pairs) -> str:
    """Command arguments flattened to one line. Each value is cut at 120 characters: the
    log records what a command was asked for, it is not a second copy of what was typed."""
    parts = []
    for name, value in pairs:
        if value is None or value == "":
            continue
        parts.append(f"**{name}** {str(value)[:120]}")
    return " · ".join(parts).replace("\n", " ")


async def log_command(guild, name: str, actor, channel, args: str, outcome: str = "") -> None:
    """One line per command run, refused and failed ones included. The cogs log what a
    command did; this logs that it was asked for, by who, where, and with what."""
    where = channel.mention if channel is not None else "a direct message"
    detail = f"in {where}"
    if args:
        detail += f"\n{args}"
    await log_action(guild, name + outcome, actor, detail)


def deleted_line(message) -> str:
    """One deleted message as text. Same shape as a ticket transcript, plus the author id,
    because this file is read when somebody is arguing about who said what."""
    stamp = message.created_at.strftime("%Y-%m-%d %H:%M")
    body = message.clean_content
    for e in message.embeds:
        parts = [e.title, e.description, *(f"{f.name}: {f.value}" for f in e.fields)]
        body += "\n  " + "\n  ".join(p for p in parts if p)
    for a in message.attachments:
        body += f"\n  [file] {a.filename} {a.url}"
    return f"[{stamp}] {message.author} ({message.author.id}): {body}"


async def log_deleted(guild, messages, channel) -> None:
    """Deleted messages, in the channel /deleted-setup named. One embed for one message,
    an embed plus a text file for a bulk delete, because eighty embeds is a rate limit.

    Cached messages only. Discord hands the bot an id and nothing else for a message it
    never saw, so anything posted before Jarcord last started is deleted without a trace.
    ponytail: discord.py caches 1000 messages by default, which is weeks at this server's
    rate. Raise max_messages in bot.py if a restart ever loses something that mattered."""
    log = log_channel(guild, "deleted_log_channel_id")
    if log is None or not messages or log.id == channel.id:
        return                      # deleting a log line must not write another log line
    messages = sorted(messages, key=lambda m: m.id)
    first = messages[0]
    file = None

    if len(messages) == 1:
        e = embed(title="Message deleted",
                  description=first.clean_content[:4000] or "(no text)", colour=RED)
        e.add_field(name="Channel", value=channel.mention, inline=True)
        e.add_field(name="Sent", value=ago(first.created_at.strftime("%Y-%m-%d %H:%M:%S")),
                    inline=True)
        if first.attachments:
            e.add_field(name="Files", inline=False, value="\n".join(
                f"[{a.filename}]({a.url})" for a in first.attachments)[:1024])
        e.set_author(name=str(first.author), icon_url=first.author.display_avatar.url)
        e.set_footer(text=f"user {first.author.id} · message {first.id}")
    else:
        e = embed(title=f"{len(messages)} messages deleted",
                  description=f"in {channel.mention}", colour=RED)
        e.set_footer(text=f"channel {channel.id}")
        text = "\n".join(deleted_line(m) for m in messages)
        # the channel name carries emoji, so the file is named after the id instead
        file = discord.File(io.BytesIO(text.encode("utf-8")),
                            filename=f"deleted-{channel.id}.txt")

    try:
        if file is None:
            await log.send(embed=e)
        else:
            await log.send(embed=e, file=file)
    except discord.HTTPException as exc:
        print(f">> couldn't log a deletion to channel {log.id}: {exc!r}")


def _allowed(member, perms, officer: bool, roles=()) -> bool:
    """Admins always pass. So does anyone holding the named Discord permissions. The role
    set with /officer-role passes only on commands marked officer=True, and any role named
    in `roles` passes for that command alone (a position, like Op Planner on /op)."""
    mine = member.guild_permissions
    if mine.administrator or (perms and all(getattr(mine, p, False) for p in perms)):
        return True
    if officer:
        role_id = get_setting("officer_role_id")
        if role_id and any(r.id == int(role_id) for r in member.roles):
            return True
    return bool(roles) and any(r.name in roles for r in member.roles)


def is_officer(member, roles=()) -> bool:
    """Manage Server, or the configured officer role. For runtime branching, not gating."""
    return _allowed(member, {"manage_guild": True}, officer=True, roles=roles)


def staff_check(*, officer: bool = False, roles=(), **perms):
    """Gate for prefix and hybrid commands."""
    async def predicate(ctx) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        if _allowed(ctx.author, perms, officer, roles):
            return True
        raise commands.MissingPermissions(list(perms))
    return commands.check(predicate)


def app_staff_check(*, officer: bool = False, roles=(), **perms):
    """Same gate for slash-only commands."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            raise app_commands.NoPrivateMessage()
        if _allowed(interaction.user, perms, officer, roles):
            return True
        raise app_commands.MissingPermissions(list(perms))
    return app_commands.check(predicate)


def check_message(error) -> str | None:
    """Friendly text for permission/check failures, or None if not one."""
    if isinstance(error, (commands.MissingPermissions, app_commands.MissingPermissions)):
        return "You don't have permission to use that."
    if isinstance(error, (commands.BotMissingPermissions, app_commands.BotMissingPermissions)):
        missing = ", ".join(error.missing_permissions)
        return f"I'm missing the **{missing}** permission. Add it in Server Settings → Roles."
    if isinstance(error, commands.CommandOnCooldown):
        return f"Give it {error.retry_after:.0f} seconds and try again."
    if isinstance(error, (commands.CheckFailure, app_commands.CheckFailure)):
        return "That command can't be used here."
    return None


# ── The clerk ──
# What Jarcord says when a member command is pointed at the bot itself. One line, third
# person, because paperwork does not say "I". Keys are command names.
CLERK = {
    "promote": "Jarcord holds no rank. It keeps the ladder.",
    "demote": "There is nothing below clerk.",
    "warn": "Noted. Jarcord files warnings, it does not collect them.",
    "warns": "No warnings. Jarcord writes them, it does not receive them.",
    "rate": "Jarcord is not rated. Ratings go the other way.",
    "rating-history": "No ratings. Jarcord keeps the scores, it does not get one.",
    "activity": "Jarcord does not count its own messages. Point /profile at it for what it does count.",
    "record": "The clerk has no record card. It writes the others.",
    "nudge": "Nothing to nudge. Jarcord verified itself.",
    "ticket-add": "Jarcord is already in every ticket.",
    "tickets": "Jarcord has never opened a ticket. It files them.",
    "continent": "Hack Club Nest is not a continent, but that is where Jarcord lives.",
    "unit": "Jarcord is posted to every unit.",
}


def is_me(member) -> bool:
    """True when a member argument is the bot itself."""
    guild = getattr(member, "guild", None)
    me = getattr(guild, "me", None)
    return me is not None and member.id == me.id


def clerk(command: str) -> str:
    return CLERK[command]
