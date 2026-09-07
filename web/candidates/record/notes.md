# Candidate: the record

## Design read

Reading this as: a persuasion landing page for young leaders of player-run military factions on Discord, in the visual language of a modern identity document and the register behind it, leaning toward a committed deep-field colour, a precise grotesk and machine-set data lines.

## Dials

- DESIGN_VARIANCE 6. A register is ordered. The asymmetry comes from the spine (a left rail and a hanging index), the straddling first entry and the stamp, not from scattered layout.
- MOTION_INTENSITY 3. One authored moment, the stamp landing. Hover and press states are small and physical. Nothing loops.
- VISUAL_DENSITY 5. An identity document is denser than an airy landing page. Data lines carry real numbers from the screenshots; the copy stays short.

## Direction contract

THESIS. Jarcord is the record itself, so the page is a register page: the open op is the first entry, closing it files attendance, the promotion and the profile read from the same lines. Every screenshot is an entry with a machine-set data strip beneath it.

OWN-WORLD. Modern identity documents and the register a serious organisation keeps: deep petrol polycarbonate (#0B3B50) as the field, a cool white data page (#F3F6F8) as the ground, ruled entry lines, tabular numerals, one stamp. Not paper, not military, not a command board.

STORY. Top to bottom: the op posted (hero), the op closed with who came (stamped), the promotion and the profile that read from it, the six commands that start a record, the two plans, the footer. Ops sit newest first (Op 10 open above Op 7 closed).

FIRST VIEWPORT. Headline states the mechanism in eight words. One sentence with the approved claim. Primary action beside the headline, one secondary link. The open op card is the dominant object, framed as entry one, straddling the edge of the field onto the data page. No stack of cards.

FORM. Schibsted Grotesk for text and display, Azeret Mono for data lines and commands, tabular numerals everywhere a number appears. State is a mark plus a word: filled square attended, empty square no-showed, chevron promoted, triangle warned, and a stamp for filed. Radius 4px everywhere. Field owns hero, setup and footer (about half the surface); ground owns the record and the plans.

## Palette and type

- Field #0B3B50 (hover #0E4A63, footer #072C3D). Ground #F3F6F8. Ink #0F1F27, secondary ink #4A6270 (5.9:1 on ground). On the field: white and #B7D0DB (7.4:1). Rules #C4D3DA on ground, white at 16 percent on field. Bezel #0E1A20. Chartreuse #DFFF00 once, as the footer swatch.
- Schibsted Grotesk 400/500/600/700 for text and display. Azeret Mono 400/500 for data strips, commands, the stamp and the plan prices. Tabular numerals on those roles only: on Schibsted the tnum feature also widens full stops and commas, so it stays off body text.
- Both families verified on Google Fonts with curl before use (HTTP 200, weights present).

## Section layout families

1. Nav: single bar on the field.
2. Hero: split, copy top left, the op card bottom right straddling the field edge onto the ground, data strip on the ground.
3. The record: spine. Sticky index rail on the left, entries hanging to the right: one image plus text with the stamp, then a paired row of two unequal frames with a paragraph under each.
4. Set up: heading stacked over a two column, three row ruled command list flowing down then across, then one full width closing row with the action.
5. Plans: comparison table in eight columns, pass prices in a two by two block beside it.
6. Footer: three column on the deep field.

## Ritual

The stamp. When the closed op entry comes into view (IntersectionObserver, threshold 0.6, disconnected after the first hit) the Filed stamp lands: scale 1.3 to 1 and opacity 0 to 1 over 420ms on an exponential ease out, rotated 6 degrees. The hero secondary link scrolls to that entry, so pressing it triggers the same landing. Under reduced motion the stamp is simply present. Without JavaScript it is present. The full page capture in the render script never fires the observer, so shots/desk-stamp.png is an extra viewport capture with the stamp landed.

## Taste pre-flight, section 14, box by box

- Brief inference declared: yes, top of this file.
- Dial values explicit and reasoned: yes, 6 / 3 / 5.
- Design system: none applies. Aesthetic labelled honestly as an identity document and register world, hand written CSS.
- Redesign mode: not a redesign, the two earlier attempts were rejected and nothing from them is reused.
- Zero em dashes: grep prints 0 for the page and for this file.
- Page theme lock: one palette, deliberately one field colour and one ground alternating by section as the owner direction asked. No section changes hue or family.
- Colour consistency: one accent, the field colour, used identically everywhere. Chartreuse appears once as the credit swatch.
- Shape consistency: 4px radius on frames, buttons and the stamp, 2px on images inside frames and the swatch.
- Button contrast: white button with field text 12:1, hover 9.6:1. Nothing white on white.
- CTA wrap: "Add to your server" is one line at 1440 and at 390 (white-space nowrap, measured).
- Form contrast: no forms on the page.
- Serif discipline: no serif.
- Premium consumer palette: not that kind of brief, and no cream, tan, beige or brass anywhere.
- Italic descenders: no italics.
- Hero fits the viewport: headline two lines at 48px, sentence 19 words on two lines, action bottom at 434px of 900, card fully visible (image bottom 791px).
- Hero top padding: 40px on the grid plus 56px on the copy, headline starts at 164px.
- Hero stack: headline, one sentence, one primary action, one secondary link. Four elements, no tagline, no trust strip.
- Eyebrow count: zero.
- Split header: none. Every section heading stacks its lead beneath it.
- Zigzag: one image and text split (the closed op), then a paired row, then a list. No three in a row.
- Duplicate CTA intent: one label, "Add to your server", in nav, hero and after setup.
- Logo wall: none.
- Bento diversity: no bento.
- Trusted by wall: none; ROC is named in a footer sentence, as permitted.
- Copy self audit: every visible string re-read. Product voice, sentence case, no first person, no exclamation marks, no banned vocabulary, no "only".
- Motion motivated: the stamp marks an entry as filed, which is the mechanism the product sells. Hover and press states are feedback.
- Marquee: none.
- Navigation one line, 68px tall. Docs and Pricing hide below 400px so the bar stays one line with the action.
- Section layout repetition: six sections, six families, listed above.
- Bento cell count: no bento.
- Long lists: the seven commands are a two column ruled list plus a separated closing row; the comparison is an eight row table, which the brief asked for.
- Real images: the five screenshots are the only imagery, framed, never rebuilt from divs.
- Pills or labels over images: none. Data strips sit below the frames.
- Photo credit captions: none.
- Version footers: none.
- Micro meta sentences under eyebrows: no eyebrows.
- Decoration strip at hero bottom: none. The hero data strip carries the op number, state and count from the screenshot.
- Floating top right sub text: none.
- Progress bars with tracks: none.
- Locale or weather strips: none.
- Scroll cues: none.
- Version labels in hero: none.
- Section numbering eyebrows: none. The command numbers are the order the commands are run in.
- Decorative dots: none. The marks are squares, a chevron and a triangle, each paired with a word.
- border top plus border bottom on every row: rows carry one rule each.
- Content density: the longest sub paragraph is the record lead at 39 words, which quotes the mechanism. Everything else is under 25 words.
- Quotes: none.
- Motion claimed equals motion shown: yes, the stamp lands and hover and press states move.
- GSAP: not used, banned by the brief.
- No window scroll listener: IntersectionObserver only.
- Reduced motion: transitions and the stamp animation are off, the stamp shows, smooth scroll is off.
- Dark mode tokens: single committed palette by the owner decision, no scheme switch.
- Mobile collapse explicit: every grid has its 860px and 400px rules in the stylesheet.
- Viewport stability: min-height uses 100dvh, and only on the hero grid.
- useEffect cleanup: no React. The observer disconnects after its one hit.
- Empty, loading, error states: a static page with no data fetching, nothing to load or fail.
- Cards omitted: no cards. Frames hold screenshots, rules hold rows.
- Icons: no icon library (banned by the brief). Four authored geometric marks in one stroke weight, each next to its word.
- Motion isolated in client components: no framework.
- AI tells: no Inter, no purple, no three equal cards, no invented names or numbers (every name and count is read off a screenshot).
- Core web vitals: one HTML file, two font families over one link, five PNGs totalling about 240KB with width and height attributes.
- One design system: hand written CSS throughout.

## Detector

Round one, before fixes: two low contrast warnings (white and #B7D0DB read against the body ground because the field colour lived on a gradient alone), one cramped padding warning (index list children flush against the list rule), three advisories for a hairline border paired with a wide shadow on the frames.

Fixes: the field colour is now a background-color on every on-field section so the pairs resolve; the index rule moved from the list onto each link; the frames dropped the hairline and keep the offset shadow plus a one pixel inset highlight. A second pass caught a real bug the detector surfaced as cramped padding: a padding shorthand on the hero grid had wiped the container horizontal padding, so the headline sat 32px left of the wordmark; fixed with longhands.

Final run: 0 findings. Dash grep: 0. Phone scroll width 390 of 390. Fifth screenshot, shots/desk-stamp.png, shows the stamp landed at 1440 since the full page capture cannot trigger the observer.
