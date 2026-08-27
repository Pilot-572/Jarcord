# Jarcord

Operations management for Discord teams: scheduled op signups, member performance ratings, and activity tracking, all inside your server. Built for faction/milsim communities; lean by design (Discord's built-in AutoMod handles moderation, so Jarcord doesn't).

All informational output uses clean embeds with a consistent accent; confirmations stay short and inline.

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

Closing an op is how attendance gets recorded. Pick everyone who turned up from a member picker; anyone who said they were coming and isn't picked is logged as a no-show, and anyone who walked in without replying still counts as attending. A closed card shows the turnout and loses its buttons. `/profile` then reports signed up, attended and no-showed instead of a signup count that means nothing.

The card carries **Attending**, **Maybe** and **Can't make it**. Pressing one rewrites the card in place, so the three lists are always current, and changing your mind moves you rather than adding you twice. The buttons survive restarts.

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
New members land restricted. On join they get the **Unverified** role and a prompt in the arrival channel. Pressing **Verify** walks them through a short private flow. Step one asks for their Roblox username, checked against the Roblox API, and what people call them in-game, which becomes their nickname. Step two is their unit (Ground Unit or Sniper Unit) and continent, both of which assign the matching role, plus optional time blocks for when they play. Then they either finish or answer three optional questions (how they found the server, age group, previous experience). Verifying swaps **Unverified** for **Operator**. Nothing is ever typed in chat.

Roles are matched by exact name and created only if missing, and existing ones are never modified. Channel visibility is yours to configure with category overwrites; Jarcord only manages the two roles, so it needs **Manage Roles** with its own role above both. Members who rejoin already holding **Operator** skip the flow. The confirm button is persistent and idempotent.

| Command | What it does |
|---|---|
| `/verify-setup <channel>` | Set the channel new members are greeted in (needs Manage Server) |
| `/verify-panel [channel]` | Post a standing panel anyone can verify from, for members who joined before this existed |
| `/records-setup <channel>` | File a member record card in this channel every time somebody verifies |
| `/record <member>` | Re-file one member's record on demand |

Without setup Jarcord picks the first channel whose name contains `operator-id`, `verify`, or `register`. Emoji and dividers in the name don't matter.

### Role utilities
| Command | What it does |
|---|---|
| `/dividers [count]` | Create N blank divider roles (default 10, max 25) to separate groups in the role list |

They're created with no permissions at the bottom of the list, so drag them into place.

### Command permissions
Two layers, and they work together.

Discord decides who **sees** a command. Setup and officer commands ship with `default_permissions`, so ordinary members never get them in the picker, and any of it can be overridden per role or per member in **Server Settings, Integrations, Jarcord**, including locking everything to one person while you set up.

Jarcord decides who may **run** it, which also covers the prefix versions Discord cannot gate. A staff command passes for admins, for anyone holding the listed permission, or for the role set with `/officer-role`. That last one is how a second in command gets a few commands without being handed Manage Server.

Setting `/officer-role` grants that role a fixed, curated set. It is not per command, and it is deliberately not everything.

| Tier | Commands | Who |
|---|---|---|
| Officer | `/op create`, `/op edit`, `/op cancel`, `/op close`, `/warn`, `/warns`, `/unwarn`, `/nickname`, `/panel`, `/record`, `/verify-panel` | The officer role, plus anyone with the underlying permission |
| Admin | `/op-setup`, `/verify-setup`, `/welcome-setup`, `/welcome-preview`, `/records-setup`, `/officer-role`, `/dividers` | Manage Server only |
| Member | `/profile`, `/op join`, `/op leave`, `/op roster`, `/op list`, `/rate`, `/rating-history`, `/continent`, `/roblox`, `/activity`, `/panel-list` | Everyone |

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

### Info panels
Reference posts (banner image, section cards, link buttons) defined as JSON files in `panels/` and posted on demand.

| Command | What it does |
|---|---|
| `/panel <name>` | Post the panel (needs Manage Messages) |
| `/panel-list` | Show available panels |

A section is either a block of `body` text or a list of `fields`, which render as evenly sized rows inside one card. Use fields for anything list shaped, like rules, so you get one tidy card instead of a dozen ragged ones. Copy `panels/example.json`, rename it, edit; the filename is the panel name. Ships with `jarcord`, a member-facing guide to every command.

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
cogs/panels.py    info panels
cogs/verify.py    new-member nickname verification
cogs/roles.py     role-list utilities
cogs/welcome.py   join welcome card
cogs/warnings.py  warning log
panels/*.json     panel definitions
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

## Deployment (Proxmox LXC)

On a fresh Debian/Ubuntu LXC:

```bash
git clone <repo-url> /opt/jarcord    # or scp the folder there
cd /opt/jarcord
bash setup.sh
nano .env                            # token + guild ID
systemctl start jarcord
journalctl -u jarcord -f             # logs
```

The systemd unit auto-restarts on failure (5s backoff). The database lives at `/opt/jarcord/data/jarcord.db`. Back that one file up and you have everything.

## AI usage declaration

The v1 codebase was written by Claude Code (Anthropic) working under my direction: I defined the full feature scope, command surface, tech stack (discord.py 2.x, plain sqlite3, cog structure, systemd deployment), and the constraints (single-server, no ORM, no moderation features, prefix + slash support). Claude Code implemented the cogs, schema, and deployment scripts to that spec; I review, test, and maintain the code.
