# ── Jarcord: self-check for the ticket kinds table (python -X utf8 test_tickets.py) ──
# Discord rejects a modal with more than five inputs or a label over 45 characters at
# send time, which is the worst moment to find out. This catches it at commit time.
import os
os.environ["JARCORD_DB"] = ":memory:"   # before any project import, so tests never touch data/jarcord.db
import re

from cogs.tickets import KINDS, panel_message, slugify

for kind, spec in KINDS.items():
    assert re.fullmatch(r"[a-z]+", kind), f"{kind}: kind must match the OpenButton template"
    assert re.fullmatch(r"[a-z0-9-]+", spec["slug"]), f"{kind}: slug goes in a channel name"
    assert len(spec["title"]) <= 45, f"{kind}: modal title over 45"
    assert 1 <= len(spec["fields"]) <= 5, f"{kind}: a modal takes 1 to 5 inputs"
    for f in spec["fields"]:
        assert len(f["label"]) <= 45, f"{kind}: label {f['label']!r} over 45"
        assert len(f.get("placeholder", "")) <= 100, f"{kind}: placeholder over 100"
        assert f.get("max_length", 1) <= 4000, f"{kind}: max_length over 4000"
    assert len(spec["blurb"]) <= 1024, f"{kind}: blurb is an embed field value"

assert slugify("Heero_Yuy!") == "heero-yuy"
assert slugify("---") == "member"
assert slugify("Neh") == "neh"

# the standing panel: one field and one button per kind, all under Discord's caps
class _Guild:
    icon = None
e, view = panel_message(_Guild())
assert len(e.fields) == len(KINDS) <= 25
assert len(view.children) == len(KINDS) <= 25
assert {b.custom_id for b in view.children} == {f"jarcord:ticket:open:{k}" for k in KINDS}

# ── query layer: every list stops at the guild line ──
from cogs.tickets import member_tickets, open_ticket_row, open_tickets
from db import conn

kind = next(iter(KINDS))
conn.execute("INSERT INTO tickets (guild_id, user_id, kind, channel_id) VALUES (100, 5, ?, 555)", (kind,))
conn.execute("INSERT INTO tickets (guild_id, user_id, kind, channel_id, status) "
             "VALUES (100, 5, ?, 556, 'closed')", (kind,))
conn.execute("INSERT INTO tickets (guild_id, user_id, kind, channel_id) VALUES (200, 5, ?, 777)", (kind,))
conn.commit()

assert open_ticket_row(100, 5, kind)["channel_id"] == 555
assert open_ticket_row(300, 5, kind) is None
assert [r["channel_id"] for r in open_tickets(100)] == [555]          # open only, this guild only
assert [r["channel_id"] for r in open_tickets(300)] == []
assert [r["channel_id"] for r in member_tickets(100, 5)] == [556, 555]  # newest first, both states
assert [r["channel_id"] for r in member_tickets(200, 5)] == [777]

print(">> ok")
