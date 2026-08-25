# ── Jarcord DB — plain sqlite3, single shared connection ──
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
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS signups (
    op_id     INTEGER NOT NULL REFERENCES ops(id),
    user_id   INTEGER NOT NULL,
    signed_at TEXT NOT NULL DEFAULT (datetime('now')),
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
"""

DATA_DIR.mkdir(exist_ok=True)
# ponytail: one sync connection, no pool — single-server bot, writes are tiny.
# discord.py runs everything on one event-loop thread, so this is safe.
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON")
conn.executescript(SCHEMA)
conn.commit()
