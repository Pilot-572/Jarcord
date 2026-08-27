#!/usr/bin/env bash
# ── Jarcord setup: works as root (LXC, VPS) or as a plain user (Hack Club Nest) ──
# Run it from inside the repo. It installs the venv, deps and a systemd unit.
set -e
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "$(id -u)" -eq 0 ]; then
    MODE=system
    UNIT=/etc/systemd/system/jarcord.service
    CTL="systemctl"
    apt-get update
    apt-get install -y python3 python3-venv
else
    # ponytail: no root, no apt. Nest images already ship python3 and venv.
    MODE=user
    UNIT="$HOME/.config/systemd/user/jarcord.service"
    CTL="systemctl --user"
    mkdir -p "$(dirname "$UNIT")"
    command -v python3 >/dev/null || { echo "!! python3 missing and I can't apt-get without root"; exit 1; }
fi
echo ">> installing as a $MODE service in $APP_DIR"

cd "$APP_DIR"
mkdir -p data          # the bot creates this too, but scp needs it up front
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

if [ ! -f .env ]; then
    cp .env.example .env
    echo ">> created $APP_DIR/.env, fill in DISCORD_TOKEN and GUILD_ID before starting"
fi

sed "s|/opt/jarcord|$APP_DIR|g" jarcord.service > "$UNIT"
if [ "$MODE" = user ]; then
    # the user manager has no network-online.target and no multi-user.target
    sed -i -e '/network-online.target/d' -e 's|WantedBy=multi-user.target|WantedBy=default.target|' "$UNIT"
    loginctl enable-linger "$USER" 2>/dev/null \
        || echo ">> couldn't enable lingering, the bot will stop when you log out"
fi

$CTL daemon-reload
$CTL enable jarcord

echo ">> done. Fill $APP_DIR/.env, then: $CTL start jarcord"
echo ">> logs: journalctl $([ "$MODE" = user ] && echo --user) -u jarcord -f"
