# discord imports
import sys
from discord.ext import commands
from discord import app_commands
import discord
import discord.ui
from discord.ui import View, Select

# python imports 
from dotenv import load_dotenv
from typing import Final
import asyncio
import time
import os
import json


# local imports
from functions import load_ids, save_transcript, get_rule_channels, create_connection, close_connection
from ticketMenu import PersistentTicketView, PersistentCloseTicketView
from musicMenu import PersistentMusicView
from cogs.RunManager import RunManager
from cogs.AccessManager import AccessManager, PersistentAcceptRulesView
from cogs.TreasureHuntManager import TreasureHuntManager
from logger import logger


# Load the environment variables
load_dotenv()
TOKEN: Final[str] = os.getenv("DISCORD_TOKEN")
TESTING: Final[str] = os.getenv("TESTING")
bot_prefix: Final[str] = os.getenv("PREFIX")

# Load the IDs from the database
ids = load_ids()

# team settings
max_teams: int = 4
cooldown_period: int = 60

# Initialize the dictionaries and lists
teams: dict = {}
update_queue: list = []
full_team_cooldowns: dict = {}
reaction_tracker: dict = {}

# Create a bot instance
intents: discord.Intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = commands.Bot(command_prefix="!", intents=intents)


# load the command whitelist
dir = "/dreamy-data"
with open(f"{dir}/whitelist.json", "r") as file:
    command_whitelist = json.load(file)["no_error_commands"]


# Startup of the bot
@client.event
async def on_ready() -> None:    
    client.add_view(PersistentTicketView(client))
    client.add_view(PersistentCloseTicketView(client))
    client.add_view(PersistentMusicView(client))
    
    connection = create_connection("Server_data")
    rule_channels = get_rule_channels(connection)
    if rule_channels:
        for rule_channel in rule_channels:
            channel = await client.fetch_channel(rule_channel["channel_id"])
            client.add_view(PersistentAcceptRulesView(client, channel))
    else:
        logger.debug("No rule channels found in the database.")
    close_connection(connection)
    
    # Load the cogs
    await client.add_cog(RunManager(client))
    await client.add_cog(AccessManager(client))
    await client.add_cog(TreasureHuntManager(client))
    
    # Set Rich Presence (Streaming)
    if TESTING == "True":
        logger.info("Bot is in testing mode.")
        # Under Development (Do not disturb)
        activity = discord.Activity(type=discord.ActivityType.playing, name="Do not disturb, im getting tested")
        await client.change_presence(status=discord.Status.do_not_disturb, activity=activity)
    else:
        logger.info("Bot is in production mode.")
        # Streaming PixelPoppyTV (streaming)
        activity = discord.Activity(type=discord.ActivityType.streaming, name="PixelPoppyTV", url="https://www.twitch.tv/pixelpoppytv", details="PixelPoppyTV", state="Sky: Children of The Light")
        await client.change_presence(status=discord.Status.online, activity=activity)
    
    logger.debug("Syncing slash commands...")
    await client.tree.sync()  # Sync slash commands
    logger.log("PRINT", f"Bot is ready as {client.user} and is connected to {len(client.guilds)} guilds.")


@client.tree.command(name="help", description="Lists all available commands.")
async def help_command(interaction: discord.Interaction):
    logger.command(interaction)
    # Create an embed for displaying the commands
    embed = discord.Embed(title="Dreamy Commands 🍃", description="Here is everything I can do for you!", color=discord.Color.green())
    embed.set_image(url="https://i.postimg.cc/28LPZLBW/20240821214134-1.jpg")
    # Loop through all commands in the CommandTree and add them to the embed
    for command in client.tree.get_commands():
        embed.add_field(name=f"/{command.name}", value=f"```ansi\n[2;31m```{command.description}```", inline=False)
        
    # Send the embed to the user
    await interaction.response.send_message(embed=embed, ephemeral=True)


@client.tree.command(name="ping", description="Check the bot's current latency.")
async def ping(interaction: discord.Interaction) -> None:
    logger.command(interaction)
    await interaction.response.send_message(f"Pong! that took me {round(client.latency * 1000)}ms to respond")
    logger.info(f"{interaction.user.name} requested the bot's latency, it's {round(client.latency * 1000)}ms")

