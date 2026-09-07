# Jarcord web design system

Written from the built pages in this folder (`index.html`, `plus.html`, `privacy.html`,
`terms.html`). When a page and this file disagree, the page is the truth until this file is
updated.

## Visual theme and atmosphere

One thing per screen, at scale. The name fills the first viewport. After it, every screen is
one inset panel with soft corners holding one thing: a video, one Discord card, one
photograph, one table. Tiny mono labels sit in the panel corners like registration marks on a
proof. The type is a light grotesk set large, and the only colour on the page is inside the
screenshots and the RSVP buttons. The reference league is genesis.ai and
paulkalkbrenner.net, not a SaaS template.

## Colour palette and roles

Tokens live on `:root`, flip under `[data-theme="dark"]` and under the system dark preference
when no theme is saved. The media panels do not flip; they are dark in both.

| Token | Light | Dark | Role |
|---|---|---|---|
| `--ground` | `#F4F5F5` | `#0B0C0D` | Page ground |
| `--ink` | `#0E0F10` | `#F4F5F5` | Text, the solid button, the mark |
| `--muted` | `#6B6F73` | `#9AA0A5` | Secondary text, labels, hairlines' text |
| `--line` | `#D9DCDE` | `#26292D` | Hairlines, ghost button ring, the ticker's rules |
| `--pale` | `#E3EAEC` | `#15171A` | The setup panel and the free tier card |
| `--nav-bg` | ground at 82% | ground at 78% | The blurred sticky nav |
| `--chat` | `#313338` | same | Discord's chat surface, behind the open card and the record frames |
| `--deep` | `#1E1F22` | same | Discord's sidebar, behind the closed card |
| `--navy` | `#0F1626` | same | Footer and the Plus tier card |
| `--chartreuse` | `#DFFF00` | same | The studio swatch beside "Made by Chartreuse", once |

The three RSVP buttons keep Discord's own greens, greys and reds (`#248046`, `#4E5058`,
`#DA373C`) because they are the product's buttons, not the site's palette.

## Typography

- **Host Grotesk** 300, 400, 500 for everything set in words. Headings at 400, tracking
  -0.025em; the wordmark at 500, tracking -0.045em, `clamp(64px, 14.6vw, 228px)`.
- **Geist Mono** 400, 500 for labels, buttons, clocks, commands and prices: 12px, uppercase,
  tracking .06em on labels and .04em on buttons.

| Role | Size | Notes |
|---|---|---|
| wordmark | clamp(64px, 14.6vw, 228px), line height .9 | one line at every width |
| h1 (Plus page) | clamp(44px, 7vw, 112px) | |
| h2 | clamp(38px, 4.6vw, 66px), line height 1.02 | max 14ch inside a panel |
| h3 | 22px, weight 400 | record item captions |
| body | 17px / 1.5, max 42ch (46ch in the hero) | muted, or ink in the hero |
| label | 12px mono uppercase | corner labels, clocks, section names |
| button | 12px mono uppercase in a 36px pill with 8px corners | |

No bold above 500, no italic, no letter-spaced headings.

## Components

- **Nav.** Sticky, 64px, ground at 82% with a 12px blur, the mark and the name left, links
  and the theme switch right. On phones only "Plus", "Add to your server" and the switch stay.
- **Theme switch.** A 36px round button with a moon (light) or sun (dark). Saves to
  `localStorage.theme`; a head script applies it before paint; `html.switching` adds a 450ms
  colour transition while it flips.
- **Wordmark.** Seven letter spans and the RSVP chip between "Jar" and "cord". The chip is
  three real buttons on the chat colour; pressing one sets `aria-pressed` and updates the
  roster line under the hero. Letters rise in on load, the buttons pop after them, and the
  whole word recedes as you scroll away (scroll-driven, where supported).
- **Buttons.** `.btn` solid ink on ground, `.btn.ghost` transparent with a hairline ring;
  inside a `.dark` panel both go white. Hover lifts 1px.
