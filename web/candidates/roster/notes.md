# Roster candidate: notes

## Design read

Reading this as: a persuasion landing page for young faction leaders who already read esports roster pages and match scoreboards daily, with a serious club's official-site language, leaning toward plain CSS grid, a wide grotesk for headings, condensed jersey numerals, one team colour on white.

## Dials

- DESIGN_VARIANCE 6. Rows and boards are a rigid, recognisable topology; asymmetry comes from column spans (7/5, 4/8), not from tilt or chaos. A club site is composed, not artsy.
- MOTION_INTENSITY 3. One authored moment: the turnout numerals on the closed op settle into place once when they enter view. Hover and press states are colour and a 1px push. Nothing else moves.
- VISUAL_DENSITY 5. Rows carry real data (commands, limits, prices), so the page is denser than an airy gallery, but each board has room around it.

## Direction contract

THESIS. Jarcord is the team's record: who signed up, who showed, who got promoted. The page is the roster page and the post-match board, read the way a squad reads a scoreboard: numbers first, words confirm.

OWN-WORLD. An esports club's official site. White ground, near-black ink, one team red that owns the hero field and the turnout board, grey hairlines. Wide grotesk headings, condensed jersey numerals with tabular figures, a clean sans for text, system mono only where a command is code. Sharp corners everywhere (2px). Dark screenshots sit in a near-black plate with an inner hairline and an offset, blurred shadow, so the Discord card reads as a framed photo of the product, not as page UI.

STORY. Row one: the open op, six signed up, buttons still live. Row two: the closed op, eight said they were coming, seven turned up, one did not; the board settles. Row three: the promotion notice and the profile read that record back. Then the six commands that set it up, in order. Then the two plans. Then the footer.

FIRST VIEWPORT. Team red field with the nav on it. Left: the headline states the mechanism in two lines, one sentence under it, the primary action in white and one secondary link. Right: the real open op card in its black plate, the largest object on the screen. No numerals in the hero; the hero stays at four text elements as the brief requires. The jersey numerals belong to the board after the match, one scroll down.

FORM. Six sections, six layout families: bar (nav), split text left and figure right (hero), full-bleed board band with numerals and figure, then two asymmetric figures 7/5 (the record), sticky heading beside a lineup of rows 4/8 (setup), full-width comparison table with a two-value head (plans), four-column footer on near-black.

## Palette

- team red #C0122D, white on it 6.24:1, tint #FFD9DE on it 4.82:1
- ink #141416 on white 18.4:1
- muted #5B5B63 on white 6.73:1, on the grey band 6.07:1
- grey band #F3F3F4, hairline #E2E2E5
- plate #16161A with a rgba(255,255,255,.08) inner hairline
- footer text #C9C9CE on ink 11.15:1, footer muted #9A9AA2 on ink 6.59:1
- chartreuse #DFFF00 once, footer credit swatch

## Type

- Archivo (variable, wdth 62 to 125, wght 400 to 900): headings at wdth 118 wght 800, jersey numerals at wdth 62 wght 900, tabular figures
- Schibsted Grotesk 400, 500, 600 for text, 17px body, measure 60 to 68ch
- system monospace for commands only, because commands are code

Both families verified against fonts.googleapis.com before use (200, wdth axis present in the Archivo payload; Schibsted Grotesk 400 to 700 served).

## Motion, and why the stills show the pre-settle width

The one authored moment: when the closed op board enters view, the two turnout numerals compress from Archivo width 86 to their jersey width 62 over 0.9s with an exponential ease-out, the second one 140ms after the first. Nothing fades and nothing moves off its baseline, so every frame is a legible board.

That is deliberate. A full-page capture never scrolls, so an entrance that starts at opacity 0 leaves the board empty in desk-full and phone-full; the first render proved it. The settle now starts from a visible state, which means the two full-page stills show the numerals slightly wider than their final cut. In a browser they end at width 62. Under prefers-reduced-motion: reduce and without JS they are at 62 from the start.

## Taste-skill section 14, box by box