# ticket commands
@client.tree.command(name="ticket_menu", description="Create a ticket create menu.")
async def ticket(interaction: discord.Interaction) -> None:
    logger.command(interaction)
    await interaction.response.defer()
    allowed_roles: list[int] = [ids[interaction.guild.id]["sancturary_keeper_role_id"], ids[interaction.guild.id]["sky_guardians_role_id"], ids[interaction.guild.id]["tech_oracle_role_id"]]
    if not any(role.id in allowed_roles for role in interaction.user.roles):
        await interaction.followup.send("```ansi\n[2;31mYou do not have permission to create a ticket menu.```", ephemeral=True)
        return
    await interaction.followup.send(
        "How to Submit Tickets:\n\n1. Click the button below to create a ticket.\n2. Choose the type of ticket you would like to create.\n3. A ticket channel will be created for you.\n4. Give as much detail as possible about the issue or question.\n5. Wait for response.\n6. Close ticket when response has been received.\n\n**Tickets remain saved on our side, so when you close a ticket we are still able to review the ticket and delete it afterwards.**", 
        view=PersistentTicketView(client))


@client.tree.command(name="force_close_ticket", description="Force close a ticket. This will CLOSE ANY channel and send the logs to the log channel.")
async def force_close_ticket(interaction: discord.Interaction) -> None:
    logger.command(interaction)
    logger.warning(f"User {interaction.user.name} requested to force close a ticket.")
    sky_guardians_role = interaction.guild.get_role(ids[interaction.guild.id]["sky_guardians_role_id"])
    if not sky_guardians_role:
        logger.error("Sky Guardians role not found. Please provide a valid role ID.")
        await interaction.followup.send("```ansi\n[2;31mSky Guardians role not found. Please provide a valid role ID.```", ephemeral=True)
        return
    
    tech_oracle_role = interaction.guild.get_role(ids[interaction.guild.id]["tech_oracle_role_id"])
    if not tech_oracle_role:
        logger.error("Tech Oracle role not found. Please provide a valid role ID.")
        await interaction.followup.send("```ansi\n[2;31mTech Oracle role not found. Please provide a valid role ID.```", ephemeral=True)
        return
    
    if interaction.user.id != ids[interaction.guild.id]["owner_id"] or sky_guardians_role in interaction.user.roles or tech_oracle_role in interaction.user.roles:
        select = Select(options=[
            discord.SelectOption(label="Yes, close this ticket", value="01", emoji="☑️", description="This closes the ticket and will mark it as solved"),
            discord.SelectOption(label="No, keep this ticket open", value="02", emoji="✖️", description="This will keep the ticket open and allow you to continue the conversation"),
        ])
        
        select.callback = ticket_select_callback
        view = View(timeout=60)
        view.add_item(select)
        await interaction.response.send_message("Do you really want to close the ticket?", view=view, ephemeral=True, delete_after=60)
    
    else:
        logger.error(f"User {interaction.user.name} does not have permission to use this command.")
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)


async def ticket_select_callback(interaction: discord.Interaction):
    logger.command(interaction)
    await interaction.response.defer()
    if interaction.data["values"][0] == "01": # Yes, close this ticket
        logger.warning(f"User {interaction.user.name} requested to force close a ticket.", extra={"command": "force_close_ticket", "sub_command": "close_select_callback", "user_id": interaction.user.id, "username": interaction.user.name, "display_name": interaction.user.display_name})
        await interaction.followup.send("Ticket will be force closed.")

        ticket_logs = ""
        path = await save_transcript(interaction.channel, ticket_logs)

        ticket_logs_channel = client.get_channel(ids[interaction.guild.id]["ticket_log_channel_id"])
        if ticket_logs_channel:
            await ticket_logs_channel.send(f"Transcript for {interaction.channel.name}:\nThe ticket channel {interaction.channel.name} has been **force** closed by {interaction.user.name} a.k.a {interaction.user.display_name}", file=discord.File(path))
        else:
            logger.error("Ticket logs channel not found. Please provide a valid channel ID.")
        logger.info(f"Ticket {interaction.channel.name} has been force closed by {interaction.user.name} a.k.a {interaction.user.display_name}")
        await interaction.channel.delete()
        await interaction.user.send("Your ticket has been closed successfully. The Transcript of the ticket has been saved.")
        await interaction.user.send(f"Transcript for {interaction.channel.name}:", file=discord.File(path))
    elif interaction.data["values"][0] == "02": # No, keep this ticket open
        await interaction.followup.send("This ticket will remain open.", ephemeral=True)
    
    else: # Invalid selection
        await interaction.followup.send("Invalid selection", ephemeral=True)

