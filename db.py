# ── Jarcord DB: plain sqlite3, single shared connection ──
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "jarcord.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS ops (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    when_text  TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    when_ts    INTEGER,           -- unix ts (UTC) when parseable, else NULL
    channel_id INTEGER,           -- where the op was posted (reminder target)
    message_id INTEGER,           -- the posted card, edited as people RSVP
    notes      TEXT,
    closed     INTEGER NOT NULL DEFAULT 0,
    reminded   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS signups (
    op_id     INTEGER NOT NULL REFERENCES ops(id),
    user_id   INTEGER NOT NULL,
    signed_at TEXT NOT NULL DEFAULT (datetime('now')),
    status    TEXT NOT NULL DEFAULT 'in',   -- in | maybe | out
    attended  INTEGER,                       -- NULL until the op is closed, then 1 or 0
    PRIMARY KEY (op_id, user_id)
);

CREATE TABLE IF NOT EXISTS ratings (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL,
    rater_id INTEGER NOT NULL,
    score    INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
    note     TEXT,
    rated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS activity (
    user_id       INTEGER PRIMARY KEY,
    message_count INTEGER NOT NULL DEFAULT 0,
    last_seen     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id     INTEGER PRIMARY KEY,
    roblox_name TEXT,
    roblox_id   INTEGER,
    continent   TEXT,
    unit        TEXT,
    play_hours  TEXT,
    heard_from  TEXT,
    experience  TEXT,
    age_group   TEXT
);

CREATE TABLE IF NOT EXISTS warnings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    officer_id INTEGER NOT NULL,
    reason     TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS applications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    roblox       TEXT NOT NULL,
    age_group    TEXT,
    pronouns     TEXT,
    timezone     TEXT,
    availability TEXT,
    status       TEXT NOT NULL DEFAULT 'pending',
    reviewer_id  INTEGER,
    message_id   INTEGER,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

DATA_DIR.mkdir(exist_ok=True)
# ponytail: one sync connection, no pool, single-server bot, writes are tiny.
# discord.py runs everything on one event-loop thread, so this is safe.
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON")
conn.executescript(SCHEMA)

# migrate pre-reminder databases
for ddl in (
    "ALTER TABLE ops ADD COLUMN when_ts INTEGER",
    "ALTER TABLE ops ADD COLUMN channel_id INTEGER",
    "ALTER TABLE ops ADD COLUMN reminded INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE profiles ADD COLUMN play_hours TEXT",
    "ALTER TABLE profiles ADD COLUMN heard_from TEXT",
    "ALTER TABLE profiles ADD COLUMN experience TEXT",
    "ALTER TABLE profiles ADD COLUMN age_group TEXT",
    "ALTER TABLE profiles ADD COLUMN unit TEXT",
    "ALTER TABLE ops ADD COLUMN message_id INTEGER",
    "ALTER TABLE ops ADD COLUMN notes TEXT",
    "ALTER TABLE signups ADD COLUMN status TEXT NOT NULL DEFAULT 'in'",
    "ALTER TABLE signups ADD COLUMN attended INTEGER",
    "ALTER TABLE ops ADD COLUMN closed INTEGER NOT NULL DEFAULT 0",
):
    try:
        conn.execute(ddl)
    except sqlite3.OperationalError:
        pass  # column already exists
conn.commit()


# ── Settings helpers (guild config that shouldn't need a restart) ──
def get_setting(key: str) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = ?",
        (key, value, value),
    )
    conn.commit()
