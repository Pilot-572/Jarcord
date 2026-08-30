# Jarcord

Scheduled op signups, member performance ratings and activity tracking for a Discord faction or milsim server, all inside the server itself. It stays small on purpose: Discord's built-in AutoMod handles moderation, so Jarcord doesn't.

Informational output goes in embeds with one accent colour; confirmations stay short and inline.

## Features

### Op signups (RSVP)
| Command | What it does |
|---|---|
| `/op create <what> <when> [who] [notes]` | Post an op card with RSVP buttons |
| `/op join <id>` or `!op join <id>` | Sign up without the buttons |
| `/op leave <id>` or `!op leave <id>` | Drop off the roster |
| `/op edit <id> [what] [when] [notes]` | Change an op. Rescheduling re-arms the reminder (creator or officer) |
| `/op close <id>` | Record who actually turned up, then close the op |
| `/op cancel <id>` or `!op cancel <id>` | Cancel an op and remove its card (creator or officer) |
| `/op roster <id>` or `!op roster <id>` | Who's attending |
| `/op list` or `!op list` | Last 10 ops with attendance counts |
| `/op-setup <channel> [ping_role]` | Where ops get posted and who gets pinged (needs Manage Server) |

Closing an op is how attendance gets recorded. The member picker opens with everyone marked Attending already ticked, so the host unticks the no-shows and ticks the walk-ins; anyone who said they were coming and isn't picked is logged as a no-show, and anyone who walked in without replying still counts as attending. A closed card shows the turnout and loses its buttons, and the op thread gets the turnout, a line for anyone hitting their first, fifth, tenth or twenty-fifth op, and a nudge to `/rate`, then archives. An hour after a timed op starts, the host gets pinged in the thread to close it. `/profile` then reports signed up, attended and no-showed instead of a signup count that means nothing.

The card carries **Attending**, **Maybe** and **Can't make it**. Pressing one rewrites the card in place, so the three lists are always current, and changing your mind moves you rather than adding you twice. Attending also adds you to the op thread. The 30 minute reminder pings everyone Attending, and gives Maybe a last call. The buttons survive restarts. Cancelling deletes the card and its thread.

`when` is free text, but if it matches `YYYY-MM-DD HH:MM` or `DD.MM HH:MM` (UTC), the op gets a real timestamp, shown in each viewer's local timezone, and the bot pings the roster in the op's channel 30 minutes before start.

### Member ratings
| Command | What it does |
|---|---|
| `/rate @member <1-5> [note]` or `!rate ...` | Rate someone's op performance |
| `/rating-history @member` | Average score + last 5 notes |

### Member profiles
| Command | What it does |
|---|---|
| `/roblox <username>` | Link your Roblox account, verified against the Roblox API, then sets your server nickname to it |
| `/continent <continent>` | Set your continent; assigns the matching role (created on first use) |
| `/profile [@member]` | Full card: Roblox link, continent, ops attended, average rating, messages, last seen |
| `/nickname @member [nickname]` | Rename a member (needs Manage Nicknames); omit the nickname to clear it |

Needs **Manage Nicknames** and **Manage Roles**, and Jarcord's role must sit above the members and continent roles it manages.

### Verification
New members land restricted. On join they get the **Unverified** role and a prompt in the arrival channel. Pressing **Verify** walks them through a short private flow. Step one asks for their Roblox username, checked against the Roblox API, and what people call them in-game, which becomes their nickname. Step two is their unit (Ground Unit or Sniper Unit) and continent, both of which assign the matching role, plus optional time blocks for when they play. Then they either finish or answer three optional questions (how they found the server, age group, previous experience). Verifying swaps **Unverified** for **Operator** and puts them on **Private 1**, the bottom of the rank ladder (a rejoin gets their old rank back). Nothing is ever typed in chat.

Roles are matched by exact name and created only if missing, and existing ones are never modified. Channel visibility is yours to configure with category overwrites; Jarcord only manages the access roles and the rank ladder, so it needs **Manage Roles** with its own role above all of them. Members who rejoin already holding **Operator** skip the flow. The confirm button is persistent and idempotent.

