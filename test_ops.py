# ── Jarcord: op query layer self-check (venv/Scripts/python -X utf8 test_ops.py) ──
# ponytail: asserts only. Two guilds in one database, and every number typed by a person
# stops at the guild line. Also the close-out arithmetic, which promotions read.
import os
os.environ["JARCORD_DB"] = ":memory:"   # before any project import
from cogs.ops import (attendance, cancel_op, close_op, create_op, edit_op, get_op, join_op,
                      leave_op, list_embed, roster, roster_embed, set_status)
from db import conn

ROC, OTHER = 100, 200


class _Guild:
    """Enough of discord.Guild for the embeds: an id and no cached members."""
    def __init__(self, gid):
        self.id = gid

    def get_member(self, user_id):
        return None


a = create_op("Night raid", "2026-09-10 21:00", 1, 10, ROC)
b = create_op("Their op", "tomorrow", 2, 20, OTHER)

# ── a number from one guild never reaches the other's row ──
assert get_op(a, ROC)["title"] == "Night raid"
assert get_op(a, OTHER) is None
assert get_op(a)["guild_id"] == ROC                      # internal, unscoped, still works
assert "No op" in join_op(b, ROC, 1)
assert "No op" in cancel_op(b, ROC, 1, True)
assert get_op(b) is not None                             # and the row survived the attempt
assert "No op" in roster_embed(b, _Guild(ROC)).description

# ── rsvp ──
assert "on the roster" in join_op(a, ROC, 5)
assert "already" in join_op(a, ROC, 5)
set_status(a, 6, "maybe")
set_status(a, 7, "out")
assert roster(a) == {"in": [5], "maybe": [6], "out": [7]}
assert "Removed" in leave_op(a, ROC, 5)
assert "weren't" in leave_op(a, ROC, 5)

# ── edit: creator or officer ──
assert "Only" in edit_op(a, ROC, 99, False, what="x")
assert "Updated" in edit_op(a, ROC, 1, False, what="Night raid 2")
assert get_op(a)["title"] == "Night raid 2"
assert "Nothing to change" in edit_op(a, ROC, 1, False)

# ── close: said in and not picked is a no-show, picked without replying still counts ──
set_status(a, 5, "in")
set_status(a, 6, "in")
assert "Only" in close_op(a, ROC, 99, False, [5])
msg = close_op(a, ROC, 1, False, [5, 8])
assert "2 attended, 1 no-showed" in msg, msg
assert attendance(5) == (1, 0)
assert attendance(6) == (0, 1)
assert attendance(8) == (1, 0)
assert "already closed" in close_op(a, ROC, 1, False, [5])

# ── the list only shows this guild ──
assert "Night raid 2" in list_embed(ROC).description
assert "Their op" not in list_embed(ROC).description
assert "Night raid" not in list_embed(OTHER).description
assert "Their op" in list_embed(OTHER).description

# ── cancel takes the signups with it ──
assert "Cancelled" in cancel_op(a, ROC, 1, False)
assert get_op(a) is None
assert conn.execute("SELECT COUNT(*) FROM signups WHERE op_id = ?", (a,)).fetchone()[0] == 0


# ── the status line and the running total ──
from cogs.ops import marks_in, status_text

conn.execute("DELETE FROM signups"); conn.execute("DELETE FROM ops"); conn.commit()
now = 1_800_000_000
assert status_text(now) == "the ops board"
conn.execute("INSERT INTO ops (id, guild_id, title, when_text, created_by) VALUES (1, 1, 'A', 'x', 9)")
assert status_text(now) == "1 op on the board"                       # free text time, no countdown
conn.execute("INSERT INTO ops (id, guild_id, title, when_text, created_by, when_ts) VALUES (2, 1, 'B', 'x', 9, ?)",
             (now + 2 * 86400,))
assert status_text(now) == "2 ops on the board", status_text(now)   # two days out is not "next"
conn.execute("INSERT INTO ops (id, guild_id, title, when_text, created_by, when_ts) VALUES (3, 1, 'C', 'x', 9, ?)",
             (now + 7200,))
assert status_text(now) == "Op 3, in 2 hours", status_text(now)
assert status_text(now + 7200 - 600) == "Op 3, in 10 minutes"
assert status_text(now + 7200 + 60) == "Op 3, live now"
assert status_text(now + 7200 + 4 * 3600) == "3 ops on the board"   # past the live window, still unclosed
conn.execute("UPDATE ops SET closed = 1 WHERE id = 3")
assert status_text(now + 7200 + 60) == "2 ops on the board"
conn.execute("INSERT INTO ops (id, guild_id, title, when_text, created_by, closed) VALUES (4, 2, 'D', 'x', 9, 1)")
conn.executemany("INSERT INTO signups (op_id, user_id, attended) VALUES (?, ?, ?)",
                 [(3, 10, 1), (3, 11, 0), (3, 12, None), (4, 10, 1)])
conn.commit()
assert marks_in(1) == 1 and marks_in(2) == 1 and marks_in(3) == 0

print(">> ok")
