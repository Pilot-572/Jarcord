# Specimen candidate

## Design read

Reading this as: a persuade landing page for young faction leaders on Discord, in the language of an interactive type specimen, leaning toward hand-written CSS, one grotesk with a width axis, a near-white ground and a single foundry red.

## The three dials

- DESIGN_VARIANCE 6. The specimen grammar is strict (baseline grid, measure, flat surfaces) but the composition is asymmetric: object right, labels tiny, headline enormous, a cascade for the commands. Higher would fight the grid; lower would be a template.
- MOTION_INTENSITY 3. One authored motion, the scrub, driven by the visitor's hand and nothing else. No entrances, no loops.
- VISUAL_DENSITY 3. Generous negative space around a few objects. The plans table is the densest region and it is still airy.

## Direction contract

THESIS. The op card is the letterform. A specimen shows one glyph at enormous scale and names its parts in tiny labels; this page shows the op card at scale and names what each part does. The visitor learns the mechanism (post, then close with who turned up) by studying one object.

OWN-WORLD. Cool near-white ground (#F4F5F7), ink (#101113), one foundry red (#C8311C) that marks the control and the active state and nothing else. Archivo across its width axis: wide and heavy for the headline and plan names, normal for text. Fragment Mono for commands and the readout. Hard corners everywhere. No shadows, no gradients, no ornament. Hairlines organise, they never decorate.

STORY. Posted, then closed. The slider scrubs the card from the open state (RSVP buttons, six attending) to the closed state (turned out: 7 attended, 1 no-showed). The readout counts signed up, attended and no-showed as the visitor scrubs. Below, the record section shows what reads from that closed card: the promotion notice and the profile. Then the six commands that set it up, then the two plans.

FIRST VIEWPORT. Headline states the mechanism in two lines. One sentence and the primary action sit left; the card on its dark plate with the slider under it sits right; the readout and part labels sit beside. A visitor who never touches the slider sees the open card, reads the headline and can press the action.

FORM. 12 column grid with minmax(0, 1fr) tracks. Six sections, six layout families: one-line nav; object with control and labels; captioned mosaic (one large, two stacked); stepped cascade; comparison table; three-part footer band.

## Taste-skill section 14, box by box

- Brief inference declared: yes, the design read above.
- Dial values explicit and reasoned: yes, 6 / 3 / 3 with reasons above.
- Design system: none. Hand-written CSS on a 12 column grid, labelled honestly as a type specimen world.
- Redesign mode: not a redesign. The two earlier attempts were read as what to avoid, nothing was preserved from them.
- Zero em dashes: `grep -c` for both dash characters prints 0. Commas, full stops and colons throughout, including alt text.
- Page theme lock: one light theme, `color-scheme: light`, explicit ground on html and body. The dark plates are frames for dark screenshots, not a section flip.
- Colour consistency lock: one accent, #C8311C, used on the slider thumb and fill, the active end label, the active readout value and the active part names. Nowhere else. Chartreuse appears once, as the footer swatch.
- Shape consistency lock: all sharp. Buttons, plates, thumb, swatch, table, zero radius everywhere.
- Button contrast: ink #101113 on ground #F4F5F7 is 17.3:1 for the primary action; ground text on ink the same. Secondary link is ink on ground.
- CTA wrap: "Add to your server" is `white-space: nowrap` and one line at 1440 and 390.
- Form contrast: the one control is the range input. Accent thumb on ground 4.9:1, fill on hairline track, focus ring accent 2px. The end buttons are #61666E on ground, 5.3:1.
- Serif discipline: no serif.
- Premium-consumer palette: not that kind of brief, and no cream, tan, olive or coyote anywhere. Ground is a cool near-white.
- Italic descender clearance: no italics.
- Hero fits the viewport: at 1440x900 the headline is two lines (measured at 1440, 1280, 1024 and 768), the sentence is 19 words, the action sits at y 424 to 472, the slider ends at y 858 open and 886 closed.
- Hero top padding: 36px under a 68px nav. The headline starts at y 104.
- Hero stack discipline: headline, one sentence, primary action plus one secondary link. No eyebrow, no tagline, no trust strip. The readout and part labels are the specimen's labels, tied to the slider, not hero copy.
- Eyebrow count: zero. No `uppercase`, no letter-spaced labels.
- Split-header ban: every section heading is stacked with its lede underneath, max 58ch.
- Zigzag cap: one image-and-text split (the hero). The record is a captioned mosaic, not a split.
- Duplicate CTA intent: one label for the add intent, "Add to your server", in the nav and the hero. Docs appears as a nav link and a footer link with the same label. The hero's secondary is an in-page anchor with a different intent.
- Logo wall: none, none invented.
- Bento diversity: no bento.
- Trusted-by: none.
- Copy self-audit: every string re-read. Sentence case, product terms (op, faction, member, officer, the record), state words (posted, closed, attended, no-showed, filed). "Jarcord+ is not on sale yet" stays honest to PRODUCT.md.
- Motion motivated: the scrub crossfades two real states and counts the readout; it is the mechanism the headline states. Hover and press are one shade and one pixel. Nothing else moves.
- Marquee: none.
- Nav one line, 68px.
- Section-layout repetition: nav line; object plus control plus labels; captioned mosaic; stepped cascade; comparison table; three-part footer band. Six sections, six families.
- Bento cell count: no bento.
- Long lists: seven commands are a stepped cascade plus a finale, not a hairlined list. The plans table has eight rows with one hairline per row, which is what a comparison table is.
- Real images: the five PNGs are the only imagery; four are used (op-open, op-closed, rank, profile). Nothing is mocked in HTML.
- No pills on images: the state stamp sits in the plate's band under the image, on my frame, not on the pixels.
- No photo-credit captions: captions name the field and its value.
- No version footers.
- No micro-meta sentences.
- No hero-bottom decoration strip. The slider hint "Drag to close the op" names the control's action.
- No floating corner text.
- No progress bars.
- No locale strips.
- No scroll cues.
- No version labels.
- No section numbering.
- No decorative dots. The footer swatch is the studio credit the brief allows once.
- No border-t plus border-b rows: table rows carry one top hairline each.
- Content density: eight table rows, seven commands, three captions. Ledes 19 to 40 words; the 40-word one is the mechanism and earns it.
- Quotes: none.
- Motion claimed equals motion shown: MOTION_INTENSITY 3, one scrub, present.
- GSAP: none, not allowed.
- No scroll listeners: the only listeners are `input` on the range and `click` on the two end buttons.
- Reduced motion: `--t` snaps to 0 or 1 at the halfway point, the end buttons jump instead of tweening, smooth scroll is off, press translate is off. Verified with Playwright's reduced_motion emulation.
- Dark mode: single committed light theme by decision, explicit colours everywhere.
- Mobile collapse: declared per section at 719px and below. 390 renders at scrollWidth 390.
- Viewport stability: no full-height hero, no 100vh anywhere.
- useEffect cleanup: no React. The tween cancels its frame on new input.
- Empty, loading, error states: the page has one control and no data fetch; the readout's "not yet" is its empty state for attended and no-showed before close.
- Cards omitted: no cards. Plates frame screenshots; everything else is spacing and hairlines.
- Icons: none.
- Motion isolated: one script block at the end of the body.
- AI tells: no Inter, no purple, no three equal cards, no invented names or numbers, no "trusted by".
- Core Web Vitals: two font families by link with display swap, four PNGs totalling 130 KB with width and height attributes, no scripts beyond 80 lines.
- One design system: hand-written CSS only.

## Detector output after fixes

`impeccable detect --json index.html` returns one finding:

- `buried-raster`, warning: the closed op card `<img>` sits at opacity 0 in the default state. It stays. It is the far end of the crossfade and reaches the screen the moment the visitor scrubs; the same PNG is also shown at full opacity in the record section. Removing it would remove the mechanism.

Dash grep (`grep -c` for em and en dash bytes): 0.
Watermark scan on index.html and notes.md: clean.

## Render facts

- 1440x900: scrollWidth 1440, page height 5034, hero slider fully visible in both states.
- 390x844: scrollWidth 390, page height 6817.
- Headline is two lines at 1440, 1280, 1024 and 768.
