# ── Jarcord: tickets (a private channel per request, filed and transcripted on close) ──
import io
import re

import discord
from discord.ext import commands

from cogs.ranks import POSITIONS
from cogs.welcome import named
from db import conn, get_setting, set_setting
from ui import ACCENT, embed, is_officer, log_action, staff_check

PARA = discord.TextStyle.paragraph
CATEGORY_NAME = "TICKETS"
PANEL_CHANNEL = "🎫┃tickets"
LOG_CHANNEL = "📁┃ticket-logs"
HISTORY_LIMIT = 500  # ponytail: a ticket that runs past 500 messages is a channel, not a ticket
CLOSED = discord.Colour(0x64748B)

# Each kind is one button on the panel and one modal. Adding a kind is adding a dict entry:
# the button, the form, the channel name and the panel line all come from here.
KINDS = {
    "support": {
        "label": "Question or problem",
        "emoji": "❔",
        "slug": "help",
        "title": "Question for Command",
        "blurb": "Anything that needs a person. Access, a bug, something you cannot find.",
        "fields": [
            {"label": "What do you need?", "style": PARA, "max_length": 900,
             "placeholder": "the whole thing in one go, it saves a round trip"},
        ],
    },
    "loa": {
        "label": "Leave of absence",
        "emoji": "🌙",
        "slug": "loa",
        "title": "Leave of absence",
        "blurb": "Away for a while. Filed here, approved by Command, and your rank keeps.",
        "fields": [
            {"label": "Away from", "placeholder": "2 September", "max_length": 40},
            {"label": "Back on", "placeholder": "16 September, or not sure yet", "max_length": 40},
            {"label": "Reason", "style": PARA, "required": False, "max_length": 500,
             "placeholder": "as much or as little as you want to say"},
        ],
    },
    "position": {
        "label": "Apply for a position",
        "emoji": "🏅",
        "slug": "apply",
        "title": "Position application",
        "blurb": f"Open posts: {', '.join(POSITIONS)}. One ticket, Command answers in it.",
        "fields": [
            {"label": "Which position?", "max_length": 60,
             "placeholder": ", ".join(POSITIONS)},
            {"label": "Why you?", "style": PARA, "max_length": 700,
             "placeholder": "what you would actually do with it"},
            {"label": "Done anything like it before?", "style": PARA, "required": False,
             "max_length": 500, "placeholder": "other factions, other servers, real kit"},
        ],
    },
    "report": {
        "label": "Report a member",
        "emoji": "🚩",
        "slug": "report",
        "title": "Member report",
        "blurb": "Goes to Command only. The person you name never sees this channel.",
        "fields": [
            {"label": "Who?", "max_length": 60, "placeholder": "their name or Discord tag"},
            {"label": "What happened?", "style": PARA, "max_length": 900},
            {"label": "Evidence", "required": False, "max_length": 300,
             "placeholder": "link to a clip or a screenshot"},
        ],
    },
    "diplomacy": {
        "label": "Work with ROC",
        "emoji": "🤝",
        "slug": "dip",
        "title": "Working with ROC",
        "blurb": "Another group booking us for OPFOR, QRF, SAR or a joint op.",
        "fields": [
            {"label": "Which group do you speak for?", "max_length": 80},
            {"label": "Your role there", "max_length": 60,
             "placeholder": "Command, host, event lead"},
            {"label": "What are you after?", "style": PARA, "max_length": 700,
             "placeholder": "OPFOR, QRF, SAR, a joint op, a standing alliance"},
            {"label": "When?", "required": False, "max_length": 100,
             "placeholder": "date and start time, in your own timezone"},
        ],
    },
}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", text.casefold()).strip("-") or "member"


def open_ticket_row(user_id: int, kind: str):
    return conn.execute(
        "SELECT * FROM tickets WHERE user_id = ? AND kind = ? AND status = 'open'",
        (user_id, kind),
    ).fetchone()


def ticket_row(ticket_id: int):
    return conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()


