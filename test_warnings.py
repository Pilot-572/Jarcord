# ── Jarcord: warnings query layer self-check (venv/Scripts/python -X utf8 test_warnings.py) ──
# ponytail: asserts only. /unwarn takes a bare number from a person; it must not delete
# another guild's warning, and a history must not show another guild's rows.
import os
os.environ["JARCORD_DB"] = ":memory:"   # before any project import
from cogs.warnings import add_warning, drop_warning, warnings_for

ROC, OTHER = 100, 200

w = add_warning(ROC, 5, 1, "late to the op")
add_warning(OTHER, 5, 2, "something elsewhere")

assert [r["reason"] for r in warnings_for(ROC, 5)] == ["late to the op"]
assert len(warnings_for(OTHER, 5)) == 1
assert drop_warning(OTHER, w) is False              # another guild's number does nothing
assert len(warnings_for(ROC, 5)) == 1               # and the row is still there
assert drop_warning(ROC, w) is True
assert warnings_for(ROC, 5) == []
assert drop_warning(ROC, w) is False                # gone means gone

print(">> ok")
