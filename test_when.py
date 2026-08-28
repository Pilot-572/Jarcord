# ── Jarcord: op time parsing self-check (venv/Scripts/python test_when.py) ──
# ponytail: asserts only, no framework. Guards the one thing that silently ships
# an op at the wrong hour: a wall clock time typed by a human is NOT UTC.
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from cogs.ops import parse_when

BUC = ZoneInfo("Europe/Bucharest")  # UTC+3 in summer, UTC+2 in winter


def utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M")


# a time typed in Bucharest is stored three hours earlier in summer
assert utc(parse_when("2026-08-29 21:00", BUC)) == "2026-08-29 18:00"
# and two hours earlier in winter, which a fixed offset would get wrong
assert utc(parse_when("2026-12-20 21:00", BUC)) == "2026-12-20 19:00"
# UTC in, UTC out
assert utc(parse_when("2026-08-29 21:00", ZoneInfo("UTC"))) == "2026-08-29 21:00"
# every documented format lands on the same instant
assert parse_when("29.08.2026 21:00", BUC) == parse_when("2026-08-29 21:00", BUC)
# DD.MM with no year fills in a year, and never lands in the past
assert parse_when("29.08 21:00", BUC) >= int(datetime.now(BUC).timestamp())
# anything else stays free text with no reminder
for junk in ("21:00", "9 pm", "29/08 21:00", "tomorrow-ish"):
    assert parse_when(junk, BUC) is None, junk

print(">> ok")