def row_for_channel(channel_id: int):
    return conn.execute(
        "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'", (channel_id,)
    ).fetchone()


def support_role(guild: discord.Guild):
    role_id = get_setting("officer_role_id")
    return guild.get_role(int(role_id)) if role_id else None


def may_handle(member: discord.Member, row) -> bool:
    """Staff work every ticket. The person who opened it can read and close their own."""
    return is_officer(member) or member.id == row["user_id"]


async def ticket_category(guild: discord.Guild) -> discord.CategoryChannel | None:
    cid = get_setting("ticket_category_id")
    if cid:
        found = guild.get_channel(int(cid))
        if isinstance(found, discord.CategoryChannel):
            return found
    # ponytail: any category with "ticket" in the name, so a hand-made one counts
    found = discord.utils.find(lambda c: "ticket" in c.name.casefold(), guild.categories)
    if found is not None:
        set_setting("ticket_category_id", str(found.id))
    return found


def ticket_embed(kind: str, member: discord.Member, answers, ticket_id: int) -> discord.Embed:
    spec = KINDS[kind]
    e = embed(title=f"{spec['title']} · #{ticket_id:03d}", colour=ACCENT)
    e.set_author(name=str(member), icon_url=member.display_avatar.url)
    for label, value in answers:
        if value:
            e.add_field(name=label, value=value[:1024], inline=False)
    e.set_footer(text=f"user {member.id}")
    return e


async def open_ticket(guild: discord.Guild, member: discord.Member, kind: str,
                      answers, note: str = None) -> discord.TextChannel:
    """Cut a private channel, file the answers in it and pull staff in. Raises
    discord.Forbidden if the bot cannot make channels, and AlreadyOpen if there is
    already an open ticket of this kind, whose channel is returned on the exception."""
    existing = open_ticket_row(member.id, kind)
    if existing is not None:
        channel = guild.get_channel(existing["channel_id"] or 0)
        if channel is not None:
            raise AlreadyOpen(channel)
        # the channel was deleted by hand, so the row is stale
        conn.execute("UPDATE tickets SET status = 'closed' WHERE id = ?", (existing["id"],))
        conn.commit()

    # the answers live in the database too, so a ticket can be read without Discord
    filed = "\n".join(f"{label}: {value}" for label, value in answers if value)
    cur = conn.execute("INSERT INTO tickets (user_id, kind, answers) VALUES (?, ?, ?)",
                       (member.id, kind, filed))
    conn.commit()
    ticket_id = cur.lastrowid

    me = guild.me
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        me: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                        manage_channels=True, read_message_history=True),
        member: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                            read_message_history=True, attach_files=True,
                                            embed_links=True),
    }
    staff = support_role(guild)
    if staff is not None:
        overwrites[staff] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True,
            attach_files=True, embed_links=True)

    channel = await guild.create_text_channel(
        name=f"{KINDS[kind]['slug']}-{slugify(member.name)}"[:100],
        category=await ticket_category(guild),
        overwrites=overwrites,
        topic=f"Ticket #{ticket_id:03d} · {KINDS[kind]['title']} · opened by {member}",
        reason=f"ticket #{ticket_id} opened by {member}",
    )
    conn.execute("UPDATE tickets SET channel_id = ? WHERE id = ?", (channel.id, ticket_id))
    conn.commit()

    # ponytail: only the opener is pinged. Command gets the card in command-logs and the
    # channel in the sidebar, a role ping per ticket would wake everyone for everything.
    await channel.send(
        content=member.mention + (f"\n{note}" if note else ""),
        embed=ticket_embed(kind, member, answers, ticket_id),
        view=TicketControls(ticket_id),
        allowed_mentions=discord.AllowedMentions(users=True, roles=False),
    )
    print(f">> ticket #{ticket_id} ({kind}) opened by {member.id} in #{channel.name}")
    await log_action(guild, f"Ticket opened: {KINDS[kind]['title']}", member,
                     f"`#{ticket_id:03d}` in {channel.mention}")
    return channel


class AlreadyOpen(Exception):
    def __init__(self, channel):
        super().__init__(str(channel.id))
        self.channel = channel