# info commands
@client.tree.command(name="timers", description="Gives the link to all of the timers.")
async def timers(interaction: discord.Interaction) -> None:
    logger.command(interaction)
    timer_channel_url = "https://discord.com/channels/1239651599480127649/1252324353115291849/1252324488901824556"
    response = "Here is the url to the channel with all the timers:\n" + timer_channel_url
    logger.debug(f"User {interaction.user.name} requested the timers link.")
    await interaction.response.send_message(response)
    

# Team commands
@client.tree.command(name="createteam", description="Create a team with a leader and an emoji.")
async def createteam(interaction: discord.Interaction, member: discord.Member, emoji: str, max_size: int = 8) -> None:
    logger.command(interaction)
    await interaction.response.defer(ephemeral=True)  # Defer the response to get more time
    allowed_roles: list[int] = [ids[interaction.guild.id]["sancturary_keeper_role_id"], ids[interaction.guild.id]["event_luminary_role_id"], ids[interaction.guild.id]["sky_guardians_role_id"], ids[interaction.guild.id]["tech_oracle_role_id"]]
    if not any(role.id in allowed_roles for role in interaction.user.roles):
        await interaction.followup.send("You do not have permission to create a team.", ephemeral=True)
        return
    
    if member.id in teams:
        try:
            message = await client.fetch_channel(teams[member.id]["channel_id"]).fetch_message(teams[member.id]["message_id"])
            await interaction.followup.send("This user already leads a team.", ephemeral=True)
        except discord.NotFound:
            logger.error(f"Team message not found for user {member.id}.")
        return

    if len(teams) >= max_teams:
        await interaction.followup.send("The maximum number of teams has been reached. Cannot create a new team.", ephemeral=True)
        return
    
    emoji = emoji.strip()  # Remove the colons from the emoji if present
    logger.debug(f"Creating team {emoji} with leader {member.name}:{member.id} and max size {max_size} in channel {interaction.channel.id}.")
    
    await interaction.followup.send(f"Team {emoji} has been created!", ephemeral=False)
    team_message = f"__**Group Leader**__\n{member.mention} {emoji}\n\n__**Members**__\n"

    message = await interaction.channel.send(team_message, allowed_mentions=discord.AllowedMentions.none())

    # Add the bot's reaction
    try:
        await message.add_reaction(emoji)
    except discord.HTTPException as e:
        logger.error(f"An error occurred while adding a reaction to the message: {e}")
        await interaction.followup.send("An error occurred while adding a reaction to the message.", ephemeral=True)
        await message.delete()
        return
    

    # Save team information
    teams[member.id] = {
        "message_id": message.id,
        "emoji": emoji,
        "members": [],
        "max_members": max_size,  # Max members in the team
        "leader_id": member.id,
        "reaction_count": 1,  # Start with 1 to count the team leader
        "last_locked_message_time": 0,
        "locked": False,  # Initialize the locked state
        "channel_id": interaction.channel.id,  # Track the channel ID
        "resetting": False  # Track if the team is currently resetting
    }
    logger.debug(f"Team {emoji} created by {member.name}:{member.id} with message ID {message.id} in channel {interaction.channel.id}.")


