#!/usr/bin/env bash
# ── Jarcord LXC setup — run as root inside a Debian/Ubuntu LXC ──
# Expects the repo to already be at /opt/jarcord (git clone or scp it there first).
set -e
APP_DIR=/opt/jarcord

apt-get update
apt-get install -y python3 python3-venv

cd "$APP_DIR"
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

if [ ! -f .env ]; then
    cp .env.example .env
    echo ">> created $APP_DIR/.env — fill in DISCORD_TOKEN and GUILD_ID before starting"
fi

cp jarcord.service /etc/systemd/system/jarcord.service
systemctl daemon-reload
systemctl enable jarcord

echo ">> done. Fill $APP_DIR/.env, then: systemctl start jarcord"
