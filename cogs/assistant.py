# ── Jarcord: /ask, so officers stop having to ask the owner ──
# The faction's knowledge already exists in the bot: the panels are the rules, the
# command tree is what can be done, the settings are how this server is wired. This
# hands all of that to a model and answers questions from it.
#
# Three deliberate limits, in order of importance:
#   1. It is read only. There is no tool calling and no action path, so no answer can
#      promote, warn, kick or post anything. The worst case is a wrong sentence.
#   2. It never sees another member's data. The prompt carries the faction's own rules
#      plus the asker's own record, and nothing about anybody else. Most of this unit
#      is under 18 and their records are not going to a third-party API.
#   3. It refuses rather than invents. The system prompt says to answer from the context
#      or say who to ask, and the answer is labelled as coming from a model.
import json
import os
from datetime import date

import aiohttp
import discord
from discord.ext import commands

from cogs.panels import load_panel, panel_names
from cogs.ranks import ABBREV, RANKS, current_rank
from cogs.tickets import KINDS
from db import conn, get_setting, set_setting
from ui import COYOTE, NEUTRAL, OLIVE, embed

# Works against Groq or anything else speaking the OpenAI chat shape. Set LLM_BASE_URL
# and LLM_API_KEY in .env; GROQ_API_KEY is accepted as-is so an existing key just works.
LLM_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
LLM_KEY = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

MAX_CONTEXT = 9000     # characters of grounding; a panel set is bigger than it looks
MAX_ANSWER = 400       # tokens out, so an answer stays a Discord message
DAILY_CAP = 200        # whole-server calls per day, so one person cannot burn the quota
TIMEOUT = aiohttp.ClientTimeout(total=25)

SYSTEM = (
    "You are Jarcord, the assistant inside a player-run military gaming faction's own "
    "Discord server. You answer questions from the faction's officers and members about "
    "how this faction works and how to use the bot.\n\n"
    "Rules you follow without exception:\n"
    "- Answer only from the FACTION CONTEXT below. If the answer is not there, say so in "
    "one sentence and say to ask an officer. Never guess at a rule.\n"
    "- Never invent a command. Only name commands that appear in the context, and write "
    "them exactly as they appear.\n"
    "- You cannot do anything yourself. You have no ability to promote, warn, post, "
    "schedule or change anything. If asked to do something, name the command that does "
    "it and who is allowed to run it.\n"
    "- You know nothing about any member other than the person asking. If asked about "
    "somebody else, say that their record is not something you can look at.\n"
    "- Under 120 words. Plain sentences. No first person, no 'Successfully', no 'Oops', "
    "no exclamation marks, no apologising. Say what to do, then who can do it."
)


# ── Grounding, assembled from what the bot already knows ──
def strings_in(value) -> list[str]:
    """Every string in a panel's JSON, whatever shape the panel is. Generic on purpose:
    the panel schema changes and this should not have to."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in strings_in(v)]
    if isinstance(value, list):
        return [s for v in value for s in strings_in(v)]
    return []


def panel_text(budget: int) -> str:
    """The faction's own rules, as written by the faction. This is the bulk of the
    grounding and the reason the answers are about this unit rather than generic."""
    out = []
    used = 0
    for name in panel_names():
        panel = load_panel(name)
        if panel is None:
            continue
        body = " ".join(s.strip() for s in strings_in(panel) if s.strip())
        chunk = f"## Page: {name}\n{body}\n"
        if used + len(chunk) > budget:
            break
        out.append(chunk)
        used += len(chunk)
    return "".join(out)


def command_text(bot: commands.Bot) -> str:
    """Straight off the command tree, so this can never drift out of date."""
    lines = []
    for cmd in sorted(bot.tree.walk_commands(), key=lambda c: c.qualified_name):
        if isinstance(cmd, discord.app_commands.Group):
            continue
        desc = (cmd.description or "").strip()
        lines.append(f"/{cmd.qualified_name}" + (f" - {desc}" if desc else ""))
    return "\n".join(lines)


def state_text() -> str:
    """How this server is set up, plus what is on the board. No member data."""
    faction = get_setting("faction_name") or "this faction"
    ladder = ", ".join(f"{r} ({a})" for r, a in zip(RANKS, ABBREV))
    kinds = "; ".join(f"{k}: {v['title']}" for k, v in KINDS.items())
    ops = conn.execute(
        "SELECT title, when_text FROM ops WHERE closed = 0 AND when_ts IS NOT NULL "
        "AND when_ts > strftime('%s', 'now') ORDER BY when_ts LIMIT 5"
    ).fetchall()
    board = ("\n".join(f"- {r['title']}, {r['when_text']}" for r in ops)
             or "- nothing scheduled")
    officer_role = "set" if get_setting("officer_role_id") else "not set yet"
    return (
        f"Faction name: {faction}\n"
        f"Rank ladder, lowest to highest: {ladder}\n"
        f"Ticket kinds members can open: {kinds}\n"
        f"Officer role: {officer_role}\n"
        f"Ops currently on the board:\n{board}\n"
    )


def asker_text(member: discord.Member) -> str:
    """The asker's own record and nothing else. Deliberately not a lookup by name:
    there is no code path here that can read a third party's record."""
    from cogs.ops import attendance  # local import: cogs.ops imports ui, keep it lazy

    rank = current_rank(member) or "no rank yet"
    came, missed = attendance(member.id)
    row = conn.execute(
        "SELECT roblox_id, unit FROM profiles WHERE user_id = ?", (member.id,)
    ).fetchone()
    linked = "linked" if row and row["roblox_id"] else "not linked"
    unit = (row["unit"] if row and row["unit"] else "no unit")
    is_officer_now = bool(get_setting("officer_role_id")) and any(
        str(r.id) == get_setting("officer_role_id") for r in member.roles)
    return (
        f"The person asking: rank {rank}, {unit}, account {linked}, "
        f"{came} ops attended, {missed} no-shows, "
        f"{'an officer' if is_officer_now or member.guild_permissions.manage_guild else 'not an officer'}.\n"
    )


