# Jarcord

Operations management for Discord teams — scheduled op signups, member performance ratings, and activity tracking, all inside your server. Built for faction/milsim communities; lean by design (Discord's built-in AutoMod handles moderation, so Jarcord doesn't).

All informational output uses clean embeds with a consistent accent; confirmations stay short and inline.

## Features

### Op signups (RSVP)
| Command | What it does |
|---|---|
| `/op-create <title> <when>` | Post an op, returns its ID |
| `/op-join <id>` or `!op join <id>` | Sign up |
| `/op-leave <id>` or `!op leave <id>` | Drop off the roster |
| `/op-cancel <id>` or `!op cancel <id>` | Cancel an op (creator or Manage Server) |
| `!op roster <id>` | Who's signed up |
| `!op list` | Last 10 ops with signup counts |

`when` is free text, but if it matches `YYYY-MM-DD HH:MM` or `DD.MM HH:MM` (UTC), the op gets a real timestamp — shown in each viewer's local timezone — and the bot pings the roster in the op's channel 30 minutes before start.

### Member ratings
| Command | What it does |
|---|---|
| `/rate @member <1-5> [note]` or `!rate ...` | Rate someone's op performance |
| `/rating-history @member` | Average score + last 5 notes |

### Member profiles
| Command | What it does |
|---|---|
| `/roblox <username>` | Link your Roblox account — verified against the Roblox API, then sets your server nickname to it |
| `/continent <continent>` | Set your continent; assigns the matching role (created on first use) |
| `/profile [@member]` | Full card: Roblox link, continent, ops attended, average rating, messages, last seen |
| `/nickname @member [nickname]` | Rename a member (needs Manage Nicknames); omit the nickname to clear it |

Needs **Manage Nicknames** and **Manage Roles**, and Jarcord's role must sit above the members and continent roles it manages.

### Info panels
Reference posts — banner image, section cards, link buttons — defined as JSON files in `panels/` and posted on demand.

| Command | What it does |
|---|---|
| `/panel <name>` | Post the panel (needs Manage Messages) |
| `/panel-list` | Show available panels |

Copy `panels/example.json`, rename it, edit; the filename is the panel name. Ships with `jarcord` — a member-facing guide to every command.

### Activity tracking
Every non-bot guild message bumps a per-user counter and `last_seen` timestamp (UTC).

| Command | What it does |
|---|---|
| `/activity @member` | Message count, ops attended, last seen |
| `!inactive [days]` | Members inactive for N+ days (default 14, includes never-seen) |

Most commands are hybrid — they work as both slash and prefix versions.

## Project structure

```
bot.py            entry point — loads cogs, syncs slash commands to GUILD_ID
db.py             sqlite3 schema + shared connection (data/jarcord.db)
ui.py             shared embed styling (accent colour)
cogs/ops.py       op signups
cogs/rating.py    ratings
cogs/activity.py  activity tracking
cogs/profile.py   Roblox link + continent + profile card
cogs/panels.py    info panels
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

The systemd unit auto-restarts on failure (5s backoff). The database lives at `/opt/jarcord/data/jarcord.db` — back that one file up and you have everything.

## AI usage declaration

The v1 codebase was written by Claude Code (Anthropic) working under my direction: I defined the full feature scope, command surface, tech stack (discord.py 2.x, plain sqlite3, cog structure, systemd deployment), and the constraints (single-server, no ORM, no moderation features, prefix + slash support). Claude Code implemented the cogs, schema, and deployment scripts to that spec; I review, test, and maintain the code.