- Brief inference declared: yes, top of this file.
- Dial values explicit: 6 / 3 / 5, reasons above.
- Design system: none, plain CSS; aesthetic labelled as a club's official site.
- Redesign mode: not a redesign. The two earlier attempts were read and avoided (no graphite, no tan or olive, no paper, no Big Shoulders or Barlow, no dark page with one acid accent, no centred column).
- Zero em or en dashes: grep prints 0 for index.html and for this file.
- Page theme lock: one light page. The red field, the red board and the near-black footer are colour bands of the same theme, not theme flips.
- Colour consistency lock: one accent, the team red, used for the two bands, the action button on white, links, focus rings and selection. Chartreuse appears once, as the footer credit swatch.
- Shape consistency lock: 2px everywhere (buttons, plates, code chips, swatch).
- Button contrast: white button with ink text on red (18.4:1), red button with white text on the grey band (6.24:1 on white, 5.63:1 on the band).
- CTA wrap: "Add to your server" is nowrap and fits at 1440 and 390.
- Form contrast: no forms.
- Serif discipline: no serif.
- Premium-consumer palette: not that brief, and no cream, tan, beige, olive, coyote, purple or blurple anywhere.
- Italic descenders: no italics.
- Hero fits the viewport: two-line headline at 1440 (measured 92px tall at 46px line-height), 19-word sentence, action and link visible, field is exactly 900px tall at 1440x900.
- Hero top padding: 48px, content vertically centred against the plate.
- Hero stack: four text elements (headline, sentence, action, link). The figure has no caption.
- Eyebrow count: zero on the page.
- Split-header ban: the setup section is heading left, real content (the lineup) right, which the rule allows. No section pairs a headline with a floating explainer.
- Zigzag cap: two image-and-text splits in a row (hero, board), then the two-figure row breaks it.
- Duplicate CTA intent: one label, "Add to your server", in the nav, the hero and the free plan column.
- Logo wall: none.
- Bento diversity: no bento.
- Trusted-by wall: none, no invented logos or numbers.
- Copy self-audit: every string re-read. Every number on the page is from a screenshot, the README or PRODUCT.md (6 attending, 7 attended, 1 no-showed, 8 said they were coming, 5 attended 0 no-showed, 6 signed up 4 attended, 5 ops, 60 days, 10 ranks, 3 months, 9, 25, 55, 4.99 EUR).
- Motion motivated: one transition, reason above.
- Marquee: none.
- Nav on one line, 68px tall at both widths.
- Section layout repetition: bar, split, band with numerals and figure, two asymmetric figures, sticky heading plus lineup, comparison table, footer. No two alike.
- Bento cell count: no bento.
- Long lists: the seven commands are an ordered lineup with one hairline above each row, because the sequence is the content. The plan comparison is a real table with a two-value head and collapses to labelled blocks on the phone.
- Real images: five real screenshots, each in a designed plate. No div-built Discord UI, no decorative SVG, no icons at all.
- No pills on images, no photo credits, no version footers, no micro-meta sentences, no hero bottom strip, no floating corner text, no progress bars, no locale strips, no scroll cues, no version labels, no section numbers, no decorative dots (the chartreuse swatch is the studio credit the brief allows once).
- No border-top plus border-bottom on rows: one border-top per row in the lineup and the table.
- Content density: nine table rows, seven command rows, sentences at or under 25 words except the picker explanation (34 words, kept because it is the mechanism).
- Quotes: none.
- Motion claimed equals motion shown: MOTION_INTENSITY 3, one transition, present.
- GSAP: not used, not allowed.
- No scroll listener: IntersectionObserver only, disconnected after the first hit.
- Reduced motion: the transition and smooth scrolling live inside prefers-reduced-motion: no-preference.
- Dark mode: the page commits to one light look with explicit backgrounds, per the brief's static site and the colour strategy.
- Mobile collapse: explicit at 880px (stack every grid) and 720px (gutter, type, nav sizes, lineup and table blocks). scrollWidth at 390 is 390.
- Viewport stability: min-height 100dvh on the field, never 100vh.
- useEffect cleanup: no React.
- Empty, loading, error states: a static page has none; the observer has a no-support fallback that shows the board settled.
- Cards omitted: no cards. Plates hold screenshots, rows and tables hold text.
- Icons: none.
- Client-leaf motion components: not applicable.
- AI tells: no Inter, no purple, no three equal cards, no invented names (every name on the page is in a real screenshot), no "Acme", no "Quietly in use at".
- Core web vitals: two font families (one variable file plus three static weights), five PNGs with width and height attributes, no scripts beyond 15 lines.
- One design system: plain CSS only.

## Detector, after fixes

First run: 10 cramped-padding warnings, all because the detector does not read padding-block. Replaced every padding-block with padding longhand; no layout change (scroll heights identical before and after: 4742 and 6474).

Second run, 2 findings remain and stay:

- cramped-padding on div.board and section.plans: "children flush against bg on right/left (no inset)". Both are full-bleed colour bands whose only child is a .wrap carrying the 24px (20px on phone) inline gutter, so text never touches an edge. The band needs zero inline padding to bleed; moving the gutter onto the band would put a second gutter inside it.

Dash grep on index.html: 0. Phone scrollWidth: 390. Desk scrollWidth: 1440.

## Measured in a browser, final file

- prefers-reduced-motion: no-preference: numerals at width 86% before the board enters, 70.5% 120ms after it enters, 62% settled. Board class after entry: "board in".
- prefers-reduced-motion: reduce: 62% before, during and after. No console errors in either mode.
- Focus on the hero action: 3px white outline on the red field. Hover on it: the tint #FFD9DE.
- Body lede measure: 62ch. Hero text elements: 4. Nav: 68px. Field at 1440x900: 900px, so the action sits in the first viewport.