def build_context(bot: commands.Bot, member: discord.Member) -> str:
    head = state_text() + asker_text(member)
    commands_block = command_text(bot)
    budget = MAX_CONTEXT - len(head) - len(commands_block) - 200
    return (
        "# FACTION CONTEXT\n\n"
        f"{head}\n"
        f"## Commands that exist\n{commands_block}\n\n"
        f"{panel_text(max(budget, 0))}"
    )[:MAX_CONTEXT]


# ── Daily cap, on the settings KV so it survives a restart ──
def take_call() -> bool:
    today = date.today().isoformat()
    stamp = get_setting("ask_calls") or ""
    day, _, count = stamp.partition(":")
    used = int(count) if day == today and count.isdigit() else 0
    if used >= DAILY_CAP:
        return False
    set_setting("ask_calls", f"{today}:{used + 1}")
    return True


async def ask_llm(question: str, context: str) -> str:
    payload = {
        "model": LLM_MODEL,
        "max_tokens": MAX_ANSWER,
        "temperature": 0.2,   # a rules question wants the same answer every time
        "messages": [
            {"role": "system", "content": SYSTEM + "\n\n" + context},
            {"role": "user", "content": question},
        ],
    }
    headers = {"Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json"}
    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        async with session.post(f"{LLM_URL}/chat/completions",
                                json=payload, headers=headers) as resp:
            body = await resp.text()
            if resp.status != 200:
                # never log the key, and never show the raw body to a member
                print(f">> /ask upstream {resp.status}: {body[:300]}")
                raise UpstreamError(resp.status)
            data = json.loads(body)
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError):
        print(f">> /ask unexpected response shape: {body[:300]}")
        raise UpstreamError(200)


class UpstreamError(Exception):
    def __init__(self, status: int):
        self.status = status


class Assistant(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx) -> bool:
        return ctx.guild is not None

    @commands.hybrid_command(
        name="ask",
        description="Ask about this faction's rules, ranks, ops or commands")
    @commands.cooldown(2, 60, commands.BucketType.user)
    async def ask(self, ctx: commands.Context, *, question: str):
        if not LLM_KEY:
            await ctx.send(
                "Asking is not switched on. An admin needs to put `LLM_API_KEY` in the "
                "bot's .env and restart it. In the meantime the same answers are in the "
                "information hub.", ephemeral=True)
            return
        if len(question) < 4:
            await ctx.send("Ask it as a question and there will be more to go on.",
                           ephemeral=True)
            return
        if not take_call():
            await ctx.send(
                f"Asking has hit its {DAILY_CAP} answers for today. It resets at midnight; "
                "an officer can answer sooner.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)
        try:
            answer = await ask_llm(question[:600], build_context(self.bot, ctx.author))
        except UpstreamError as exc:
            await ctx.send(
                "That didn't come back. Try once more; if it fails again tell an officer "
                f"the code A-{exc.status}.", ephemeral=True)
            return
        except (aiohttp.ClientError, TimeoutError) as exc:
            print(f">> /ask network: {exc!r}")
            await ctx.send("That didn't come back in time. Try once more.", ephemeral=True)
            return

        e = embed(title=None, description=answer[:4000], colour=OLIVE)
        e.set_author(name="Answered from this server's own pages")
        e.set_footer(text="Written by a model, so check anything that matters with an officer.")
        await ctx.send(embed=e, ephemeral=True)
        print(f">> /ask answered for {ctx.author.id}")

    @commands.hybrid_command(name="ask-status", description="Whether asking is switched on")
    async def ask_status(self, ctx: commands.Context):
        today = date.today().isoformat()
        stamp = get_setting("ask_calls") or ""
        day, _, count = stamp.partition(":")
        used = int(count) if day == today and count.isdigit() else 0
        ctx_size = len(build_context(self.bot, ctx.author))
        e = embed(
            title="Asking is on" if LLM_KEY else "Asking is off",
            description=(
                f"Model: `{LLM_MODEL}`\n"
                f"Used today: {used} of {DAILY_CAP}\n"
                f"Pages it reads from: {len(panel_names())}\n"
                f"Context size: {ctx_size} characters"
                if LLM_KEY else
                "No `LLM_API_KEY` in the bot's .env, so /ask cannot answer."
            ),
            colour=OLIVE if LLM_KEY else NEUTRAL,
        )
        await ctx.send(embed=e, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Assistant(bot))