async def transcript(channel: discord.TextChannel) -> str:
    """The whole channel as text. Attachments become links, since Discord keeps the file
    behind the URL long after the channel is gone."""
    lines = [f"# {channel.name} · {channel.topic or 'ticket'}", ""]
    async for m in channel.history(limit=HISTORY_LIMIT, oldest_first=True):
        stamp = m.created_at.strftime("%Y-%m-%d %H:%M")
        body = m.clean_content
        for e in m.embeds:
            parts = [e.title, e.description, *(f"{f.name}: {f.value}" for f in e.fields)]
            body += "\n  " + "\n  ".join(p for p in parts if p)
        for a in m.attachments:
            body += f"\n  [file] {a.filename} {a.url}"
        lines.append(f"[{stamp}] {m.author}: {body}")
    return "\n".join(lines)


async def close_ticket(channel: discord.TextChannel, closer: discord.Member,
                       reason: str = None) -> str | None:
    """File the transcript, tell the member, then delete the channel. Returns a problem
    to show the closer, or None. The channel is never deleted before the transcript lands."""
    row = row_for_channel(channel.id)
    if row is None:
        return "This isn't a ticket channel."

    log_id = get_setting("ticket_log_channel_id")
    log = channel.guild.get_channel(int(log_id)) if log_id else None
    if log is None:
        return ("No transcript channel is set, so closing this would lose it. "
                "Run `/tickets-setup` first.")

    spec = KINDS.get(row["kind"], {"title": row["kind"]})
    e = embed(title=f"Closed · {spec['title']} #{row['id']:03d}", colour=CLOSED)
    e.add_field(name="Opened by", value=f"<@{row['user_id']}>", inline=True)
    e.add_field(name="Closed by", value=closer.mention, inline=True)
    if row["claimed_by"]:
        e.add_field(name="Handled by", value=f"<@{row['claimed_by']}>", inline=True)
    if reason:
        e.add_field(name="Reason", value=reason[:1024], inline=False)
    text = await transcript(channel)
    try:
        await log.send(embed=e, file=discord.File(io.BytesIO(text.encode("utf-8")),
                                                  filename=f"{channel.name}.txt"))
    except discord.HTTPException as exc:
        print(f">> transcript for ticket {row['id']} failed: {exc!r}")
        return f"Couldn't file the transcript, so nothing was deleted: {exc.text or exc}"

    conn.execute(
        "UPDATE tickets SET status = 'closed', closed_at = datetime('now'), closed_by = ?, "
        "transcript = ? WHERE id = ?", (closer.id, text, row["id"]),
    )
    conn.commit()

    member = channel.guild.get_member(row["user_id"])
    if member is not None and member != closer:
        try:
            await member.send(
                f"Your **{spec['title'].lower()}** ticket in **{channel.guild.name}** is closed."
                + (f"\n{reason}" if reason else "")
            )
        except discord.HTTPException:
            pass  # closed DMs, the transcript is filed either way

    print(f">> ticket #{row['id']} closed by {closer.id}")
    await log_action(channel.guild, f"Ticket closed: {spec['title']}", closer,
                     f"`#{row['id']:03d}`" + (f"\n{reason}" if reason else ""))
    await channel.delete(reason=f"ticket #{row['id']} closed by {closer}")
    return None


# ── Buttons ──
class OpenButton(discord.ui.DynamicItem[discord.ui.Button],
                 template=r"jarcord:ticket:open:(?P<kind>[a-z]+)"):
    """One per kind on the standing panel. The kind rides in the custom_id, so a restart
    forgets nothing and there is no view to re-register per panel."""

    def __init__(self, kind: str):
        spec = KINDS[kind]
        super().__init__(discord.ui.Button(
            label=spec["label"], emoji=spec["emoji"], style=discord.ButtonStyle.secondary,
            custom_id=f"jarcord:ticket:open:{kind}",
        ))
        self.kind = kind

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(match["kind"])

    async def callback(self, interaction: discord.Interaction):
        if self.kind not in KINDS:
            await interaction.response.send_message("That ticket type is gone.", ephemeral=True)
            return
        await interaction.response.send_modal(TicketModal(self.kind))


