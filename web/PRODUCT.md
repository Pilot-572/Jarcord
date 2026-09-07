# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

delegated: static HTML and CSS in this folder, one file per page, Google Fonts by link, no build step. The page is served as static files (GitHub Pages or any host), so nothing may depend on a server.

## Users

Primary: the leader or officer of a player-run military faction on Discord. Today that is Rapid Ops Company (ROC), a BRM5 faction on Roblox; next are other BRM5 and Roblox military groups, later Arma Reforger units. Usually 14 to 25 years old, running a server of 30 to 300 members in their spare time, on a laptop or a phone, often at night. They already run three to five bots and are tired of it.

Secondary: the members of such a faction, who see the bot's cards in Discord and press its buttons. They never visit the site to buy; they visit to understand what the bot does.

Job: post an op, know who is coming, know who actually came, and promote people on a record instead of a feeling.

## Product Purpose

Jarcord is a Discord bot that keeps a faction's service record inside the Discord server the faction already lives in. It posts the op with RSVP buttons, closes the op with who actually turned up, files that on each member's record, and lets promotions, warnings, tickets and verification read from and write to the same record.

Success: a second faction, not ROC, adds the bot, runs one wizard, posts an op, closes it, and reads a member's record, without help.

## Positioning

Every other roster tool is a website that notifies Discord. Jarcord is the record itself, and it lives where the faction already is.

Approved phrasing: "records who actually turned up after the op, from inside Discord". Never write "no other bot does this" or "the only bot that": a competitor's attendance API has not been checked.

## Operating Context

The bot lives in a Discord server: slash commands, embeds and cards with buttons, private ticket channels, roles for rank and unit. Officers run it from Discord on desktop and phone. Screenshots of the running bot are the only product imagery. Discord's brand rules apply: write "Jarcord for Discord", never "Discord Jarcord"; no Blurple; never draw a verified mark.

## Capabilities and Constraints

Shipped today (see README.md in the repository root for the full command list):

- Ops: post with RSVP (Attending, Maybe, Can't make it), roster, edit, reminder 10 minutes before, close with a picker that records attended and no-showed, cancel, list.
- Ranks: a ladder from Private 1 to Staff Sergeant, promote and demote with a reason, the notice shows the member's record.
- Warnings with a reason and history; member profiles with Roblox link, continent, unit, ops signed up and attended, warnings, rating, messages, last seen.
- Verification of new members with a private flow; a second door for outside groups.
- Tickets: a private channel per request, transcript filed on close.
- Information panels, welcome cards, an audit log channel, a duty rota and daily list, a recurring advert, a read-only /ask.

Not shipped, do not claim as live: multi-server tenancy, Jarcord+ or any paid tier, recurring ops, slots, CSV export, per-server bot avatar, a service record page. The plans and prices below are the decided plan, not a live product.

Decided plan for tiers (from the v2 product spec, 2026-09-03):

- Free: 5 scheduled ops at a time, 60 days of attendance visible with everything retained, one rank ladder up to 10 ranks, one ticket panel, 3 information panels; warnings, audit log, welcome, verification, profiles and the record are free.
- Jarcord+: unlimited and recurring ops, custom RSVP options and slot roles, up to five reminders, full history and CSV export, unlimited ranks and ladders, several ticket panels with transcripts, bot avatar and banner per server.
- Jarcord+ is sold as one-time passes: 9 EUR for 3 months, 25 EUR for 12 months, 55 EUR perpetual, plus a 4.99 EUR monthly. Anyone can pay; the code is redeemed in a server by a slash command.

Terminology: op (never event or raid), faction (never clan or guild), member, officer, the record. Identifiers are written one way: "Op 14".

## Brand Commitments

Name: Jarcord, and Jarcord+ for the paid tier. Made by Chartreuse (the owner's studio). The studio colour, chartreuse #DFFF00, may appear once as the studio credit and nowhere else; it is not the product colour.

Voice: say what happened, then what to do. No first person, no exclamation marks, no "Successfully", "Seamless", "Elevate" or any promotional vocabulary. Sentence case. No em dashes or en dashes anywhere.

Binding visual constraints from the owner (2026-09-06): the site must feel modern, slick and professional, and must be completely different from the two earlier attempts. The first was a dark graphite "command board" with tan and olive accents and the second a tan paper page with olive and coyote ink; neither may be revisited, nor any dark page with a single acid accent, rounded cards and a centred narrow column, which the project's reviewers rejected on 2026-08-26.

## Evidence on Hand

Real screenshots of the running bot, in `img/`:

- `op-open.png` (473 by 408): an open op card with the three RSVP buttons, six attending.
- `op-closed.png` (549 by 506): a closed op, "Turned out: 7 attended, 1 no-showed".
- `rank.png` (482 by 268): a promotion notice with the member's record and the reason.
- `profile.png` (418 by 243): a member profile card.
- `cards.png` (609 by 1167): the open op, the closed op and the promotion stacked as they appear in the channel.

No testimonials, no customer logos, no usage numbers, no press. Do not invent any. ROC is the one server running it and may be named as such.

## Product Principles

1. The record is the product. Every surface should make it obvious that attendance is recorded after the op, not at signup.
2. Prove with the real cards. The screenshots are the imagery; nothing is mocked up in HTML to look like Discord.
3. Free has to carry the wedge. Ops and attendance are never behind a paywall.
4. Short on purpose. The bot stays small, and so does the copy about it.

## Accessibility & Inclusion

Members are often on phones and often under 18. Text at 16px or larger, WCAG AA contrast, keyboard focus visible, motion respects the reduced-motion setting.