@client.tree.command(name="closeteam", description="Close the given leader's team.")
async def closeteam(interaction: discord.Interaction, member: discord.Member) -> None:
    logger.command(interaction)
    await interaction.response.defer(ephemeral=True)  # Defer the response to get more time
    allowed_roles: list[int] = [ids[interaction.guild.id]["sancturary_keeper_role_id"], ids[interaction.guild.id]["event_luminary_role_id"], ids[interaction.guild.id]["sky_guardians_role_id"], ids[interaction.guild.id]["tech_oracle_role_id"]]
    if not any(role.id in allowed_roles for role in interaction.user.roles):
        await interaction.followup.send("You do not have permission to close a team.", ephemeral=True)
        return
    
    if member.id not in teams:
        await interaction.followup.send(f"A team led by {member.mention} not found.", ephemeral=True)
        return
    
    team_data = teams[member.id]
    
    # Check if the team is locked
    if team_data["locked"] == False: 
        await interaction.followup.send(f"Team {team_data['emoji']} led by {member.mention} is not currently locked. Please lock the team first.", ephemeral=True)
        return
    team_data["closed"] = True  # Set the closed flag
    try:
        channel = client.get_channel(team_data["channel_id"])  # Get the team's channel
        message = await channel.fetch_message(team_data["message_id"])  # Fetch the message
        await message.delete()  # Delete the message
    except discord.NotFound:
        logger.error(f"Team message not found for user {member.id}.")
        await interaction.followup.send(f"Team {team_data['emoji']} led by {member.mention} message was not found.", ephemeral=True)

    await interaction.channel.send(f"Team {team_data['emoji']} led by {member.mention} has been closed.", allowed_mentions=discord.AllowedMentions.none())
    await interaction.followup.send(f"Team {team_data['emoji']} led by {member.mention} has been closed.", ephemeral=False)
    del teams[member.id]  # Remove the team from the dictionary


@client.tree.command(name="force_close_team", description="Close the given leader's team.")
async def force_close_team(interaction: discord.Interaction, member: discord.Member) -> None:
    logger.command(interaction)
    logger.warning(f"User {interaction.user.name} requested to force close a team.")
    await interaction.response.defer(ephemeral=True)  # Defer the response to get more time
    allowed_roles: list[int] = [ids[interaction.guild.id]["sancturary_keeper_role_id"], ids[interaction.guild.id]["event_luminary_role_id"], ids[interaction.guild.id]["sky_guardians_role_id"], ids[interaction.guild.id]["tech_oracle_role_id"]]
    if not any(role.id in allowed_roles for role in interaction.user.roles):
        await interaction.followup.send("You do not have permission to force close a team.", ephemeral=True)
        return
    
    if member.id not in teams:
        await interaction.followup.send(f"A team led by {member.mention} not found.", ephemeral=True)
        return
    
    team_data = teams[member.id]
    
    # Check if the team is locked
    team_data["closed"] = True  # Set the closed flag

    await interaction.channel.send(f"Team {team_data['emoji']} led by {member.mention} has been closed.", allowed_mentions=discord.AllowedMentions.none())
    await interaction.followup.send(f"Team {team_data['emoji']} led by {member.mention} has been force closed.", ephemeral=False)
    del teams[member.id]  # Remove the team from the dictionary


@client.tree.command(name="lockteam", description="Lock the given leader's team.")
async def lockteam(interaction: discord.Interaction, member: discord.Member) -> None:
    logger.command(interaction)
    await interaction.response.defer(ephemeral=True)  # Defer the response to get more time
    allowed_roles: list[int] = [ids[interaction.guild.id]["sancturary_keeper_role_id"], ids[interaction.guild.id]["event_luminary_role_id"], ids[interaction.guild.id]["sky_guardians_role_id"], ids[interaction.guild.id]["tech_oracle_role_id"]]
    if not any(role.id in allowed_roles for role in interaction.user.roles):
        await interaction.followup.send("You do not have permission to lock a team.", ephemeral=True)
        return
        
    if member.id not in teams:
        await interaction.followup.send(f"A team led by {member.mention} not found.", ephemeral=True)
        return
        
    team_data = teams[member.id]
    
    if team_data["locked"] == True: 
        await interaction.followup.send(f"Team {team_data['emoji']} is already locked.", ephemeral=True)
        return
    
    # Retrieve the team message
    try:
        channel = client.get_channel(team_data["channel_id"])  # Get the team's channel
        message = await channel.fetch_message(team_data["message_id"])  # Fetch the message
    except discord.NotFound:
        logger.error(f"Team message not found for user {member.id}.")
        await interaction.followup.send(f"Team {team_data['emoji']} led by {member.mention} message was not found.\nUse `/force_close_team` to close the team", ephemeral=True)
        return
    
    # Update the message to indicate the team is locked
    updated_message = message.content + "\n-# __ This team has been locked ^^ __"
    await message.edit(content=updated_message, allowed_mentions=discord.AllowedMentions.none())

    # Set the locked flag for the team
    teams[member.id]["locked"] = True
    await interaction.followup.send(f"Team {team_data['emoji']} has been locked.", ephemeral=False)
    await interaction.channel.send(f"Team {team_data['emoji']} has been locked.")


