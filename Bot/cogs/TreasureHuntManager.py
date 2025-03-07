import discord
from discord import ChannelType, app_commands
from discord.ext import commands
from discord.ui import View, Select

from functions import load_ids, create_connection, close_connection, get_accepted_rules, get_rule_channels, create_rule_channel, remove_rule_channel, set_accepted_rules, get_rule_channel

# local imports
from logger import logger

ids = load_ids()

class TreasureHuntManager(commands.Cog):
    def __init__(self, client: commands.Bot) -> None:
        self.client = client
    
    # Check if the user is a runner or Tech Oracle or above
    def is_eventlumi() -> bool:
        async def predicate(interaction: discord.Interaction) -> bool:
            allowed_roles: list[int] = [ids[interaction.guild.id]["sancturary_keeper_role_id"], ids[interaction.guild.id]["event_luminary_role_id"], ids[interaction.guild.id]["sky_guardians_role_id"], ids[interaction.guild.id]["tech_oracle_role_id"]]
            if any(role.id in allowed_roles for role in interaction.user.roles):
                logger.debug("User has the required role to use this command.", {"user_id": interaction.user.id, "username": interaction.user.name, "display_name": interaction.user.display_name, "guild_id": interaction.guild.id, "guild_name": interaction.guild.name, "channel_id": interaction.channel.id, "channel_name": interaction.channel.name})
                return True
            logger.info("User does not have the required role to use this command.", {"user_id": interaction.user.id, "username": interaction.user.name, "display_name": interaction.user.display_name, "guild_id": interaction.guild.id, "guild_name": interaction.guild.name, "channel_id": interaction.channel.id, "channel_name": interaction.channel.name})
            await interaction.response.send_message("You do not have the required role to use this command.", ephemeral=True)
            return False
        return app_commands.check(predicate)
    
    @app_commands.command(name="start_treasure_round", description="sets up a round for a treasure run.")
    @is_eventlumi()
    async def setupTreasureRun(self, interaction: discord.Interaction, roundnr: int) -> None:
        logger.command(interaction)
        await interaction.response.send_message(f"Setting up the treasure run round: {roundnr}", ephemeral=True)
        
        threads = interaction.channel.threads
        for thread in threads:
            await thread.edit(archived=True, reason="Next Treasure Run Round Setup")
        
        await interaction.channel.send("", view=PersistentSubmitView(self.client, interaction.channel, roundnr))
    
    @app_commands.command(name="clear_treasure_run", description="removes all treasure run threads.")
    @is_eventlumi()
    async def clearTreasureRun(self, interaction: discord.Interaction) -> None:
        logger.command(interaction)
        await interaction.response.send_message(f"Removing all threads on this channel", ephemeral=True)
        
        # threads = interaction.channel.archived_threads(private=True)
        # for thread in threads.iter(): # TODO: this is not working, need to fix
        #     await thread.delete(reason="Treasure Run Cleanup")
        
        threads = interaction.channel.threads
        for thread in threads:
            if thread.is_private():
                await thread.delete(reason="Treasure Run Cleanup")
            else:
                await thread.edit(archived=True, reason="Treasure Run Cleanup")
        
        await interaction.followup.send("All threads have been removed.", ephemeral=True)

class PersistentSubmitView(discord.ui.View):
    def __init__(self, client: commands.Bot, channel: discord.abc.GuildChannel, roundNr: int) -> None:
        super().__init__(timeout=None)  
        self.add_item(discord.ui.Button(label="🪙 I have found the treasure!! 🪙", style=discord.ButtonStyle.blurple, custom_id=f"treasure_run_submit{channel.id}"))
        self.children[-1].callback = self.submit_callback
        self.client = client
        self.channel = channel
        self.roundNr = roundNr

    async def submit_callback(self, interaction: discord.Interaction) -> None:
        logger.command(interaction)
        await interaction.response.defer()
        
        if not self.channel:
            logger.warning("Channel not found.")
            return
        
        thread = await self.channel.create_thread(
            name=f"Round {self.roundNr} - {interaction.user.display_name}",
            type=ChannelType.private_thread,
            invitable=False,
            auto_archive_duration=60,
            reason="Treasure Run Submission",
        )
        
        await interaction.followup.send(f"Congratulations on finding the treasure!!\nYou can now submit your proof in {thread.jump_url}", ephemeral=True)
        
        await thread.send(f"# **Round {self.roundNr}**\n{interaction.user.mention} Congratulations on finding the treasure!!\nPlease submit your proof here so that we can verify it!")