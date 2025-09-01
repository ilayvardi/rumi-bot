import discord
from discord import app_commands
import asyncio
from typing import List
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from personality import RUMI_PERSONALITY
from ai_client import AIClient
from context_manager import ContextManager

# Initialize AI client and context manager
ai_client = AIClient()
context_manager = ContextManager()

class ChatCommand(app_commands.Command):
    def __init__(self):
        super().__init__(
            name="chat",
            description="Chat with Rumi (optionally with recent context)",
            callback=self.execute,
        )

    @app_commands.describe(
        prompt="What do you want to say to Rumi?",
        context_messages="How many recent messages to include for context",
        ephemeral="Reply only visible to you",
    )
    async def execute(
        self,
        interaction: discord.Interaction,
        prompt: str,
        context_messages: int = 20,
        ephemeral: bool = False,
    ):
        await interaction.response.defer(thinking=True, ephemeral=ephemeral)

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("This command only works in text channels.")
            return

        # Get context from the enhanced memory system
        context_lines: List[str] = []
        
        if interaction.guild:
            # Fetch recent context from database
            recent_messages = await context_manager.get_recent_context(
                str(interaction.guild.id),
                str(channel.id),
                hours=24,
                limit=context_messages
            )
            
            for msg in recent_messages:
                context_lines.append(f"{msg['display_name']}: {msg['content']}")
        
        # If no database context, fetch from Discord API
        if not context_lines and context_messages > 0:
            try:
                async for msg in channel.history(limit=context_messages):
                    if not msg.author.bot and msg.content:
                        context_lines.append(f"{msg.author.display_name}: {msg.content}")
                context_lines.reverse()  # Chronological order
            except Exception as e:
                print(f"Error fetching channel history: {e}")

        # Get user profile for personalized response
        user_context = None
        if interaction.guild:
            user_context = await context_manager.get_user_profile(
                str(interaction.user.id),
                str(interaction.guild.id)
            )

        # Build conversation context
        conversation_context = "\n".join(context_lines) if context_lines else "No recent context available"
        
        # Generate response using AI client
        response = await ai_client.generate_contextual_response(
            prompt,
            user_context,
            conversation_context,
            RUMI_PERSONALITY
        )

        # Handle Discord's 2000 character limit
        if len(response) <= 2000:
            await interaction.followup.send(response)
        else:
            chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await interaction.followup.send(chunk)
                else:
                    await interaction.channel.send(chunk)