class TicketModal(discord.ui.Modal):
    def __init__(self, kind: str):
        super().__init__(title=KINDS[kind]["title"][:45])
        self.kind = kind
        self.answers = []
        for spec in KINDS[kind]["fields"]:
            item = discord.ui.TextInput(**spec)
            self.add_item(item)
            self.answers.append(item)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        answers = [(i.label, str(i).strip()) for i in self.answers]
        try:
            channel = await open_ticket(interaction.guild, interaction.user, self.kind, answers)
        except AlreadyOpen as open_already:
            await interaction.followup.send(
                f"You already have one open: {open_already.channel.mention}. "
                "Use that one, or close it first.", ephemeral=True)
            return
        except discord.Forbidden:
            await interaction.followup.send(
                "I can't make channels here. Command needs to give me **Manage Channels**.",
                ephemeral=True)
            return
        await interaction.followup.send(f"Opened {channel.mention}.", ephemeral=True)


class ClaimButton(discord.ui.DynamicItem[discord.ui.Button],
                  template=r"jarcord:ticket:claim:(?P<id>\d+)"):
    def __init__(self, ticket_id: int):
        super().__init__(discord.ui.Button(
            label="Claim", emoji="✋", style=discord.ButtonStyle.primary,
            custom_id=f"jarcord:ticket:claim:{ticket_id}",
        ))
        self.ticket_id = ticket_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["id"]))

    async def callback(self, interaction: discord.Interaction):
        if not is_officer(interaction.user):
            await interaction.response.send_message("Command claims tickets.", ephemeral=True)
            return
        row = ticket_row(self.ticket_id)
        if row is None:
            await interaction.response.send_message("That ticket is gone.", ephemeral=True)
            return
        if row["claimed_by"]:
            await interaction.response.send_message(
                f"<@{row['claimed_by']}> already has this one.", ephemeral=True)
            return
        conn.execute("UPDATE tickets SET claimed_by = ? WHERE id = ?",
                     (interaction.user.id, self.ticket_id))
        conn.commit()
        e = interaction.message.embeds[0]
        e.add_field(name="Handled by", value=interaction.user.mention, inline=False)
        await interaction.response.edit_message(embed=e)
        await interaction.followup.send(f"{interaction.user.mention} has this one.")


class CloseButton(discord.ui.DynamicItem[discord.ui.Button],
                  template=r"jarcord:ticket:close:(?P<id>\d+)"):
    def __init__(self, ticket_id: int):
        super().__init__(discord.ui.Button(
            label="Close", emoji="🔒", style=discord.ButtonStyle.danger,
            custom_id=f"jarcord:ticket:close:{ticket_id}",
        ))
        self.ticket_id = ticket_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):
        return cls(int(match["id"]))

    async def callback(self, interaction: discord.Interaction):
        row = ticket_row(self.ticket_id)
        if row is None or row["status"] != "open":
            await interaction.response.send_message("That ticket is already closed.", ephemeral=True)
            return
        if not may_handle(interaction.user, row):
            await interaction.response.send_message("Not your ticket.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Closing files a transcript and deletes this channel. Sure?",
            view=ConfirmClose(), ephemeral=True)


class ConfirmClose(discord.ui.View):
    """Short lived and ephemeral, so no persistence and no custom_id."""

    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Close it", style=discord.ButtonStyle.danger)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Filing the transcript.", view=None)
        problem = await close_ticket(interaction.channel, interaction.user)
        if problem:
            await interaction.edit_original_response(content=problem)


class TicketControls(discord.ui.View):
    def __init__(self, ticket_id: int):
        super().__init__(timeout=None)
        self.add_item(ClaimButton(ticket_id))
        self.add_item(CloseButton(ticket_id))