- **Panel.** `margin: 16px; border-radius: 22px; padding: 40px; min-height: clamp(560px,
  90vh, 880px)`, a 12 column grid inside, `.top` labels on row one, `.art` on rows two and
  three, `.copy` bottom left. Variants: `.chat`, `.deep`, `.pale`, `.navy`, and `.media` with
  a `.bg` image or video under a bottom-heavy dark gradient. Four `.ticks` spans draw the
  corner marks.
- **Cards.** The open op card sits straight on `--chat` with a drop shadow; the closed card
  floats on the briefing-room photo with a 12px radius and a deep shadow. Both tilt up to 8
  degrees toward a fine pointer.
- **Record items.** Three `.item` figures: a `.frame` on the chat colour with a 4:3.1 ratio,
  then a mono number, an h3 and one paragraph. Images scale 3.5% on hover.
- **Ticker.** One mono line between hairlines, 42s loop, pauses on hover, one per page.
- **Setup rows.** Each row is a button: number, command, description; click copies the
  command and the number reads "Copied" for 1.2s. The payoff row sits under a 1px ink rule.
- **Tier cards (Plus page).** Two panels side by side, free on `--pale`, Plus on `--navy`,
  each with a mono price line, the name at 40px, a dash-marked list and the actions at the
  bottom. The comparison table and the pass list follow.
- **Footer.** A navy panel with the helicopter photo behind, the mark and "Jarcord for Discord"
  at display size, five links right, the studio credit and the Discord disclaimer below.

## Layout principles

- Inset everything: panels keep 16px from the viewport edge (8px on phones), sections 40px.
- 12 columns with `minmax(0, 1fr)` tracks and 24px gaps inside panels and section heads.
- Vertical rhythm: 96px to 120px between white sections, 64px on phones; inside a panel the
  copy sits at the bottom left and the art centres in the remaining rows.
- Splits alternate: art right then art left, then a three-up, then a full-bleed photo, then a
  table, then a footer. No two consecutive screens share a layout.

## Depth and elevation

Flat page, depth only on the objects: the open card's drop shadow, the closed card's deep
shadow, the chip's small shadow. Media panels darken toward the text with a gradient. No
glass, no glow.

## Motion

Reveal on entry for every section (opacity and a 28px rise with a 1.5% scale), corner ticks
drawing in, labels fading after, items and rows staggered by `--i`. The wordmark's letters
rise on load. Cards drift 6% through the viewport and tilt toward the pointer. The video
panel runs a clock and a 2px progress line. Everything but the muted loop goes still under
`prefers-reduced-motion: reduce`; the loop keeps playing because it is ambient and silent.

## Do and do not

Do: one thing per screen, real screenshots on Discord's colours, mono labels in corners,
light type at scale, the mark in `currentColor` so it follows the theme.

Do not: add an accent colour, round a panel past 22px, use a card grid, set a heading bold,
put pricing on the front page (it lives on `plus.html`), use an em dash, or claim a feature
the README does not describe.

## Responsive behaviour

- 1000px: panels stack art over copy; the setup rows drop under the heading; the three-up
  becomes one column; the footer links move under the wordmark.
- 720px: 8px insets, 20px panel padding, 16px corners, the wordmark at 12.2vw, nav trimmed
  to Plus, the action and the switch, the comparison table becomes labelled blocks.
- No horizontal scroll at 390px. Touch targets are 36px or taller.

## Agent prompt guide

"Add a section to the Jarcord site in its panel system: an inset panel with 22px corners and
40px padding on `--chat`, `--deep`, `--pale` or `--navy`, or a `.media` panel with a
photograph under the dark gradient; mono uppercase labels in the top corners; one h2 in Host
Grotesk 400 at clamp(38px, 4.6vw, 66px) bottom left with one muted paragraph under 42ch;
one object centred in the remaining rows; `.reveal` on the section; tokens only, no new
colours, no em dashes."
