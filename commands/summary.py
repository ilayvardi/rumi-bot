import discord
from discord import app_commands
from datetime import datetime, timedelta
from typing import List
import asyncio
from groq import Groq
import os

# Import personality
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from personality import RUMI_PERSONALITY

# Initialize Groq client
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

class SummaryCommand(app_commands.Command):
    def __init__(self):
        super().__init__(
            name="summary",
            description="Get a summary of recent chat activity",
            callback=self.execute
        )
    
    @app_commands.describe(
        timeframe="Choose time period or message count",
        amount="Number (e.g., 5 for '5 hours' or '100' for messages)"
    )
    @app_commands.choices(timeframe=[
        app_commands.Choice(name="Hours", value="hours"),
        app_commands.Choice(name="Days", value="days"),
        app_commands.Choice(name="Messages", value="messages"),
    ])
    async def execute(
        self, 
        interaction: discord.Interaction, 
        timeframe: str = None,
        amount: int = None
    ):
        await interaction.response.defer(thinking=True)
        
        # Get the channel where command was called
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("This command only works in text channels.")
            return
        
        # Default values if not specified
        if not timeframe:
            timeframe_value = "days"
            amount = 2
        else:
            timeframe_value = timeframe  # It's already a string now
            if not amount:
                # Default amounts
                amount = 2 if timeframe_value == "days" else 6 if timeframe_value == "hours" else 100
        
        # Fetch messages based on timeframe type
        if timeframe_value == "messages":
            messages = await self.fetch_last_n_messages(channel, amount)
            summary_context = f"last {amount} messages"
        elif timeframe_value == "hours":
            messages = await self.fetch_messages_by_time(channel, hours=amount)
            summary_context = f"last {amount} hour(s)"
        else:  # days
            messages = await self.fetch_messages_by_time(channel, days=amount)
            summary_context = f"last {amount} day(s)"
        
        if not messages:
            await interaction.followup.send(f"No messages found in the {summary_context}.")
            return
        
        # Get summary from Groq
        try:
            # Calculate stats
            total_words = sum(len(msg.split()) for msg in messages)
            
            summary = await self.get_summary(messages, summary_context)
            summary_words = len(summary.split())
            
            # Add stats header
            stats_header = f"📊 **Summary Stats**\n• Period: {summary_context}\n• Messages analyzed: {len(messages)}\n• Total words: ~{total_words:,}\n• Summary length: {summary_words} words\n\n---\n\n"
            
            full_response = stats_header + summary
            
            # Handle Discord's 2000 character limit
            if len(full_response) <= 2000:
                await interaction.followup.send(full_response)
            else:
                # Split into chunks
                chunks = []
                current_chunk = stats_header  # Start with stats
                
                # Split by sections (looking for **bold headers**)
                lines = summary.split('\n')
                for line in lines:
                    if len(current_chunk) + len(line) + 1 > 1950:  # Leave buffer for formatting
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = line
                    else:
                        current_chunk += '\n' + line if current_chunk else line
                
                if current_chunk:
                    chunks.append(current_chunk)
                
                # Send each chunk
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await interaction.followup.send(chunk)
                    else:
                        await interaction.channel.send(chunk)
                        
        except Exception as e:
            await interaction.followup.send(f"Error generating summary: {str(e)}")
    
    async def fetch_messages_by_time(self, channel: discord.TextChannel, days: int = 0, hours: int = 0) -> List[str]:
        """Fetch messages from the channel for the specified time period"""
        if days:
            after = datetime.utcnow() - timedelta(days=days)
        elif hours:
            after = datetime.utcnow() - timedelta(hours=hours)
        else:
            after = datetime.utcnow() - timedelta(days=2)  # Default
        messages = []
        
        async for msg in channel.history(limit=None, after=after, oldest_first=True):
            # Skip bot messages
            if msg.author.bot:
                continue
            
            # Add regular message content
            if msg.content:
                messages.append(f"{msg.author.display_name}: {msg.content}")
            
            # Disabled for now - can re-enable later
            # # Check for text file attachments
            # for attachment in msg.attachments:
            #     if attachment.filename.endswith('.txt'):
            #         try:
            #             # Download and read the text file
            #             file_content = await attachment.read()
            #             text_content = file_content.decode('utf-8', errors='ignore')
            #             
            #             # Add file content with context
            #             messages.append(f"{msg.author.display_name} [shared {attachment.filename}]: {text_content[:2000]}")  # Cap at 2000 chars per file
            #         except Exception as e:
            #             messages.append(f"{msg.author.display_name} [shared {attachment.filename}]: (couldn't read file)")
        
        return messages
    
    async def fetch_last_n_messages(self, channel: discord.TextChannel, n: int) -> List[str]:
        """Fetch the last N messages from the channel"""
        messages = []
        
        async for msg in channel.history(limit=n, oldest_first=False):
            # Skip bot messages
            if msg.author.bot:
                continue
            
            # Add regular message content
            if msg.content:
                messages.append(f"{msg.author.display_name}: {msg.content}")
        
        # Reverse to get chronological order
        return list(reversed(messages))
    
    async def get_summary(self, messages: List[str], context: str) -> str:
        """Get summary from Groq using llama maverick"""
        # Join all messages
        chat_log = "\n".join(messages)
        
        # PRE-CONTEXT: High-level expectations
        pre_context = f"""You're summarizing a Discord conversation from the {context}.
This is a high-level intellectual friend group that discusses complex technical, philosophical, and scientific topics.
They're brilliant AND hilarious - capture both the genius and the chaos.

IMPORTANT: ADAPT YOUR RESPONSE TO THE ACTUAL CONTENT!
- If it's deep philosophical discussion → detailed technical analysis
- If it's shitposting and spam → acknowledge the absurdity with humor
- If it's mixed → capture both aspects
- If nothing happened → be brief and witty about the void

The following structure is a GUIDE, not a rigid template:
• The Vibe (always include)
• Core Ideas (IF there were actual ideas discussed)
• Arguments (IF there were debates)
• Brilliant Moments (IF someone said something clever)
• Comedy Gold (IF there was humor)
• Social Dynamics (IF interesting interpersonal stuff happened)
• Open Questions (IF there are unresolved topics)
• Resources (IF any were shared)

BE CREATIVE with your format based on what actually happened:
- Dense technical discussion? → Focus on the ideas
- Chaos and jokes? → Lean into the humor
- Someone spamming "bla"? → Don't force 8 sections of analysis on nothing

Write naturally, match the energy of what actually happened."""

        # POST-CONTEXT: After seeing the actual messages
        post_context = """Based on the actual conversation above:
- PRESERVE TECHNICAL ACCURACY - use exact terminology, don't dumb down complex ideas
- Include enough detail that someone could continue the conversation intelligently
- Note when someone makes a particularly clever point or connection
- Capture the interpersonal subtext (tensions, alliances, intellectual sparring, roasting)
- If someone shares research/theory, explain what it actually says
- Quote verbatim when someone says something brilliant OR hilarious
- Show how jokes and humor advance or derail the intellectual discussion
- Preserve dark humor, absurdist takes, and intellectual shitposting
- Show how ideas evolved through the discussion, not just end state"""

        # Build the full prompt
        user_prompt = f"""{pre_context}

[CONVERSATION LOGS START]
{chat_log}
[CONVERSATION LOGS END]

{post_context}"""
        
        # Call Groq API with Llama Maverick
        response = await asyncio.to_thread(
            groq_client.chat.completions.create,
            model="meta-llama/llama-4-maverick-17b-128e-instruct",
            messages=[
                {"role": "system", "content": RUMI_PERSONALITY},
                {"role": "user", "content": user_prompt}
            ],
            temperature=1.0
            # No max_tokens limit as requested
        )
        
        return response.choices[0].message.content