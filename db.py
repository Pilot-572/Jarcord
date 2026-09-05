# ── Jarcord DB: plain sqlite3, single shared connection ──
import os
import sqlite3
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
# JARCORD_DB overrides the file. A test sets it to ":memory:" before importing anything.
DB_PATH = os.getenv("JARCORD_DB") or str(DATA_DIR / "jarcord.db")

# The shape at v1, frozen. A new table may go here (IF NOT EXISTS is idempotent), but a
# new column on an existing table goes in MIGRATIONS, never here: SCHEMA runs first on
# every start, so a column added here would make the migration that adds it fail.
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
    thread_id  INTEGER,           -- discussion thread, deliberately not the card's own thread
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
    age_group   TEXT,
    rank        TEXT,             -- a name from cogs.ranks.RANKS, NULL until first promotion
    nudged      INTEGER NOT NULL DEFAULT 0   -- verification reminders sent, 0 to 2
);

CREATE TABLE IF NOT EXISTS warnings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    officer_id INTEGER NOT NULL,
    reason     TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tickets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    kind       TEXT NOT NULL,          -- a key from cogs.tickets.KINDS
    channel_id INTEGER,                -- NULL for the moment between the row and the channel
    claimed_by INTEGER,
    status     TEXT NOT NULL DEFAULT 'open',   -- open | closed
    opened_at  TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at  TEXT,
    closed_by  INTEGER,
    answers    TEXT,                -- the form, one "label: value" per line
    transcript TEXT                 -- the whole channel, written on close
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Recurring posts that go out with nobody present: the recruitment advert first.
-- next_ts is recomputed after every send, so a restart never double-posts and a
-- missed window is simply the next window.
CREATE TABLE IF NOT EXISTS posts (
    name       TEXT PRIMARY KEY,       -- 'advert'
    channel_id INTEGER,
    body       TEXT NOT NULL,
    every_min  INTEGER NOT NULL,       -- 1440 = daily
    at_minute  INTEGER,                -- minutes past local midnight for the day's first slot
    enabled    INTEGER NOT NULL DEFAULT 1,
    last_run   TEXT,
    next_ts    INTEGER
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

def connect(path: str) -> sqlite3.Connection:
    """One connection with the pragmas every reader and writer needs. WAL lets a backup
    or a read-only report run while the bot writes, the busy timeout makes a write wait
    instead of raising, and NORMAL sync is safe under WAL and much cheaper than FULL."""
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA journal_mode = WAL")      # answers "memory" on :memory:, which is fine
    c.execute("PRAGMA busy_timeout = 5000")
    c.execute("PRAGMA synchronous = NORMAL")
    return c


# ── Migrations ──
# Each entry is a function taking the connection, numbered from 1 by its position in
# MIGRATIONS. The runner wraps each one in a transaction and stamps PRAGMA user_version
# inside it, so a migration that fails leaves the file exactly as it was. Inside a
# migration use c.execute per statement: executescript commits behind your back.
def m1_legacy_columns(c: sqlite3.Connection) -> None:
    """Columns added before the runner existed. Guarded one by one, because a file from
    any point in that history may be missing any subset of them. Nothing after this
    entry is allowed to look like this."""
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
        "ALTER TABLE ops ADD COLUMN thread_id INTEGER",
        "ALTER TABLE profiles ADD COLUMN rank TEXT",
        "ALTER TABLE profiles ADD COLUMN nudged INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE tickets ADD COLUMN answers TEXT",
        "ALTER TABLE tickets ADD COLUMN transcript TEXT",
        "ALTER TABLE ops ADD COLUMN notes TEXT",
        "ALTER TABLE signups ADD COLUMN status TEXT NOT NULL DEFAULT 'in'",
        "ALTER TABLE signups ADD COLUMN attended INTEGER",
        "ALTER TABLE ops ADD COLUMN closed INTEGER NOT NULL DEFAULT 0",
    ):
        try:
            c.execute(ddl)
        except sqlite3.OperationalError:
            pass  # column already exists


def m2_guild_id(c: sqlite3.Connection) -> None:
    """Rows a member can name by number get the guild they belong to, so a number typed
    in one server can never reach another server's row. Nullable for now: claim_orphans
    fills the old rows at startup, and the column tightens in the schema step."""
    for table in ("ops", "tickets", "warnings"):
        c.execute(f"ALTER TABLE {table} ADD COLUMN guild_id INTEGER")


MIGRATIONS = [m1_legacy_columns, m2_guild_id]


def db_file(c: sqlite3.Connection) -> Path | None:
    """The file behind a connection, or None for :memory:."""
    name = c.execute("PRAGMA database_list").fetchone()[2]
    return Path(name) if name else None


def backup(c: sqlite3.Connection, version: int) -> Path | None:
    """A copy of the file in data/backups, taken before a migration touches it.
    ponytail: one file per migration, nothing prunes them; a few MB each, a few a year."""
    src = db_file(c)
    if src is None or not src.exists():
        return None
    dest_dir = src.parent / "backups"
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / f"{src.stem}-v{version}-{datetime.now():%Y%m%d-%H%M%S}.db"
    out = sqlite3.connect(dest)
    try:
        c.backup(out)
    finally:
        out.close()
    print(f">> db backed up to {dest}")
    return dest


def migrate(c: sqlite3.Connection, migrations=MIGRATIONS) -> int:
    """Create anything missing, then apply every migration past the file's version.
    Returns the version the file is at afterwards."""
    c.executescript(SCHEMA)
    have = c.execute("PRAGMA user_version").fetchone()[0]
    if have < len(migrations):
        backup(c, have)
    for n, step in enumerate(migrations[have:], start=have + 1):
        c.execute("BEGIN")
        try:
            step(c)
            c.execute(f"PRAGMA user_version = {n}")
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
        print(f">> db migrated to v{n} ({step.__name__})")
    return c.execute("PRAGMA user_version").fetchone()[0]


DATA_DIR.mkdir(exist_ok=True)
# ponytail: one sync connection, no pool, single-server bot, writes are tiny.
# discord.py runs everything on one event-loop thread, so this is safe.
conn = connect(DB_PATH)
migrate(conn)


def claim_orphans(guild_id: int) -> None:
    """Rows written before guild_id existed all belong to the one guild this bot served
    then. Idempotent, so bot.py calls it on every start.
    ponytail: goes away with GUILD_ID in the multi-guild step, by which time no row is NULL."""
    for table in ("ops", "tickets", "warnings"):
        conn.execute(f"UPDATE {table} SET guild_id = ? WHERE guild_id IS NULL", (guild_id,))
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
