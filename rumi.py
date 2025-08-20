#!/usr/bin/env python3
import os
import discord
from discord import app_commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import commands
from commands.summary import SummaryCommand

class Rumi(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Need this to read channel history
        intents.guilds = True
        intents.messages = True  # Need this for message events
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
    
    async def setup_hook(self):
        # Register commands
        self.tree.add_command(SummaryCommand())
        
        # Sync commands (use guild for faster testing if GUILD_ID is set)
        guild_id = os.getenv("GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            # Sync to guild ONLY (not globally)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            # Clear any global commands
            self.tree.clear_commands(guild=None)
            await self.tree.sync()  # Sync empty global commands
            print(f"Commands synced to guild {guild_id} only (cleared global)")
        else:
            await self.tree.sync()
            print("Commands synced globally")
    
    async def on_ready(self):
        print(f'Rumi has awakened as {self.user}')

def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("Missing DISCORD_TOKEN in .env")
    
    bot = Rumi()
    bot.run(token)

if __name__ == "__main__":
    main()