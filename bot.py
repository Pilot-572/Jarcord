# ── Jarcord — entry point ──
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ["DISCORD_TOKEN"]
PREFIX = os.getenv("COMMAND_PREFIX", "!")
GUILD_ID = int(os.environ["GUILD_ID"])

COGS = ("cogs.ops", "cogs.rating", "cogs.activity")

intents = discord.Intents.default()
intents.message_content = True  # prefix commands + activity tracking
intents.members = True          # !inactive needs the full member list


class Jarcord(commands.Bot):
    async def setup_hook(self):
        for cog in COGS:
            await self.load_extension(cog)
            print(f">> loaded {cog}")
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        print(f">> synced {len(synced)} slash commands to guild {GUILD_ID}")


bot = Jarcord(command_prefix=PREFIX, intents=intents)


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
    print(f">> command error in {ctx.command}: {error!r}")


bot.run(TOKEN)
