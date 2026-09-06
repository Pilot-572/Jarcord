# ── Jarcord: self-check for the bot's own profile card (python -X utf8 test_profile.py) ──
import os
os.environ["JARCORD_DB"] = ":memory:"   # before any project import, so tests never touch data/jarcord.db

from cogs.profile import BUILD, self_card
from db import conn

# two ops in guild 1, one closed with two marks, one open; one op in guild 2 that must not count
conn.execute("INSERT INTO ops (id, guild_id, title, when_text, created_by, closed) VALUES (1, 1, 'A', 'x', 9, 1)")
conn.execute("INSERT INTO ops (id, guild_id, title, when_text, created_by, closed) VALUES (2, 1, 'B', 'x', 9, 0)")
conn.execute("INSERT INTO ops (id, guild_id, title, when_text, created_by, closed) VALUES (3, 2, 'C', 'x', 9, 1)")
conn.executemany("INSERT INTO signups (op_id, user_id, attended) VALUES (?, ?, ?)",
                 [(1, 10, 1), (1, 11, 0), (2, 10, None), (3, 12, 1)])
conn.execute("INSERT INTO warnings (guild_id, user_id, officer_id, reason) VALUES (1, 10, 9, 'late')")
conn.execute("INSERT INTO tickets (guild_id, user_id, kind, channel_id) VALUES (2, 10, 'help', 5)")
conn.commit()

e = self_card(1, "Jarcord", "https://example.invalid/a.png")
fields = {f.name: f.value for f in e.fields}
assert len(e.fields) == 9, "same nine fields as a member card"
assert fields["Ops"] == "2 posted, 1 closed\n1 attendance mark", fields["Ops"]
assert fields["Warnings"] == "1 filed, none received"
assert fields["Last seen"].startswith("Right now. Up since <t:")
assert e.footer.text.startswith(f"Build {BUILD}. 0 tickets filed.")
assert BUILD  # "unknown" outside a git checkout, a short hash inside one


# ── streaks ──
from cogs.profile import streak, turnout_lines

conn.executemany("INSERT INTO ops (id, guild_id, title, when_text, created_by, closed, when_ts) "
                 "VALUES (?, 1, 'S', 'x', 9, 1, ?)", [(4, 100), (5, 200), (6, 300)])
conn.executemany("INSERT INTO signups (op_id, user_id, attended) VALUES (?, 20, ?)", [(4, 0), (5, 1), (6, 1)])
conn.commit()
assert streak(20) == 2      # newest first: came, came, then the no-show ends it
assert streak(10) == 1
assert streak(99) == 0
assert turnout_lines(0, 0, 0, 0) == "none yet"
assert turnout_lines(4, 3, 1, 3) == "4 signed up\n3 attended, 1 no-showed\n3 in a row"
assert turnout_lines(4, 3, 1, 2) == "4 signed up\n3 attended, 1 no-showed"
assert turnout_lines(6, 6, 0, 6) == "6 signed up\n6 attended, 0 no-showed\nPerfect turnout, 6 in a row"

print(">> ok")