| Command | What it does |
|---|---|
| `/verify-setup <channel>` | Set the channel new members are greeted in (needs Manage Server) |
| `/verify-panel [channel]` | Post a standing panel anyone can verify from, for members who joined before this existed |
| `/records-setup <channel>` | File a member record card in this channel every time somebody verifies |
| `/record <member>` | Re-file one member's record on demand |

Without setup Jarcord picks the first channel whose name contains `operator-id`, `verify`, or `register`. Emoji and dividers in the name don't matter.

**The other door.** Somebody from another group (an ally, a client booking ROC as OPFOR, an event host) is not an Operator and should not answer Operator questions. The panel has a second button, **Work with ROC**, with its own form: which group they speak for, their role there, Roblox name, what they are here for, and the detail. Submitting it swaps **Unverified** for **Guest**, tags the group onto their nickname, and opens a Work with ROC ticket with the answers already in it, so Command finds them in a private channel instead of in general. Guests hold no rank and no unit. Give the role whatever visibility you want; a diplomacy category with one overwrite is enough.

**Chasing the stragglers.** Every six hours Jarcord looks at who still holds **Unverified**. 24 hours after joining they get a DM with a link to the verification channel; 72 hours after joining a last one, and if their DMs are closed, a ping in the channel itself. After that they are left alone. `/nudge` sends the next reminder to everybody due right now, `/nudge @member` to one person, and both report how many were reached.

### Role utilities
| Command | What it does |
|---|---|
| `/dividers [count]` | Create N blank divider roles (default 10, max 25) to separate groups in the role list |
| `/c <count>` or `!c <count>` | Clear the last N messages in this channel, 1 to 100, pinned messages skipped, no receipt left behind (needs Manage Messages) |
| `/logs-setup <channel>` | Write every notable action to this channel (needs Manage Server) |

### Logs
With `/logs-setup` pointed at a Command only channel, Jarcord writes a card for each verification, outside contact, nudge, ticket opened and closed, promotion, demotion, warning, deleted warning, op posted, op closed, op cancelled, message clear and server code change. The card carries who did it, who it was done to and the reason where there is one, so enforcement has a paper trail without anyone keeping notes. The server code itself is never written to the log, only the fact that it changed.

They're created with no permissions at the bottom of the list, so drag them into place.

### Command permissions
Two layers, and they work together.

Discord decides who **sees** a command. Setup and officer commands ship with `default_permissions`, so ordinary members never get them in the picker, and any of it can be overridden per role or per member in **Server Settings, Integrations, Jarcord**, including locking everything to one person while you set up.

Jarcord decides who may **run** it, which also covers the prefix versions Discord cannot gate. A staff command passes for admins, for anyone holding the listed permission, or for the role set with `/officer-role`. That last one is how a second in command gets a few commands without being handed Manage Server.

Setting `/officer-role` grants that role a fixed, curated set. It is not per command, and it is deliberately not everything.

| Tier | Commands | Who |
|---|---|---|
| Officer | `/op create`, `/op edit`, `/op cancel`, `/op close`, `/promote`, `/demote`, `/warn`, `/warns`, `/unwarn`, `/nickname`, `/panel`, `/record`, `/verify-panel`, `/c`, `/code-set` | The officer role, plus anyone with the underlying permission. `/code-set` also passes for the **Server Host** role |
| Admin | `/op-setup`, `/verify-setup`, `/welcome-setup`, `/welcome-preview`, `/records-setup`, `/officer-role`, `/ranks-setup`, `/promotions-setup`, `/dividers` | Manage Server only |
| Member | `/profile`, `/code`, `/op join`, `/op leave`, `/op roster`, `/op list`, `/rate`, `/rating-history`, `/continent`, `/unit`, `/roblox`, `/activity`, `/panel-list` | Everyone |

The split is running the faction versus configuring the server. An officer posts ops, renames people, files records and reposts panels. Wiring up which channel things land in stays with you.

### Welcome
A card in the welcome channel when someone joins: their avatar, the member number, and links to the rules and verification channels.