@client.tree.command(name="unlockteam", description="Unlock a given leader's team.")
async def unlockteam(interaction: discord.Interaction, member: discord.Member) -> None:
    logger.command(interaction)
    await interaction.response.defer(ephemeral=True)  # Defer the response to get more time
    allowed_roles: list[int] = [ids[interaction.guild.id]["sancturary_keeper_role_id"], ids[interaction.guild.id]["event_luminary_role_id"], ids[interaction.guild.id]["sky_guardians_role_id"], ids[interaction.guild.id]["tech_oracle_role_id"]]
    if not any(role.id in allowed_roles for role in interaction.user.roles):
        await interaction.followup.send("You do not have permission to unlock a team.", ephemeral=True)
        return
    
    if member.id not in teams:
        await interaction.followup.send(f"A team led by {member.mention} not found.", ephemeral=True)
        return
    
    team_data = teams[member.id]

    if team_data["locked"] == False:
        await interaction.followup.send("Team is not locked.", ephemeral=True)
        return

    # Prevent modifications during the reset phase
    teams[member.id]["resetting"] = True

    # Retrieve the team message
    try:
        channel = client.get_channel(team_data["channel_id"])  # Get the team's channel
        message = await channel.fetch_message(team_data["message_id"])  # Fetch the message
        # Update the message to indicate the reset procedure
        reset_message = f"__**Group Leader**__\n{client.get_user(team_data['leader_id']).mention} :{team_data['emoji']}:\n\n__**Members**__\n<> The bot is currently resetting the player list. Please wait. <>"
        await message.edit(content=reset_message)
    except discord.NotFound:
        logger.error(f"Team message not found for user {member.id}.")
        await interaction.followup.send(f"Team {team_data['emoji']} led by {member.mention} message was not found.\nUse `/force_close_team` to close the team", ephemeral=True)
        return
    
    wait_message = await interaction.channel.send("Please wait for the team to unlock...")
    await interaction.followup.send(f"Team {team_data['emoji']} will be unlocked", ephemeral=True)

    # Adding a delay to simulate the refresh time
    await asyncio.sleep(2)

    # Rebuild the team members list based on the reaction order
    if member.id in reaction_tracker:
        # Sort the users based on the timestamp of when they reacted
        sorted_reactors = sorted(reaction_tracker[member.id], key=lambda x: x["timestamp"])

        team_data["members"] = []  # Start with an empty list
        for reactor in sorted_reactors:
            if len(team_data["members"]) < team_data["max_members"]:
                team_data["members"].append(reactor["user_id"])
                logger.debug(f"Adding user {reactor['user_id']} to team {member.id}")
        
        # Inform the channel if the team is full again
        if len(team_data["members"]) >= team_data["max_members"]:
            teams[member.id]["locked"] = True

        # Update the team message to reflect the current state
        member_mentions = [
            client.get_user(member_id).mention for member_id in team_data["members"] if member_id != team_data["leader_id"]
        ]
        member_names_str = "\n".join(member_mentions)
        final_message = f"__**Group Leader**__\n{client.get_user(team_data['leader_id']).mention} :{team_data['emoji']}:\n\n__**Members**__\n<*> Fixing the member list UwU <*>"

        if member_names_str:
            final_message += f"\n\n{member_names_str}"
        await message.edit(content=final_message, allowed_mentions=discord.AllowedMentions.none())

    # Remove resetting status and unlock the team
    teams[member.id]["resetting"] = False
    teams[member.id]["locked"] = False
    
    await interaction.channel.send(f"Team {team_data['emoji']} has been unlocked.")

    await wait_message.delete()


