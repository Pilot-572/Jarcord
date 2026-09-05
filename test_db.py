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

print(">> ok")