| Command | What it does |
|---|---|
| `/welcome-setup <channel> [message]` | Set the channel, and optionally the greeting line (needs Manage Server) |
| `/welcome-preview` | See the card without waiting for a join |

The message accepts `{user}`, `{name}`, `{server}` and `{count}`. Nothing is posted until the channel is set.

### Warnings
Your enforcement rules say warning, then removal. This is the record that makes "repeated" mean something.

| Command | What it does |
|---|---|
| `/warn @member <reason>` | Log a warning, DM the member, file a card in the records channel |
| `/warns @member` | Their full history, last ten shown |
| `/unwarn <id>` | Delete one by its number |

The count shows on `/profile` and on their member record. Needs Moderate Members or the officer role.

### Ranks
A nine step ladder from Private 1 to Staff Sergeant, separate from the Operator access role and from Command, so promoting somebody never touches who can see what or who runs the faction. Verifying lands a member on Private 1.

| Command | What it does |
|---|---|
| `/promote @member [reason]` | One step up: swaps the rank role, DMs them, files a card in the records channel |
| `/demote @member [reason]` | One step down, same trail |
| `/ranks-setup` | Create every rank, the `NCO` marker and the position roles that are missing, and start every verified member who has no rank on Private 1 (needs Manage Server) |
| `/promotions-setup <channel>` | Announce every promotion and demotion there, member pinged, reason included (needs Manage Server) |

From Corporal 1 up a member also holds the `NCO` marker, so an NCO channel needs one permission line and never has to be touched when the ladder changes. Rank shows on `/profile`.

### Server code
| Command | What it does |
|---|---|
| `/code` | The private server code, ephemeral, verified members only |
| `/code-set <code>` | Change it. Command, or whoever holds the **Server Host** role |

The information hub's key button reads the same setting live, so changing the code never means re-posting anything.

### Tickets
A private channel per request, filed on close. Make a category with "ticket" in the name, run `/tickets-setup`, and Jarcord fills it: `🎫┃tickets` (visible to everyone, read only) with the panel in it, `📁┃ticket-logs` (Command only), and every opened ticket lands there too. Without such a category the panel goes next to the information channel, transcripts next to the channel `/logs-setup` points at, and opened tickets under that Command category; opened tickets carry their own overwrites, so they are private wherever they sit. Pass `panel`, `logs` or `category` to use channels you already have. A `TICKETS` category is created only if there is nothing at all to go on. Five buttons: a question or problem, a leave of absence, a position application (Media, Op Planner, JTAC, Server Host), a member report, and Work with ROC for outside groups. Each opens a short form; submitting it cuts a channel named after the kind and the member (`loa-heero`, `dip-somebody`) that only they, Command and Jarcord can see, and posts their answers as a card with **Claim** and **Close** underneath. One open ticket per kind per person, so nobody floods the category.

The officer role is pinged when a ticket opens, nobody else; the opener already has the channel link. A dedicated ticket category is locked down by setup: hidden from everyone, open to the officer role, and each ticket adds its own opener on top. Closing files the whole channel as a text transcript in the log channel, with who opened it, who closed it, who claimed it and the reason, DMs the member, and only then deletes the channel. If the transcript cannot be filed the channel stays. The form answers and the transcript are also kept in the `tickets` table, so a ticket can be read straight from the database. A member who leaves with a ticket open gets a line posted in it rather than the ticket being closed under Command's feet.

| Command | What it does |
|---|---|
| `/tickets-setup [panel] [logs] [category]` | Point tickets at your own channels, or leave any of them out and Jarcord creates it. Posts the panel (needs Manage Server) |
| `/tickets-panel [channel]` | Post the panel again somewhere else |
| `/tickets [@member]` | Every open ticket, or one member's last fifteen |
| `/ticket-add @member` | Pull somebody else into the ticket you are standing in |
| `/ticket-close [reason]` | Same as the button. The opener can close their own, Command can close any |

The support role is whatever `/officer-role` points at, and Jarcord needs **Manage Channels**. Ticket kinds live in one table at the top of `cogs/tickets.py`; adding one is adding an entry.

### Info panels and the hub
Reference posts (banner image, section cards, buttons) defined as JSON files in `panels/` and posted on demand.