def panel_message(guild: discord.Guild) -> tuple[discord.Embed, discord.ui.View]:
    e = embed(
        title="OPEN A TICKET",
        colour=ACCENT,
        description=(
            "Pick what this is about. You get a private channel that only you and "
            "**Command** can read, and it stays open until it is sorted.\n\n"
            "──────────────────────────────"
        ),
    )
    for spec in KINDS.values():
        e.add_field(name=f"{spec['emoji']} {spec['label']}", value=spec["blurb"], inline=False)
    e.set_footer(text="Every closed ticket is kept as a transcript")
    if guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    e.timestamp = None
    view = discord.ui.View(timeout=None)
    for kind in KINDS:
        view.add_item(OpenButton(kind))
    return e, view


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_dynamic_items(OpenButton, ClaimButton, CloseButton)

    async def cog_check(self, ctx) -> bool:
        return ctx.guild is not None

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Somebody left with a ticket open. Say so in it rather than closing it, because
        the answer in there is often still wanted."""
        rows = conn.execute(
            "SELECT * FROM tickets WHERE user_id = ? AND status = 'open'", (member.id,)
        ).fetchall()
        for row in rows:
            channel = member.guild.get_channel(row["channel_id"] or 0)
            if channel is not None:
                await channel.send(f"**{member}** left the server. Close this when you are done with it.")

    @commands.hybrid_command(name="tickets-setup",
                             description="Set up tickets: your channels, or new ones if you leave them out")
    @discord.app_commands.describe(
        panel="Where the ticket panel goes, anything everyone can read",
        logs="Where transcripts are filed, keep it Command only",
        category="Where opened ticket channels land, any category will do")
    @discord.app_commands.default_permissions(manage_guild=True)
    @staff_check(manage_guild=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def tickets_setup(self, ctx: commands.Context, panel: discord.TextChannel = None,
                            logs: discord.TextChannel = None,
                            category: discord.CategoryChannel = None):
        await ctx.defer(ephemeral=True)
        guild, staff, made = ctx.guild, support_role(ctx.guild), []
        command_logs = guild.get_channel(int(get_setting("log_channel_id") or 0))
        info = named(guild, "information") or guild.get_channel(int(get_setting("op_channel_id") or 0))

        # A ticket category, yours or one passed in, holds everything: the panel, the
        # transcripts and every opened ticket. Without one, the panel goes next to the
        # information hub, transcripts next to command-logs, and opened tickets under Command.
        category = category or await ticket_category(guild)
        dedicated = category is not None
        if category is None and command_logs is not None:
            category = command_logs.category
        if category is None:
            category = await guild.create_category(
                CATEGORY_NAME,
                overwrites={guild.default_role: discord.PermissionOverwrite(view_channel=False)},
                reason="ticket system")
            made.append(category.name)
            dedicated = True
        set_setting("ticket_category_id", str(category.id))

        def inherit(home, **everyone):
            """A new channel does not pick up its category's overwrites on its own, so copy
            them and adjust the @everyone line. Explicit overwrites beat category sync."""
            overwrites = dict(home.overwrites) if home is not None else {}
            line = overwrites.get(guild.default_role, discord.PermissionOverwrite())
            line.update(**everyone)
            overwrites[guild.default_role] = line
            return overwrites

        panel = panel or guild.get_channel(int(get_setting("ticket_panel_channel_id") or 0))
        if panel is None:
            if dedicated:  # a ticket category is usually hidden, and the panel must not be
                home, overwrites = category, inherit(category, view_channel=True, send_messages=False)
            else:
                home = info.category if info is not None else category
                overwrites = inherit(home, send_messages=False)
            panel = await guild.create_text_channel(
                PANEL_CHANNEL, category=home, overwrites=overwrites, reason="ticket panel")
            made.append(panel.name)
        set_setting("ticket_panel_channel_id", str(panel.id))

        log = logs or guild.get_channel(int(get_setting("ticket_log_channel_id") or 0))
        if log is None:
            home = category if dedicated or command_logs is None else command_logs.category
            overwrites = inherit(home, view_channel=False)  # Command only, wherever it sits
            if staff is not None:
                overwrites[staff] = discord.PermissionOverwrite(view_channel=True,
                                                                read_message_history=True)
            log = await guild.create_text_channel(LOG_CHANNEL, category=home,
                                                  overwrites=overwrites, reason="ticket transcripts")
            made.append(log.name)
        set_setting("ticket_log_channel_id", str(log.id))

        e, view = panel_message(guild)
        await panel.send(embed=e, view=view)
        print(f">> ticket system set up in guild {guild.id}, created {made or 'nothing new'}")
        await log_action(guild, "Ticket system set up", ctx.author,
                         f"Panel in {panel.mention}, transcripts in {log.mention}")
        note = f"Created {', '.join(made)}." if made else "Everything already existed."
        if staff is None:
            note += " No officer role is set, so only admins can read tickets. Run `/officer-role`."
        await ctx.send(f"{note} Panel is up in {panel.mention}.", ephemeral=True)

    @commands.hybrid_command(name="tickets-panel", description="Post the ticket panel again")
    @discord.app_commands.default_permissions(manage_guild=True)
    @staff_check(officer=True, manage_guild=True)
    async def tickets_panel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        target = channel or ctx.channel
        e, view = panel_message(ctx.guild)
        try:
            await target.send(embed=e, view=view)
        except discord.Forbidden:
            await ctx.send(f"I can't post in {target.mention}.", ephemeral=True)
            return
        set_setting("ticket_panel_channel_id", str(target.id))
        if ctx.interaction:
            await ctx.send(f"Panel posted in {target.mention}.", ephemeral=True)

    @commands.hybrid_command(name="ticket-add", description="Pull someone into this ticket")
    @discord.app_commands.default_permissions(manage_messages=True)
    @staff_check(officer=True, manage_messages=True)
    async def ticket_add(self, ctx: commands.Context, member: discord.Member):
        if row_for_channel(ctx.channel.id) is None:
            await ctx.send("Run this inside a ticket channel.", ephemeral=True)
            return
        await ctx.channel.set_permissions(member, view_channel=True, send_messages=True,
                                          read_message_history=True, attach_files=True)
        await ctx.send(f"{member.mention} is in.")

    @commands.hybrid_command(name="ticket-close", description="Close this ticket and file it")
    async def ticket_close(self, ctx: commands.Context, *, reason: str = None):
        row = row_for_channel(ctx.channel.id)
        if row is None:
            await ctx.send("Run this inside an open ticket channel.", ephemeral=True)
            return
        if not may_handle(ctx.author, row):
            await ctx.send("Not your ticket.", ephemeral=True)
            return
        problem = await close_ticket(ctx.channel, ctx.author, reason)
        if problem:
            await ctx.send(problem, ephemeral=True)

    @commands.hybrid_command(name="tickets", description="Open tickets, or one member's history")
    @discord.app_commands.default_permissions(manage_messages=True)
    @staff_check(officer=True, manage_messages=True)
    async def tickets(self, ctx: commands.Context, member: discord.Member = None):
        if member is None:
            rows = conn.execute(
                "SELECT * FROM tickets WHERE status = 'open' ORDER BY id").fetchall()
            title = f"{len(rows)} open ticket{'s' if len(rows) != 1 else ''}"
        else:
            rows = conn.execute(
                "SELECT * FROM tickets WHERE user_id = ? ORDER BY id DESC LIMIT 15",
                (member.id,)).fetchall()
            title = f"{member.display_name}: {len(rows)} ticket{'s' if len(rows) != 1 else ''}"

        e = embed(title=title, colour=ACCENT)
        for r in rows[:25]:
            spec = KINDS.get(r["kind"], {"title": r["kind"]})
            where = f"<#{r['channel_id']}>" if r["status"] == "open" else "closed"
            e.add_field(name=f"#{r['id']:03d} {spec['title']}",
                        value=f"<@{r['user_id']}> · {where}", inline=False)
        if not rows:
            e.description = "Nothing open."
        await ctx.send(embed=e, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
