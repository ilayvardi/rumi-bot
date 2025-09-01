import discord
from discord import app_commands
from typing import List
import asyncio
import random
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

class RuminateCommand(app_commands.Command):
    def __init__(self):
        super().__init__(
            name="ruminate",
            description="Rumi thinks to herself based on a random spark and recent context",
            callback=self.execute,
        )

    @app_commands.describe(
        messages="How many recent messages to consider (context)",
        style="Seed style",
        ephemeral="Reply only visible to you",
    )
    @app_commands.choices(
        style=[
            app_commands.Choice(name="Random", value="random"),
            app_commands.Choice(name="Whimsical", value="whimsical"),
            app_commands.Choice(name="Technical", value="technical"),
            app_commands.Choice(name="Philosophical", value="philosophical"),
        ]
    )
    async def execute(
        self,
        interaction: discord.Interaction,
        messages: int = 10,
        style: str = "random",
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
                limit=messages
            )
            
            for msg in recent_messages:
                context_lines.append(f"{msg['display_name']}: {msg['content']}")
        
        # If no database context, fetch from Discord API
        if not context_lines and messages > 0:
            try:
                async for msg in channel.history(limit=messages):
                    if not msg.author.bot and msg.content:
                        context_lines.append(f"{msg.author.display_name}: {msg.content}")
                context_lines.reverse()  # Chronological order
            except Exception as e:
                print(f"Error fetching channel history: {e}")

        # Get conversation context for deeper rumination
        conversation_summary = ""
        if interaction.guild:
            conversation_summary = await context_manager.get_conversation_context(
                str(interaction.guild.id),
                str(channel.id),
                days_back=7
            )

        # Style seeds for rumination
        style_seeds = {
            "whimsical": [
                "What if gravity worked backwards on Tuesdays?",
                "The philosophical implications of rubber ducks",
                "Why do we park in driveways and drive on parkways?",
                "The secret lives of semicolons",
            ],
            "technical": [
                "The elegance of recursion in nature and code",
                "What if CPUs could dream?",
                "The entropy of a perfectly organized codebase",
                "Database normalization as a metaphor for life",
            ],
            "philosophical": [
                "The nature of consciousness in distributed systems",
                "If a tree falls in a forest with no error logging",
                "The ship of Theseus but it's a git repository",
                "Free will vs deterministic algorithms",
            ],
        }

        # Select style
        if style == "random":
            style = random.choice(["whimsical", "technical", "philosophical"])
        
        seeds = style_seeds.get(style, style_seeds["philosophical"])
        spark = random.choice(seeds)

        # Build rumination prompt
        system_prompt = f"""{RUMI_PERSONALITY}

You're ruminating - thinking out loud based on recent conversations and a random spark of thought.
This isn't a direct response to anyone, but a stream of consciousness that might reference recent topics.

Style: {style.capitalize()}
Be creative, meandering, and genuinely thoughtful. Connect disparate ideas. Wonder about things.
Sometimes contradict yourself. Sometimes get lost in tangents. Be authentically contemplative."""

        user_prompt = f"""RECENT CONVERSATION:
{chr(10).join(context_lines) if context_lines else "No recent messages"}

BROADER CONTEXT:
{conversation_summary[:500] if conversation_summary else "No broader context"}

SPARK OF THOUGHT: {spark}

Now ruminate freely, letting your thoughts wander where they will..."""

        # Generate rumination
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await ai_client.get_completion(messages, temperature=0.95)

        # Format response
        formatted_response = f"*💭 Rumi ruminating ({style})...*\n\n{response}"

        # Handle Discord's 2000 character limit
        if len(formatted_response) <= 2000:
            await interaction.followup.send(formatted_response)
        else:
            # Split at sentence boundaries if possible
            chunks = []
            current_chunk = "*💭 Rumi ruminating...*\n\n"
            sentences = response.split('. ')
            
            for sentence in sentences:
                if len(current_chunk) + len(sentence) + 2 < 2000:
                    current_chunk += sentence + '. '
                else:
                    chunks.append(current_chunk.rstrip())
                    current_chunk = sentence + '. '
            
            if current_chunk.strip():
                chunks.append(current_chunk.rstrip())
            
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await interaction.followup.send(chunk)
                else:
                    await asyncio.sleep(1)
                    await interaction.channel.send(chunk)