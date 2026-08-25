# ── Jarcord — op signups (RSVP) cog ──
import sqlite3

import discord
from discord import app_commands
from discord.ext import commands

from db import conn


# ── DB helpers (shared by slash + prefix) ──
def create_op(title: str, when: str, author_id: int) -> int:
    cur = conn.execute(
        "INSERT INTO ops (title, when_text, created_by) VALUES (?, ?, ?)",
        (title, when, author_id),
    )
    conn.commit()
    return cur.lastrowid


def join_op(op_id: int, user_id: int) -> str:
    op = conn.execute("SELECT * FROM ops WHERE id = ?", (op_id,)).fetchone()
    if op is None:
        return f"No op with ID `{op_id}`."
    try:
        conn.execute("INSERT INTO signups (op_id, user_id) VALUES (?, ?)", (op_id, user_id))
        conn.commit()
    except sqlite3.IntegrityError:
        return f"You're already signed up for **{op['title']}**."
    return f"Signed up for **{op['title']}** ({op['when_text']})."


def roster_text(op_id: int) -> str:
    op = conn.execute("SELECT * FROM ops WHERE id = ?", (op_id,)).fetchone()
    if op is None:
        return f"No op with ID `{op_id}`."
    rows = conn.execute(
        "SELECT user_id FROM signups WHERE op_id = ? ORDER BY signed_at", (op_id,)
    ).fetchall()
    header = f"**{op['title']}** — {op['when_text']} (ID `{op_id}`)"
    if not rows:
        return f"{header}\nNobody signed up yet."
    names = "\n".join(f"{i}. <@{r['user_id']}>" for i, r in enumerate(rows, 1))
    return f"{header}\n{names}"


def list_text() -> str:
    rows = conn.execute(
        """SELECT o.id, o.title, o.when_text, COUNT(s.user_id) AS n
           FROM ops o LEFT JOIN signups s ON s.op_id = o.id
           GROUP BY o.id ORDER BY o.id DESC LIMIT 10"""
    ).fetchall()
    if not rows:
        return "No ops yet."
    return "**Recent ops**\n" + "\n".join(
        f"`{r['id']}` **{r['title']}** — {r['when_text']} ({r['n']} signed up)" for r in rows
    )


class Ops(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Slash commands ──
    @app_commands.command(name="op-create", description="Post a new op and get its ID")
    @app_commands.describe(title="Op name", when="When it happens (free text)")
    async def op_create(self, interaction: discord.Interaction, title: str, when: str):
        op_id = create_op(title, when, interaction.user.id)
        await interaction.response.send_message(
            f"Op **{title}** posted — **{when}**. ID `{op_id}`. Join with `/op-join {op_id}`."
        )

    @app_commands.command(name="op-join", description="Sign up for an op")
    @app_commands.describe(op_id="The op ID")
    async def op_join(self, interaction: discord.Interaction, op_id: int):
        await interaction.response.send_message(join_op(op_id, interaction.user.id))

    # ── Prefix commands: !op join / roster / list ──
    @commands.group(name="op", invoke_without_command=True)
    async def op(self, ctx: commands.Context):
        await ctx.send("Usage: `op join <id>` | `op roster <id>` | `op list`")

    @op.command(name="join")
    async def op_join_prefix(self, ctx: commands.Context, op_id: int):
        await ctx.send(join_op(op_id, ctx.author.id))

    @op.command(name="roster")
    async def op_roster(self, ctx: commands.Context, op_id: int):
        await ctx.send(roster_text(op_id))

    @op.command(name="list")
    async def op_list(self, ctx: commands.Context):
        await ctx.send(list_text())


async def setup(bot: commands.Bot):
    await bot.add_cog(Ops(bot))
