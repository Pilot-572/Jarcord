# ── Jarcord: the ideas board (venv/Scripts/python -X utf8 test_ideas.py) ──
# ponytail: asserts only. The one thing that fails badly here is a typo in ideas.json
# found halfway through posting, with ten messages already in the channel and ten missing.
import os
os.environ["JARCORD_DB"] = ":memory:"   # before any project import, so tests never touch data/jarcord.db

from cogs.ideas import (BODY_MAX, TITLE_MAX, board_names, idea_embed, load_ideas,
                        problems)

# ── the shipped file has to be postable ──
data = load_ideas()
assert problems(data) == [], problems(data)
assert len(data["ideas"]) >= 10, len(data["ideas"])

# every idea renders, and Discord will accept every field
for idea in data["ideas"]:
    e = idea_embed(idea)
    assert e.title == idea["title"]
    assert e.description == idea["body"]
    assert e.timestamp is None          # a board is reference, not an event
    assert len(e) <= 6000, (idea["title"], len(e))

# titles are unique, so a vote count can be attributed to one idea
titles = [i["title"] for i in data["ideas"]]
assert len(set(titles)) == len(titles), titles

# ── the ping note has to survive .format(), which is the one way it can blow up mid-post ──
note = data["ping_note"]
assert "{mention}" in note, note
assert note.format(mention="<@1>").startswith("<@1>"), note
assert "{" not in note.format(mention="<@1>"), "a stray brace would raise on the real call"
assert problems({"title": "x", "ping_note": "y" * (BODY_MAX + 1),
                 "ideas": [{"title": "a", "body": "b"}]}) == ["ping note too long"]

# ── problems() catches what a hand edit gets wrong ──
assert problems({"title": "x", "ideas": []}) == ["no ideas"]
assert problems({"ideas": [{"title": "a", "body": "b"}]}) == ["no title"]
assert problems({"title": "x", "ideas": [{"body": "b"}]}) == ["idea 1: no title"]
assert problems({"title": "x", "ideas": [{"title": "a"}]}) == ["a: no body"]
assert problems({"title": "x", "ideas": [{"title": "y" * (TITLE_MAX + 1), "body": "b"}]}) == [
    f"{'y' * (TITLE_MAX + 1)}: title over {TITLE_MAX}"]
assert problems({"title": "x", "ideas": [{"title": "a", "body": "b" * (BODY_MAX + 1)}]}) == [
    f"a: body over {BODY_MAX}"]

# a tag is optional, and its absence is not a problem
assert problems({"title": "x", "ideas": [{"title": "a", "body": "b"}]}) == []
assert idea_embed({"title": "a", "body": "b"}).footer.text is None

# ── every board on disk has to be postable, not just the default one ──
assert "ideas" in board_names() and "op-ideas" in board_names(), board_names()
for name in board_names():
    b = load_ideas(name)
    assert problems(b) == [], (name, problems(b))
    assert "{mention}" in b["ping_note"], name
    assert "{" not in b["ping_note"].format(mention="<@1>"), name
    names = [i["title"] for i in b["ideas"]]
    assert len(set(names)) == len(names), (name, names)

# a board that is not on disk is refused rather than turned into a path
try:
    load_ideas("../../etc/passwd")
    raise AssertionError("should have refused")
except KeyError:
    pass

print(">> ok")
