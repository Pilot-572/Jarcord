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
assert fields["Ops"] == "2 posted, 1 closed\n2 attendance marks", fields["Ops"]
assert fields["Warnings"] == "1 filed, none received"
assert fields["Last seen"].startswith("Right now. Up since <t:")
assert e.footer.text.startswith(f"Build {BUILD}. 0 tickets filed.")
assert BUILD  # "unknown" outside a git checkout, a short hash inside one

print(">> ok")
