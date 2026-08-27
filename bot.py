# ── Jarcord: entry point ──
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from ui import check_message

load_dotenv()
TOKEN = os.environ["DISCORD_TOKEN"]
PREFIX = os.getenv("COMMAND_PREFIX", "!")
GUILD_ID = int(os.environ["GUILD_ID"])

COGS = (
    "cogs.ops", "cogs.rating", "cogs.activity",
    "cogs.profile", "cogs.panels", "cogs.registration", "cogs.verify", "cogs.roles", "cogs.welcome",
)

intents = discord.Intents.default()
intents.message_content = True  # prefix commands + activity tracking
intents.members = True          # !inactive needs the full member list


class Jarcord(commands.Bot):
    async def setup_hook(self):
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
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.UserInputError):
        await ctx.send(f"Usage error: {error}")
        return
    msg = check_message(error)
    if msg is not None:
        await ctx.send(msg)
        return
    print(f">> command error in {ctx.command}: {error!r}")


bot.run(TOKEN)
