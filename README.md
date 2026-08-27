# Jarcord

Operations management for Discord teams: scheduled op signups, member performance ratings, and activity tracking, all inside your server. Built for faction/milsim communities; lean by design (Discord's built-in AutoMod handles moderation, so Jarcord doesn't).

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

### Registration
A real application form instead of a copy-paste template: `/register` opens a modal (Roblox username, age group, pronouns, time zone, availability). The submission posts to a staff channel as a card with **Approve** / **Deny** buttons.

Approving verifies the Roblox account, links it to their profile, sets their nickname, assigns the member role, and DMs them. Denying just marks the card. Review buttons survive bot restarts.

| Command | What it does |
|---|---|
| `/register` | Open the registration form |
| `/register-setup <channel> [role]` | Set the review channel and the role approved members get (needs Manage Server) |

Reviewing requires Manage Roles. One pending application per member.

### Verification
New members land restricted. On join they get the **Unverified** role and a prompt in the arrival channel. Pressing **Verify** opens a private form asking for their Roblox username and, optionally, what people should call them. The username is checked against the Roblox API and linked to their profile, their nickname is set for them, and **Unverified** is swapped for **Operator**. Nothing is ever typed in chat.

Roles are matched by exact name and created only if missing, and existing ones are never modified. Channel visibility is yours to configure with category overwrites; Jarcord only manages the two roles, so it needs **Manage Roles** with its own role above both. Members who rejoin already holding **Operator** skip the flow. The confirm button is persistent and idempotent.

| Command | What it does |
|---|---|
| `/verify-setup <channel>` | Set the channel new members are greeted in (needs Manage Server) |
| `/verify-panel [channel]` | Post a standing panel anyone can verify from, for members who joined before this existed |

Without setup Jarcord picks the first channel whose name contains `operator-id`, `verify`, or `register`. Emoji and dividers in the name don't matter.

### Role utilities
| Command | What it does |
|---|---|
| `/dividers [count]` | Create N blank divider roles (default 10, max 25) to separate groups in the role list |

They're created with no permissions at the bottom of the list, so drag them into place.

### Welcome
A card in the welcome channel when someone joins: their avatar, the member number, and links to the rules and verification channels.

| Command | What it does |
|---|---|
| `/welcome-setup <channel> [message]` | Set the channel, and optionally the greeting line (needs Manage Server) |
| `/welcome-preview` | See the card without waiting for a join |

The message accepts `{user}`, `{name}`, `{server}` and `{count}`. Nothing is posted until the channel is set.

### Info panels
Reference posts (banner image, section cards, link buttons) defined as JSON files in `panels/` and posted on demand.

| Command | What it does |
|---|---|
| `/panel <name>` | Post the panel (needs Manage Messages) |
| `/panel-list` | Show available panels |

Copy `panels/example.json`, rename it, edit; the filename is the panel name. Ships with `jarcord`, a member-facing guide to every command.

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
cogs/registration.py  registration form + staff review
cogs/verify.py    new-member nickname verification
cogs/roles.py     role-list utilities
cogs/welcome.py   join welcome card
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
