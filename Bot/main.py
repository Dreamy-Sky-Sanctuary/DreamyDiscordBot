from typing import Final
import os
import time
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord.types.activity import ActivityAssets
import asyncio
from functions import send_message_to_user

# Load the environment variables
load_dotenv()
TOKEN: Final[str] = os.getenv("DISCORD_TOKEN")

# Bot settings
allowed_roles: list[int] = [1240725491099631717, 1242514956058890240, 1274673142153084928, 1266201501924331552] # last one is for testing purpeses
sky_guardians_role_id: int = 1242514956058890240
owner_id: int = 529007366365249546
support_category_id = 1250699865621794836
max_teams = 4

tickets: dict = {}
teams: dict = {}
update_queue: list = []
full_team_cooldowns: dict = {}
cooldown_period: int = 60  # 60 seconds cooldown

# Create a bot instance
intents: discord.Intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = commands.Bot(command_prefix="/", intents=intents)

# Startup of the bot
@client.event
async def on_ready():
    print(f"\n\n THE BOT IS OUT OF ORDER\n")
    print(f"\n[info] Bot is ready as {client.user}\n")
    
    # Set Rich Presence (Activity)
    activity = discord.Activity(type=discord.ActivityType.playing, name="Out of Order")
    
    await client.change_presence(status=discord.Status.do_not_disturb, activity=activity)
    await client.tree.sync()  # Sync slash commands


# Error handling for command not found
@client.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandNotFound):
        print(f"[warning] {ctx.author} tried to use an unknown command in channel {ctx.channel}: {ctx.message.content}\n - {error}")
        await ctx.send(f"Command not found! Please check your command or use `/help` for available commands.")
    else:
        # Raise the error if it's not CommandNotFound
        raise error


def main() -> None:
    client.run(TOKEN)


if __name__ == "__main__":
    main()