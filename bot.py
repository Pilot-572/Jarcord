# ── Jarcord: entry point ──
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from db import claim_orphans
from ui import check_message, log_command, log_deleted, one_line

load_dotenv()
TOKEN = os.environ["DISCORD_TOKEN"]
PREFIX = os.getenv("COMMAND_PREFIX", "!")
GUILD_ID = int(os.environ["GUILD_ID"])

COGS = (
    "cogs.ops", "cogs.rating", "cogs.activity",
    "cogs.profile", "cogs.panels", "cogs.verify", "cogs.roles", "cogs.welcome", "cogs.warnings",
    "cogs.ranks", "cogs.tickets", "cogs.duty", "cogs.assistant", "cogs.ideas",
)

# how a command log line ends when the command did not do what it was asked. Words, not
# colour: a Nitro theme flattens every embed strip to grey.
REFUSED = " (refused)"
FAILED = " (failed)"

intents = discord.Intents.default()
intents.message_content = True  # prefix commands + activity tracking
intents.members = True          # !inactive needs the full member list


class Jarcord(commands.Bot):
    async def setup_hook(self):
        claim_orphans(GUILD_ID)   # rows from before guild_id existed belong to this guild
        for cog in COGS:
            await self.load_extension(cog)
            print(f">> loaded {cog}")
        self.tree.on_error = self.on_tree_error
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        print(f">> synced {len(synced)} slash commands to guild {GUILD_ID}")

    async def on_tree_error(self, interaction: discord.Interaction, error):
        msg = check_message(error)
        name = interaction.command.qualified_name if interaction.command else "unknown"
        await log_command(interaction.guild, f"/{name}", interaction.user,
                          interaction.channel, one_line(interaction.namespace),
                          REFUSED if msg else FAILED)
        if msg is None:
            print(f">> slash command error in {interaction.command}: {error!r}")
            msg = "Something went wrong running that."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


bot = Jarcord(
    command_prefix=PREFIX,
    intents=intents,
    activity=discord.Activity(type=discord.ActivityType.watching, name="the ops board"),
)


@bot.event
async def on_ready():
    print(f">> logged in as {bot.user} ({bot.user.id})")


@bot.event
async def on_message(message):
    # a bare @Jarcord gets the clerk; anything else goes to the prefix commands as before
    if message.guild is not None and not message.author.bot and bot.user is not None \
            and message.content.strip() in (bot.user.mention, f"<@!{bot.user.id}>"):
        await message.reply(
            "Company clerk. Point /profile at Jarcord for the details, or type / to see the commands.",
            mention_author=False,
        )
        return
    await bot.process_commands(message)


# ── The command log ──
# Every command that runs goes to the log channel, refused and failed ones included. The
# cogs log what a command did; these four log that it was asked for. A hybrid run as a
# slash command dispatches both completion events, so the prefix one stands down when the
# context carries an interaction.


@bot.event
async def on_app_command_completion(interaction, command):
    await log_command(interaction.guild, f"/{command.qualified_name}", interaction.user,
                      interaction.channel, one_line(interaction.namespace))


@bot.event
async def on_command_completion(ctx):
    if ctx.interaction is not None:
        return
    await log_command(ctx.guild, f"{PREFIX}{ctx.command.qualified_name}", ctx.author,
                      ctx.channel, one_line(ctx.kwargs.items()))


@bot.event
async def on_message_delete(message):
    await log_deleted(message.guild, [message], message.channel)


@bot.event
async def on_bulk_message_delete(messages):
    # one file, not one embed each: /c 100 would otherwise be a hundred sends
    if messages:
        await log_deleted(messages[0].guild, messages, messages[0].channel)


async def log_failure(ctx, outcome: str) -> None:
    name = ctx.command.qualified_name if ctx.command else "unknown"
    prefix = "/" if ctx.interaction is not None else PREFIX
    await log_command(ctx.guild, f"{prefix}{name}", ctx.author, ctx.channel,
                      one_line(ctx.kwargs.items()), outcome)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.UserInputError):
        await log_failure(ctx, FAILED)
        await ctx.send(f"Usage error: {error}")
        return
    msg = check_message(error)
    await log_failure(ctx, REFUSED if msg else FAILED)
    if msg is not None:
        await ctx.send(msg)
        return
    print(f">> command error in {ctx.command}: {error!r}")


bot.run(TOKEN)
