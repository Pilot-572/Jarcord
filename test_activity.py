# ── Jarcord: activity batching self-check (venv/Scripts/python -X utf8 test_activity.py) ──
# ponytail: asserts only. The count must add up across flushes and last_seen must be the
# newest message, in SQLite's own text format, or /inactive starts lying.
import os
os.environ["JARCORD_DB"] = ":memory:"   # before any project import
from datetime import datetime, timezone

from cogs.activity import flush, note_message, pending
from db import conn

t1 = datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc)
t2 = datetime(2026, 9, 5, 10, 5, tzinfo=timezone.utc)

note_message(7, t1)
note_message(7, t2)
note_message(8, t1)
assert flush() == 2                                   # two people, one row each
assert not pending                                    # and nothing left behind
row = conn.execute("SELECT message_count, last_seen FROM activity WHERE user_id = 7").fetchone()
assert row["message_count"] == 2
assert row["last_seen"] == "2026-09-05 10:05:00"      # the newest, in datetime('now') format

note_message(7, t2)
assert flush() == 1
assert conn.execute("SELECT message_count FROM activity WHERE user_id = 7").fetchone()[0] == 3
assert flush() == 0                                   # nothing pending is a no-op, not a write

print(">> ok")
