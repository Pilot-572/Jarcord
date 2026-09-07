"""Read-only usage report over a Jarcord database.

Answers the questions the market research could not: how often does a real
faction post ops, how many people RSVP, how many of those actually turn up,
which ticket kinds get used, how many members ever link a Roblox account.

Run it against the live copy on Nest:

    ssh pilot@hackclub.app 'cd /root/jarcord && venv/bin/python -' < docs/roc-usage-report.py

or locally against a copy:

    venv/Scripts/python.exe docs/roc-usage-report.py data/jarcord.db

Opens the database read-only. Prints counts and dates, never user ids,
Roblox names or ticket text.
"""

import sqlite3
import sys
from collections import Counter

DB = sys.argv[1] if len(sys.argv) > 1 else "data/jarcord.db"

conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row


def cols(table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def one(sql, *args):
    row = conn.execute(sql, args).fetchone()
    return row[0] if row else None


def show(label, value):
    print(f"{label:34s} {value}")


print(f"database: {DB}\n")

# ── Ops ──
print("OPS")
total = one("SELECT COUNT(*) FROM ops")
show("ops ever posted", total)
if total:
    show("closed", one("SELECT COUNT(*) FROM ops WHERE closed = 1"))
    show("first posted", one("SELECT MIN(created_at) FROM ops"))
    show("last posted", one("SELECT MAX(created_at) FROM ops"))
    weeks = conn.execute(
        "SELECT strftime('%Y-W%W', created_at) w, COUNT(*) n FROM ops GROUP BY w ORDER BY w"
    ).fetchall()
    show("weeks with at least one op", len(weeks))
    if weeks:
        show("ops per active week, average", round(total / len(weeks), 1))
        show("busiest week", f"{max(r['n'] for r in weeks)} ops")
    with_time = one("SELECT COUNT(*) FROM ops WHERE when_ts IS NOT NULL")
    show("ops with a parsed start time", f"{with_time} of {total}")
    if "notes" in cols("ops"):
        show("ops with notes", one("SELECT COUNT(*) FROM ops WHERE notes IS NOT NULL AND notes != ''"))
    if "thread_id" in cols("ops"):
        show("ops with a thread", one("SELECT COUNT(*) FROM ops WHERE thread_id IS NOT NULL"))

# ── Signups and attendance ──
print("\nSIGNUPS AND ATTENDANCE")
sc = cols("signups")
show("signup rows", one("SELECT COUNT(*) FROM signups"))
show("distinct people who ever RSVPed", one("SELECT COUNT(DISTINCT user_id) FROM signups"))
if "status" in sc:
    for r in conn.execute("SELECT status, COUNT(*) n FROM signups GROUP BY status ORDER BY n DESC"):
        show(f"  status {r['status']}", r["n"])
attend_col = "attended" if "attended" in sc else ("came" if "came" in sc else None)
if attend_col:
    marked = one(f"SELECT COUNT(*) FROM signups WHERE {attend_col} IS NOT NULL")
    show("rows with attendance recorded", marked)
    if marked:
        came = one(f"SELECT COUNT(*) FROM signups WHERE {attend_col} = 1")
        show("turned up", came)
        show("no-shows", one(
            f"SELECT COUNT(*) FROM signups WHERE {attend_col} = 0"
            + (" AND status = 'in'" if "status" in sc else "")))
        show("turnout rate", f"{round(100 * came / marked)}%")
    print("\n  per closed op: rsvp in / turned up")
    rows = conn.execute(
        f"""SELECT s.op_id,
                   SUM(CASE WHEN {'s.status = "in"' if "status" in sc else '1'} THEN 1 ELSE 0 END) rsvp_in,
                   SUM(CASE WHEN s.{attend_col} = 1 THEN 1 ELSE 0 END) came
            FROM signups s JOIN ops o ON o.id = s.op_id
            WHERE o.closed = 1 GROUP BY s.op_id ORDER BY s.op_id"""
    ).fetchall()
    for r in rows:
        print(f"    op {r['op_id']:>4}  {r['rsvp_in']:>3} in  {r['came']:>3} came")
    if rows:
        biggest = max(r["rsvp_in"] for r in rows)
        show("\n  biggest op by RSVP", biggest)
        show("  ops over the 25-person picker cap", sum(1 for r in rows if r["rsvp_in"] > 25))

# ── Members ──
print("\nMEMBERS")
pc = cols("profiles")
show("profiles", one("SELECT COUNT(*) FROM profiles"))
if "roblox_id" in pc:
    show("with a Roblox account linked", one("SELECT COUNT(*) FROM profiles WHERE roblox_id IS NOT NULL"))
for field in ("rank", "unit", "continent", "age_group", "play_hours", "heard_from"):
    if field in pc:
        vals = conn.execute(
            f"SELECT {field} v, COUNT(*) n FROM profiles WHERE {field} IS NOT NULL GROUP BY v ORDER BY n DESC"
        ).fetchall()
        if vals:
            show(f"  {field}", ", ".join(f"{r['v']}: {r['n']}" for r in vals[:9]))

# ── Everything else ──
print("\nOTHER FEATURES")
show("ratings", one("SELECT COUNT(*) FROM ratings"))
if one("SELECT COUNT(*) FROM ratings"):
    show("  people rated", one("SELECT COUNT(DISTINCT user_id) FROM ratings"))
    show("  people who rated", one("SELECT COUNT(DISTINCT rater_id) FROM ratings"))
    show("  average score", round(one("SELECT AVG(score) FROM ratings"), 2))
show("warnings", one("SELECT COUNT(*) FROM warnings"))
show("tickets", one("SELECT COUNT(*) FROM tickets"))
for r in conn.execute("SELECT kind, COUNT(*) n, SUM(status = 'closed') closed FROM tickets GROUP BY kind ORDER BY n DESC"):
    show(f"  {r['kind']}", f"{r['n']} opened, {r['closed']} closed")
if one("SELECT COUNT(*) FROM tickets"):
    show("  median hours to close", one(
        """SELECT ROUND(AVG((julianday(closed_at) - julianday(opened_at)) * 24), 1)
           FROM tickets WHERE closed_at IS NOT NULL"""))
show("members with activity tracked", one("SELECT COUNT(*) FROM activity"))
if one("SELECT COUNT(*) FROM activity"):
    show("  messages counted", one("SELECT SUM(message_count) FROM activity"))
    show("  busiest member", one("SELECT MAX(message_count) FROM activity"))
    show("  seen in the last 14 days", one(
        "SELECT COUNT(*) FROM activity WHERE last_seen > datetime('now', '-14 days')"))
show("applications rows", one("SELECT COUNT(*) FROM applications"))

print("\nSETTINGS SET")
for r in conn.execute("SELECT key FROM settings ORDER BY key"):
    print(f"  {r['key']}")

print("\nSCHEMA CHECK")
for table in ("ops", "signups", "profiles", "tickets", "warnings", "activity", "ratings", "settings", "applications"):
    try:
        show(f"  {table} has guild_id", "yes" if "guild_id" in cols(table) else "no")
    except sqlite3.Error:
        show(f"  {table}", "missing")
