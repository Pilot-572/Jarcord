# ── Jarcord: Roblox lookup self-check (venv/Scripts/python test_roblox.py) ──
# ponytail: hits the real API, no mocks. The whole point is that a dead lookup
# and a missing username stop looking identical to the caller.
import asyncio

import cogs.profile as profile

# a real account resolves to its canonical name
assert asyncio.run(profile.resolve_roblox("Roblox"))[1] == "Roblox"
# a username nobody owns is None, which callers report as a typo
assert asyncio.run(profile.resolve_roblox("zzz_not_a_real_user_9182736")) is None

# an unreachable endpoint must raise, never return None
profile.ROBLOX_LOOKUP = "http://127.0.0.1:9/closed"
try:
    asyncio.run(profile.resolve_roblox("Roblox"))
    raise SystemExit(">> FAILED: an outage came back as 'no such user'")
except profile.RobloxDown:
    pass

print(">> ok")