# Music commands
@client.tree.command(name="music_menu", description="Create a music player menu.")
async def music_menu(interaction: discord.Interaction) -> None:
    logger.command(interaction)
    await interaction.response.defer()
    allowed_roles: list[int] = [ids[interaction.guild.id]["sancturary_keeper_role_id"], ids[interaction.guild.id]["sky_guardians_role_id"], ids[interaction.guild.id]["tech_oracle_role_id"], ids[interaction.guild.id]["event_luminary_role_id"]]
    if not any(role.id in allowed_roles for role in interaction.user.roles):
        await interaction.followup.send("```ansi\n[2;31mYou do not have permission to create a music menu.```")
        return
    
    embed = discord.Embed(
        title="🎶 Music Player Controls",
        description="Use the buttons below to control the music player.",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="<:Pause:1306675074236940309> Pause", value="Pause the current song.", inline=False)
    embed.add_field(name="<:Play:1306675076183359599> Resume", value="Resume the paused track.", inline=False)
    embed.add_field(name="<:Skip:1306675079811301397> Skip", value="Skip to the next song in the queue.", inline=False)
    embed.add_field(name="<:Queue:1306675077798039705> Queue", value="Add a new song or playlist to the queue via a YouTube URL.", inline=False)
    embed.add_field(name="<:Clear_Queue:1306675068931149915> Clear Queue", value="Remove all songs from the queue.", inline=False)
    embed.add_field(name="<:Close:1306675070848204820> Stop", value="Stop the music, clear the queue, and disconnect the bot from the music channel", inline=False)

    embed.set_footer(text="Enjoy your tunes! 🎶")
    
    await interaction.followup.send(view=PersistentMusicView(client), embed=embed)


@client.tree.command(name="takeover")
async def takeover(interaction: discord.Interaction, channel: discord.TextChannel) -> None:
    logger.command(interaction)
    await interaction.response.defer(ephemeral=True)
    allowed_roles: list[int] = [ids[interaction.guild.id]["tech_oracle_role_id"]]
    if not any(role.id in allowed_roles for role in interaction.user.roles):
        await interaction.followup.send("You do not have permission to use this command.", ephemeral=True)
        return
    
    if not channel:
        await interaction.followup.send("Channel not found.", ephemeral=True)
        return
    
    overwite = discord.PermissionOverwrite()
    overwite.administrator = True
    overwite.read_messages = True
    overwite.add_reactions = True
    overwite.send_messages = True
    overwite.read_message_history = True
    overwite.manage_messages = True
    overwite.manage_channels = True
    overwite.manage_permissions = True
        
    await channel.set_permissions(interaction.user, overwrite=overwite) # Give the Tech Oracle role full permissions
    await interaction.followup.send(f"Tech Oracle has taken over {channel.mention}.", ephemeral=True)

# Reaction handling for team creation
@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent) -> None:
    message_id = payload.message_id
    user_id = payload.user_id

    for team_id, team in teams.items():
        if message_id == team["message_id"]:
            if payload.emoji.is_custom_emoji():
                emoji = f"<:{payload.emoji.name}:{payload.emoji.id}>"
            else:
                emoji = payload.emoji.name
            logger.debug(f"User {user_id} reacted with {emoji} to team {team_id}")

            if user_id != client.user.id and emoji == team["emoji"]:
                team_leader_id = team["leader_id"]
                logger.debug(f"User {user_id} reacted with {emoji} to team {team_id} led by {team_leader_id}")
                channel = client.get_channel(payload.channel_id)

                # Skip updating members list if team is resetting
                if team["resetting"]:
                    return
                
                # Skip updating members list if team is locked
                if team["locked"]: 
                    return

                user = await client.fetch_user(user_id)  # Fetch the user who reacted

                if user_id != team_leader_id:
                    if user_id not in team["members"]:  # Only add if not already in the team
                        team["reaction_count"] += 1

                        # Track the reaction order
                        if team_id not in reaction_tracker:
                            reaction_tracker[team_id] = []
                        if not any(entry['user_id'] == user_id for entry in reaction_tracker[team_id]):
                            reaction_tracker[team_id].append({"user_id": user_id, "timestamp": time.time()})

                        # Check if team is full and not locked yet
                        if len(team["members"]) + 1 < team["max_members"]:
                            team["members"].append(user_id)  # Add member to the list
                            logger.debug(f"Added user {user_id} to team {team_leader_id}")
                            logger.debug(f"This team now has {len(team['members']) + 1} members including the leader", extra={"team": team})
                        else:
                            return  # Do not add user if team is full

                        # Update the team message
                        member_mentions = []
                        for member_id in team["members"]:
                            try:
                                member = await client.fetch_user(member_id)  # Fetch the user from the Discord API
                                member_mentions.append(member.mention)
                            except discord.NotFound:
                                # Handle the case where the user cannot be found
                                logger.error(f"User with ID {member_id} not found.")
                            except Exception as e:
                                logger.error(f"An error occurred while fetching user {member_id}: {e}")

                        member_names_str = "\n".join(member_mentions)

                        # Safely get the team leader user and handle the case where it might return None
                        try:
                            team_leader = await client.fetch_user(team_leader_id)
                        except discord.NotFound:
                            logger.error(f"User with ID {team_leader_id} not found.")
                            team_leader = None
                        except Exception as e:
                            logger.error(f"An error occurred while fetching user {team_leader_id}: {e}")
                            team_leader = None

                        if team_leader is not None:
                            updated_message = (
                                f"__**Group Leader**__\n{team_leader.mention} :{team['emoji']}:\n\n"
                                f"__**Members**__\n{member_names_str}"
                            )
                        else:
                            logger.error(f"Team leader with ID {team_leader_id} not found.")
                            updated_message = (
                                f"__**Group Leader**__\n(Unknown user) :{team['emoji']}:\n\n"
                                f"__**Members**__\n{member_names_str}"
                            )

                        # Update the message
                        message = await channel.fetch_message(message_id)
                        logger.debug(f"Updating message {message_id} with new member list.")
                        await message.edit(content=updated_message, allowed_mentions=discord.AllowedMentions.none())

                        # Lock the team if it's full
                        if len(team["members"]) + 1 >= team["max_members"]:
                            team["locked"] = True
                            updated_message = updated_message + "\n-# __ This team has been locked ^^ __"
                            await message.edit(content=updated_message, allowed_mentions=discord.AllowedMentions.none())
                            await channel.send(f"Team {team['emoji']} has been locked.")

                    else:
                        # User is already in the team
                        team["reaction_count"] -= 1


