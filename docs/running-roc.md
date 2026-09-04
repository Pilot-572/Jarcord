# Running the faction for a week

For whoever is on duty. You do not need to know how the bot works, and you should not
need to message the owner. If you get to the bottom of this page and still do not know
what to do, that is a fault in the page and worth saying so.

## Your day

At 12:00 the bot posts a list in the duty channel and pings whoever is on. That list is
the whole job. Every line either ticks itself when the work is done or stays bold.

Nothing on the list needs marking off by hand. The bot reads the actual state of the
server, so a line goes quiet when the thing is genuinely done and not before. If a line
is bold and you know it does not apply today, press **Nothing needed today** and nobody
else gets pinged about it.

If the list is still open four hours later, the next person in the rota gets pinged. If
it is still open after eight, the server owner does. That is the only reason he gets
pulled in, so clearing the list is the whole of keeping him out of it.

## The five lines, and what each one means

**Post the advert.** It goes out on its own, on its schedule. This line appears when the
last scheduled post did not go out, usually because the bot lost permission to write in
that channel, or when nothing has been posted yet. Check it can still post there, then
`/advert now` to send it by hand.

**Nothing on the board.** No op is scheduled ahead. Schedule one with `/op create`. A
faction with an empty board for a few days starts losing people, which is the reason
this line exists at all.

**Ops started and never closed.** Somebody ran an op and never recorded who turned up.
`/op close` and tick the attendees. This matters more than it looks: attendance is what
promotions read, so an op that is never closed is an op that never counted for anyone.

**Tickets unclaimed for over 12 hours.** Somebody asked for something and nobody
answered. Open the ticket channel, claim it, reply. A leave request that sits unanswered
for a day is how you lose a member who was trying to do the right thing.

**Members never linked an account.** They joined, never finished verification. Nudge
them, or ask an officer whether they should still be in.

## Commands you will actually use

| Command | What it does |
|---|---|
| `/duty today` | Today's list, on demand. Anyone can run it |
| `/duty rota @a @b @c` | Set the rotation, in order. Add `rotate_days:7` for a week each, and `channel:` to say where the list posts |
| `/op create` | Post an op |
| `/op close` | Record who turned up |
| `/advert set` | Write the recruitment post and schedule it |
| `/advert now` | Post it immediately, without touching the schedule |
| `/advert off` | Stop it going out |
| `/ask` | Ask about the faction's own rules and commands. Off until a key is configured |

`/duty rota` and the `/advert` commands need the officer role or Manage Server. The rest
is open.

## When something is actually broken

**The bot is offline.** Nothing posts, no commands answer. Only the owner can restart it.
Say so in the staff channel and carry the day by hand; the list will catch up.

**A command says Jarcord is missing a permission.** It names the permission. Someone with
Manage Roles can add it in Server Settings, Roles, Jarcord. This does not need the owner.

**A command fails with a code like `A-500`.** Send the code to the owner. It is the only
thing he needs to find what went wrong, so it is worth copying exactly.

**Somebody is being treated badly.** This does not go through the rota and does not wait
for the duty officer. It goes straight up, and if the person you would report it to is
part of the problem, go past them.

## What the rota is not

It is not a promise that you do everything alone. It means you are the person who notices,
and the person who asks somebody else if you cannot. A day where you pinged two people and
did none of it yourself is a day the rota worked.
