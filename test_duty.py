# ── Jarcord: duty rota + schedule self-check (venv/Scripts/python -X utf8 test_duty.py) ──
# ponytail: asserts only. Guards the three things that fail silently and only show up
# a day later: a slot that resolves to the wrong side of noon, a rota that drifts after
# downtime, and a chore that reads as done when it isn't.
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from cogs.duty import chore_lines, next_run, on_duty, todays_slot

TZ = "Europe/Bucharest"


def ts(y, m, d, hh, mm=0) -> int:
    return int(datetime(y, m, d, hh, mm, tzinfo=ZoneInfo(TZ)).timestamp())


# ── todays_slot: the bug that made the chore list fire just after midnight ──
# before noon, today's slot is still ahead
assert todays_slot(ts(2026, 9, 4, 10), 12 * 60, TZ) == ts(2026, 9, 4, 12)
# after noon, it is the same slot, now behind us
assert todays_slot(ts(2026, 9, 4, 15), 12 * 60, TZ) == ts(2026, 9, 4, 12)
# one minute past midnight must not resolve to yesterday
assert todays_slot(ts(2026, 9, 4, 0, 1), 12 * 60, TZ) == ts(2026, 9, 4, 12)
# so "has today's slot happened" reads correctly on both sides of it
assert ts(2026, 9, 4, 10) < todays_slot(ts(2026, 9, 4, 10), 12 * 60, TZ)
assert ts(2026, 9, 4, 15) > todays_slot(ts(2026, 9, 4, 15), 12 * 60, TZ)

# ── next_run: the recurring advert ──
# daily at noon, asked in the morning, lands today
assert next_run(ts(2026, 9, 4, 10), 12 * 60, 1440, TZ) == ts(2026, 9, 4, 12)
# asked in the afternoon, lands tomorrow
assert next_run(ts(2026, 9, 4, 13), 12 * 60, 1440, TZ) == ts(2026, 9, 5, 12)
# exactly on the slot rolls forward: strictly after, so one tick cannot double-post
assert next_run(ts(2026, 9, 4, 12), 12 * 60, 1440, TZ) == ts(2026, 9, 5, 12)
# twice a day from noon means the next one is midnight
assert next_run(ts(2026, 9, 4, 13), 12 * 60, 720, TZ) == ts(2026, 9, 5, 0)
# every four hours stays inside the day
assert next_run(ts(2026, 9, 4, 13), 12 * 60, 240, TZ) == ts(2026, 9, 4, 16)
# whatever the cadence, the answer is always in the future
for every in (60, 240, 720, 1440, 10080):
    for hour in (0, 12, 23):
        now = ts(2026, 9, 4, 13, 37)
        assert next_run(now, hour * 60, every, TZ) > now, (every, hour)

# ── on_duty: derived from the date, so downtime cannot desync it ──
epoch = date(2026, 9, 4)
rota = [11, 22, 33]
assert on_duty(rota, date(2026, 9, 4), epoch) == 11
assert on_duty(rota, date(2026, 9, 5), epoch) == 22
assert on_duty(rota, date(2026, 9, 6), epoch) == 33
assert on_duty(rota, date(2026, 9, 7), epoch) == 11        # wraps
assert on_duty(rota, date(2026, 10, 4), epoch) == 11       # 30 days on, still valid
# a week each: the same person all week, the next one on day 8
assert on_duty(rota, date(2026, 9, 10), epoch, 7) == 11
assert on_duty(rota, date(2026, 9, 11), epoch, 7) == 22
# a date before the epoch (clock wrong, rota re-set) must not raise or index badly
assert on_duty(rota, date(2026, 9, 1), epoch) in rota
# degenerate inputs
assert on_duty([], date(2026, 9, 4), epoch) is None
assert on_duty([11], date(2026, 12, 25), epoch) == 11
assert on_duty(rota, date(2026, 9, 5), epoch, 0) == 22     # rotate_days 0 behaves as 1

# ── chore_lines: done means done ──
clear = chore_lines(advert_due=False, ops_ahead=2, needs_closing=0,
                    stale_tickets=0, unverified=0)
assert [key for key, _, _ in clear] == ["advert", "ops", "close", "tickets", "verify"]
assert all(done for _, done, _ in clear)

busy = chore_lines(advert_due=True, ops_ahead=0, needs_closing=3,
                   stale_tickets=1, unverified=4)
assert not any(done for _, done, _ in busy)
text = dict((key, sentence) for key, _, sentence in busy)
# an open chore says what to do, not just what is wrong
assert "/op create" in text["ops"]
assert "/op close" in text["close"]
# singular and plural both read properly, since this goes in front of the whole unit
assert "1 ticket unclaimed" in text["tickets"]
assert "4 members" in text["verify"]
assert "3 ops started" in text["close"]
one = dict((k, s) for k, _, s in chore_lines(False, 1, 1, 0, 1))
assert "1 op on the board" in one["ops"]
assert "1 op started" in one["close"]
assert "1 member never" in one["verify"]

print(">> ok")