| Command | What it does |
|---|---|
| `/panel <name>` | Post the panel (needs Manage Messages) |
| `/panel-list` | Show available panels |

A section is either a block of `body` text or a list of `fields`, which render as evenly sized rows inside one card. Use fields for anything list shaped, like rules, so you get one tidy card instead of a dozen ragged ones. Copy `panels/example.json`, rename it, edit; the filename is the panel name.

A banner can be a URL or `file:name.png` for an image shipped in `panels/assets/`, attached at post time so nothing needs hosting. A button with a `url` is a link. A button with a `panel` opens that panel as an ephemeral reply, only the presser sees it, which is how `hub` works: one message in the information channel, a banner, and a row of buttons for who we are, rules, units, chain of command, working with ROC, channels, operations, commands and the server code. Hub buttons survive restarts.

### Activity tracking
Every non-bot guild message bumps a per-user counter and `last_seen` timestamp (UTC).

| Command | What it does |
|---|---|
| `/activity @member` | Message count, ops attended, last seen |
| `!inactive [days]` | Members inactive for N+ days (default 14, includes never-seen) |

Most commands are hybrid, so they work as both slash and prefix versions.

## Project structure

```
bot.py            entry point: loads cogs, syncs slash commands to GUILD_ID
db.py             sqlite3 schema + shared connection (data/jarcord.db)
ui.py             shared embed styling (accent colour)
cogs/ops.py       op signups
cogs/rating.py    ratings
cogs/activity.py  activity tracking
cogs/profile.py   Roblox link + continent + profile card
cogs/panels.py    info panels and the hub
cogs/verify.py    new-member nickname verification
cogs/roles.py     server setup, role utilities, server code
cogs/welcome.py   join welcome card
cogs/warnings.py  warning log
cogs/ranks.py     rank ladder
cogs/tickets.py   tickets, transcripts, the Work with ROC door
panels/*.json     panel definitions
panels/assets/    images attached to panels
setup.sh          LXC provisioning script
jarcord.service   systemd unit
```

## Setup

1. Create a bot at the [Discord developer portal](https://discord.com/developers/applications).
   Under **Bot**, enable the **Server Members** and **Message Content** privileged intents.
2. Invite it to the server with the `bot` + `applications.commands` scopes.
3. Configure:
   ```bash
   cp .env.example .env
   # fill in DISCORD_TOKEN, GUILD_ID (server ID), COMMAND_PREFIX (default !)
   ```
4. Run locally:
   ```bash
   python -m venv venv
   venv/bin/pip install -r requirements.txt   # Windows: venv\Scripts\pip
   venv/bin/python bot.py
   ```

Slash commands sync to the guild in `GUILD_ID` on startup, so they appear instantly.

## Deployment

`setup.sh` handles both cases: run it as root and you get a system service, run it as a normal
user (Hack Club Nest, any shared box) and you get a user service with lingering enabled. It
takes its paths from wherever the repo actually sits, so nothing is hardcoded to `/opt`.

**As root**, on a fresh Debian or Ubuntu box:

```bash
git clone <repo-url> /opt/jarcord
cd /opt/jarcord
bash setup.sh
nano .env                     # token + guild ID
systemctl start jarcord
journalctl -u jarcord -f
```

**As a plain user**:

```bash
git clone <repo-url> ~/jarcord
cd ~/jarcord
bash setup.sh
nano .env
systemctl --user start jarcord
journalctl --user -u jarcord -f
```

The unit auto-restarts on failure with a 5 second backoff, and runs unbuffered so the `>> `
lines reach the journal live. The database is one file at `data/jarcord.db`; back that up and
you have everything, including every guild setting.

## AI usage declaration

The v1 codebase was written by Claude Code (Anthropic) working under my direction: I defined the full feature scope, command surface, tech stack (discord.py 2.x, plain sqlite3, cog structure, systemd deployment), and the constraints (single-server, no ORM, no moderation features, prefix + slash support). Claude Code implemented the cogs, schema, and deployment scripts to that spec; I review, test, and maintain the code.