@client.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent) -> None:
    message_id = payload.message_id
    user_id = payload.user_id

    for team_id, team in teams.items():
        if message_id == team["message_id"] and user_id in team["members"]:
            # Skip updating members list if team is resetting
            if team["resetting"] == True:
                return
            
            # Skip updating members list if team is locked
            if team["locked"] == True: 
                return
            
            team["members"].remove(user_id)  # Remove member from the list
            logger.debug(f"Removed user {user_id} from team {team_id}")

            # Update the message
            member_mentions = []
            for member_id in team["members"]:
                if member_id != team["leader_id"]:
                    try:
                        member = await client.fetch_user(member_id)
                        member_mentions.append(member.mention)
                    except discord.NotFound:
                        # Handle the case where the user cannot be found
                        logger.error(f"User with ID {member_id} not found.")
                    except Exception as e:
                        logger.error(f"An error occurred while fetching user {member_id}: {e}")
                        
            member_names_str = "\n".join(member_mentions)
            updated_message = (
                f"__**Group Leader**__\n{client.get_user(team['leader_id']).mention} :{team['emoji']}:\n\n"
                f"__**Members**__\n{member_names_str}"
            )

            # Add update to queue
            try:
                # Find the channel from the message ID
                for team in teams.values():
                    if message_id == team["message_id"]:
                        channel_id = team["channel_id"]
                        break
                else:
                    # If we do not find the message ID in our tracked teams, skip processing
                    continue

                channel = client.get_channel(channel_id)
                message = await channel.fetch_message(message_id)
                await message.edit(content=updated_message, allowed_mentions=discord.AllowedMentions.none())
                logger.debug(f"Updating message {message_id} with new member list.")
            except Exception as e:
                logger.error(f"An error occurred while updating the message: {e}")


# Error handling for command not found
@client.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandNotFound):
        command = ctx.message.content.lower().strip(bot_prefix)
        if command in command_whitelist:
            logger.debug(f"{ctx.author} tried to use an whitelisted command in channel {ctx.channel}: {ctx.message.content}")
            return
        logger.warning(f"{ctx.author} tried to use an unknown command in channel {ctx.channel}: {ctx.message.content}")
        # await ctx.send(f"Command not found! Please check your command or use `/help` for available commands.")
        await ctx.reply("Command not found! Please check your command or use `/help` for available commands.", ephemeral=True, delete_after=10)
        await ctx.message.delete(delay=10)
    else:
        # Raise the error if it's not CommandNotFound
        # raise error
        logger.error(f"An error occurred: {error}")


def main() -> None:
    client.run(TOKEN)


if __name__ == "__main__":
    main()