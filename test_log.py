# ── Jarcord: command log formatting self-check (venv/Scripts/python test_log.py) ──
# ponytail: asserts only, no framework. The command log is the record a moderation
# dispute gets read from, so the two things that would quietly ruin it are guarded here:
# an argument that goes missing, and one long enough to push the embed over Discord's limit.
import os
os.environ["JARCORD_DB"] = ":memory:"   # before any project import, so tests never touch data/jarcord.db

from ui import one_line

# name and value, in the order they were given
assert one_line([("member", "Howitzer"), ("reason", "late")]) == "**member** Howitzer · **reason** late"
# an argument that was not filled in leaves no trace
assert one_line([("member", "Howitzer"), ("reason", None), ("note", "")]) == "**member** Howitzer"
# zero is a real answer and stays
assert one_line([("count", 0)]) == "**count** 0"
# no arguments is an empty string, not the word None
assert one_line([]) == ""
# a multi-line argument stays on one line, or it breaks the reading of every line after it
assert "\n" not in one_line([("notes", "first\nsecond\nthird")])
# a long argument is cut, so forty arguments cannot overflow the embed
long = one_line([("notes", "x" * 500)])
assert len(long) == len("**notes** ") + 120, len(long)
# and the cut keeps the start, which is the part worth reading
assert long.startswith("**notes** xxx")


# ── deleted_line: the text a bulk delete files, read when people argue about who said what ──
from datetime import datetime, timezone

from ui import deleted_line


class Fake:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __str__(self):
        return self.__dict__.get("name", "")


def message(content, embeds=(), attachments=()):
    return Fake(created_at=datetime(2026, 9, 18, 14, 30, tzinfo=timezone.utc),
                clean_content=content, embeds=list(embeds), attachments=list(attachments),
                author=Fake(name="howitzer", id=769163831238328342))


# the author id is on the line, not only the name, because names get changed
line = deleted_line(message("see you at 17"))
assert line == "[2026-09-18 14:30] howitzer (769163831238328342): see you at 17", line
# a file survives its message: Discord serves the URL after the message is gone
assert deleted_line(message("", attachments=[Fake(filename="map.png", url="https://cdn/x")])) \
    .endswith("\n  [file] map.png https://cdn/x")
# an embed is content too, and a deleted bot card should not read as an empty message
assert "Op posted" in deleted_line(message("", embeds=[
    Fake(title="Op posted", description=None, fields=[])]))

print(">> ok")
