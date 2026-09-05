# ── Jarcord: database layer self-check (venv/Scripts/python -X utf8 test_db.py) ──
# ponytail: asserts only. Guards the things that only show up on the first bad deploy:
# a pragma that silently did not apply, a migration that half-ran, a backup that was
# taken after the change instead of before.
import os
os.environ["JARCORD_DB"] = ":memory:"   # before db is imported, so the real file is never touched
import sqlite3
import tempfile
from pathlib import Path

from db import connect

# ── connect: every pragma actually took ──
c = connect(":memory:")
assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1
assert c.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
assert c.execute("PRAGMA synchronous").fetchone()[0] == 1          # NORMAL
assert c.execute("SELECT 1 AS one").fetchone()["one"] == 1         # rows come back by name
c.close()
with tempfile.TemporaryDirectory() as tmp:
    f = connect(str(Path(tmp) / "t.db"))
    assert f.execute("PRAGMA journal_mode").fetchone()[0] == "wal"  # only a file can be WAL
    f.close()

from db import MIGRATIONS, backup, m1_legacy_columns, migrate

# ── migrate: a fresh database lands on the newest version ──
c = connect(":memory:")
assert migrate(c) == len(MIGRATIONS)
tables = {r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
assert {"ops", "signups", "tickets", "warnings", "settings", "posts"} <= tables
assert migrate(c) == len(MIGRATIONS)                    # a second run does nothing
c.close()

# ── migrate: a file from before the runner existed is upgraded, and backed up first ──
with tempfile.TemporaryDirectory() as tmp:
    path = str(Path(tmp) / "old.db")
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE ops (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, when_text TEXT NOT NULL,
            created_by INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')));
        INSERT INTO ops (title, when_text, created_by) VALUES ('Old op', 'tonight', 1);
    """)
    old.commit()
    old.close()

    c = connect(path)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 0
    assert migrate(c) == len(MIGRATIONS)
    cols = {r["name"] for r in c.execute("PRAGMA table_info(ops)")}
    assert {"when_ts", "notes", "closed", "thread_id", "reminded"} <= cols   # m1 added them
    assert c.execute("SELECT title FROM ops").fetchone()["title"] == "Old op"  # and kept the row
    c.close()

    backups = list((Path(tmp) / "backups").glob("old-v0-*.db"))
    assert len(backups) == 1, backups
    b = sqlite3.connect(backups[0])
    assert b.execute("SELECT COUNT(*) FROM ops").fetchone()[0] == 1
    # the copy is of the file before the migration, which is the whole point of it
    assert "notes" not in {r[1] for r in b.execute("PRAGMA table_info(ops)")}
    b.close()

    c = connect(path)
    migrate(c)                                                      # nothing pending
    c.close()
    assert len(list((Path(tmp) / "backups").glob("*.db"))) == 1     # so no second backup

# ── migrate: a migration that fails leaves the file exactly as it was ──
def m_bad(c):
    c.execute("CREATE TABLE half (x)")
    raise RuntimeError("boom")

c = connect(":memory:")
try:
    migrate(c, [m1_legacy_columns, m_bad])
    assert False, "a failing migration must raise, not be swallowed"
except RuntimeError:
    pass
assert c.execute("PRAGMA user_version").fetchone()[0] == 1          # m1 stuck, m_bad did not
assert c.execute("SELECT name FROM sqlite_master WHERE name = 'half'").fetchone() is None
c.close()

# ── backup: nothing to copy for a memory database ──
c = connect(":memory:")
assert backup(c, 0) is None
c.close()

print(">> ok")
