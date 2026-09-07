# Jarcord brand

The mark is the J+A ligature. One stroke unit governs everything.

Drawn by Fabian, turn 3, built from the Aperture direction: the version where the break
between the two terminals became a deliberate slot rather than a gap where the line ran out.

## The rule that matters

Stroke is 1u. Both terminals sit on one vertical axis with exactly 1u of white between
their edges. That slot is the signature and it must never close. Clear space is 1u on all
four sides.

## Files

| File | Use |
|---|---|
| `mark.svg` | `currentColor`, for inlining. What the site uses |
| `mark-black.svg` | `#16181D` on light |
| `mark-white.svg` | `#F6F5F2` on dark |
| `mark-amber.svg` | `#F0A736`, for ink grounds |
| `avatar-square.svg` | Ink ground, amber mark. The Discord application icon and the favicon |
| `avatar-circle.svg` | Amber disc, ink mark. How Discord crops it in the member list |
| `avatar-512.png` | 512px render of the square lock, ready to upload |
| `avatar-512-circle.png` | 512px render of the circle lock |

The avatars carry a shorter sweep and bump the stroke one step to 14, so the slot survives
at 32px. Do not swap the full sweep back in.

## Size ladder

96, 48, 32, 20. The stroke thickens slightly as it shrinks so the slot stays open. At 20 and
below the sweep goes first, because it turns to mush before the mark does.

The 32px member list avatar is the size that matters most, since that is where most people
meet the bot.

## Lockup

Primary reads Ja + rcord: the mark is the Ja, the word carries on. Mark sits 0.5u from the r.
Type is Space Grotesk Medium. Use the full word spelled out where the ligature would be
missed.

## Palette

| | Hex |
|---|---|
| Ink | `#16181D` |
| Amber | `#F0A736` |
| Paper | `#F6F5F2` |

Amber over Discord's blurple on purpose: the bot should read as its own thing inside the app
rather than part of it. Amber on black and the mono knockout are the only two icon locks.
Never amber on blurple.
