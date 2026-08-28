# ── Jarcord: pre-commit sanity check (python -X utf8 check.py) ──
# ponytail: one script, no framework. Catches the two things that actually bite:
# AI-tell dashes in shipped text, and panel JSON that Discord will reject at post time.
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
BAD_DASHES = {chr(0x2014): "em dash", chr(0x2013): "en dash"}  # chr() so this file passes its own check
# Discord embed limits
LIMITS = {"title": 256, "body": 4096, "name": 256, "value": 1024}

errors = []


def scan_dashes():
    files = [*ROOT.glob("*.py"), *ROOT.glob("cogs/*.py"), *ROOT.glob("panels/*.json"),
             ROOT / "README.md", ROOT / ".env.example"]
    for f in files:
        if not f.exists():
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for ch, name in BAD_DASHES.items():
                if ch in line:
                    errors.append(f"{f.relative_to(ROOT)}:{n} contains an {name}")


def check_panels():
    for f in sorted(ROOT.glob("panels/*.json")):
        try:
            panel = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{f.name} is not valid JSON: {e}")
            continue
        sections = panel.get("sections", [])
        if len(sections) + bool(panel.get("banner")) > 10:
            errors.append(f"{f.name} has more than 10 embeds, Discord will reject the message")
        for s in sections:
            title = s.get("title", "?")
            for key, cap in (("title", LIMITS["title"]), ("body", LIMITS["body"])):
                if len(s.get(key) or "") > cap:
                    errors.append(f"{f.name} section '{title}' {key} is over {cap} chars")
            fields = s.get("fields", [])
            if len(fields) > 25:
                errors.append(f"{f.name} section '{title}' has more than 25 fields")
            for fl in fields:
                for key in ("name", "value"):
                    if len(fl.get(key) or "") > LIMITS[key]:
                        errors.append(f"{f.name} field '{fl.get('name')}' {key} is over {LIMITS[key]} chars")
            if not s.get("body") and not s.get("fields") and not s.get("image"):
                errors.append(f"{f.name} section '{title}' is empty")


scan_dashes()
check_panels()

if errors:
    print(">> FAILED")
    for e in errors:
        print("   " + e)
    sys.exit(1)
print(">> ok")
