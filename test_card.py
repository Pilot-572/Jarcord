# ── Jarcord: op card naming self-check (venv/Scripts/python -X utf8 test_card.py) ──
# ponytail: asserts only. Guards the one thing a second client sees differently:
# a raw <@id> in an embed when their client has not cached that user.
from types import SimpleNamespace as NS

from cogs.ops import who

member = NS(id=7, display_name="heero")
guild = NS(get_member=lambda uid: member if uid == 7 else None)

# somebody the bot can see in the guild is named, never mentioned
assert who(guild, 7) == "heero"
# somebody it cannot resolve still shows something rather than a bare number
assert who(guild, 999) == "<@999>"
# no guild at all (a cache miss on startup) must not raise
assert who(None, 7) == "<@7>"

print(">> ok")
