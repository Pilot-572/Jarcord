# ── Jarcord: rank ladder self-check (venv/Scripts/python -X utf8 test_ranks.py) ──
# ponytail: asserts only. Guards the ladder order, the NCO line, and that the panel
# members read names every rank exactly as the role is called.
from pathlib import Path

from cogs.ranks import ABBREV, NCO_FROM, RANKS, abbrev, is_nco, ladder_bar, step

assert len(RANKS) == len(ABBREV) == len(set(RANKS))

# no rank sits one below the bottom, and the ends of the ladder are walls
assert step(None, True) == RANKS[0]
assert step(None, False) is None
assert step(RANKS[0], False) is None
assert step(RANKS[-1], True) is None

# walking up then down visits every rank in order
rank = None
for expected in RANKS:
    rank = step(rank, True)
    assert rank == expected, (rank, expected)
for expected in reversed(RANKS[:-1]):
    rank = step(rank, False)
    assert rank == expected, (rank, expected)

# the card's bar always has one block per rank, filled up to where they stand
for i, rank in enumerate(RANKS):
    bar = ladder_bar(rank)
    assert len(bar) == len(RANKS), rank
    assert bar.count("▰") == i + 1, rank
assert abbrev(None) == "..." and abbrev(RANKS[0]) == ABBREV[0]

# the NCO marker starts exactly at Corporal 1
assert RANKS[NCO_FROM] == "Corporal 1"
assert not is_nco(None) and not is_nco("Specialist 2")
assert is_nco("Corporal 1") and is_nco("Staff Sergeant")

# the chain of command page names every rank and abbreviation as the ladder spells them,
# as a role token so it renders as a clickable pill once the role exists
text = (Path(__file__).parent / "panels" / "chain-of-command.json").read_text(encoding="utf-8")
for name, short in zip(RANKS, ABBREV):
    assert f"**{short}** {{role:{name}}}" in text, name

print(">> ok")
