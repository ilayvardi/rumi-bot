#!/usr/bin/env python3
import os
import discord
from discord import app_commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import commands
from commands.summary import SummaryCommand
from commands.memory import MemoryCommand
from commands.database import DatabaseCommand
from commands.chat import ChatCommand
from commands.ruminate import RuminateCommand
from context_manager import ContextManager
from ai_client import AIClient

# Initialize global managers
context_manager = ContextManager()
ai_client = AIClient()

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
        self.tree.add_command(MemoryCommand())
        self.tree.add_command(DatabaseCommand())
        self.tree.add_command(ChatCommand())
        self.tree.add_command(RuminateCommand())
        
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
        print(f'AI Model: {ai_client.model}')
        print(f'Memory system: Active')
        
        # Initialize memory cleanup task
        self.cleanup_task = self.loop.create_task(self.memory_cleanup_loop())
    
    async def on_message(self, message):
        # Skip bot messages
        if message.author.bot:
            return
        
        # Store message for context with enhanced schema
        if message.guild:
            await context_manager.store_message(
                str(message.guild.id),
                str(message.channel.id),
                str(message.author.id),
                message.author.name,
                message.author.display_name,
                message.content,
                'user'
            )
    
    async def memory_cleanup_loop(self):
        """Periodic cleanup of old memory data"""
        while True:
            try:
                await asyncio.sleep(86400)  # 24 hours
                await context_manager.cleanup_old_data()
                print("Memory cleanup completed")
            except Exception as e:
                print(f"Memory cleanup error: {e}")

def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("Missing DISCORD_TOKEN in .env")
    
    # Verify AI configuration
    try:
        ai_test = AIClient()
        print(f"AI Client initialized with model: {ai_test.model}")
    except Exception as e:
        print(f"Warning: AI Client initialization failed: {e}")
        print("Bot will start but AI features may not work")
    
    bot = Rumi()
    bot.run(token)

if __name__ == "__main__":
    main()