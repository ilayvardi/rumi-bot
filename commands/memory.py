import discord
from discord import app_commands
from typing import Optional
import asyncio
import os
import sys

# Import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_client import AIClient
from context_manager import ContextManager

# Initialize clients
ai_client = AIClient()
context_manager = ContextManager()

class MemoryCommand(app_commands.Command):
    def __init__(self):
        super().__init__(
            name="memory",
            description="Manage Rumi's memory and context",
            callback=self.execute
        )
    
    @app_commands.describe(
        action="Memory action to perform",
        user="User to analyze or get context for"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Status", value="status"),
        app_commands.Choice(name="Context", value="context"),
        app_commands.Choice(name="Analyze User", value="analyze"),
        app_commands.Choice(name="Cleanup", value="cleanup"),
    ])
    async def execute(
        self,
        interaction: discord.Interaction,
        action: str = "status",
        user: Optional[discord.Member] = None
    ):
        await interaction.response.defer(thinking=True)
        
        guild_id = str(interaction.guild_id)
        channel_id = str(interaction.channel_id)
        
        if action == "status":
            await self.show_memory_status(interaction, guild_id, channel_id)
        elif action == "context":
            await self.show_conversation_context(interaction, guild_id, channel_id)
        elif action == "analyze" and user:
            await self.analyze_user(interaction, user, guild_id, channel_id)
        elif action == "cleanup":
            await self.cleanup_memory(interaction)
        else:
            await interaction.followup.send("Invalid action or missing user parameter for analysis.")
    
    async def show_memory_status(self, interaction: discord.Interaction, guild_id: str, channel_id: str):
        """Show current memory status"""
        try:
            # Get recent message count
            recent_messages = await context_manager.get_recent_context(guild_id, channel_id, hours=24)
            
            # Count summaries
            context_info = await context_manager.get_conversation_context(guild_id, channel_id)
            summary_count = context_info.count("**") // 2  # Rough estimate
            
            status = f"""🧠 **Rumi's Memory Status**
            
**Current Channel:**
• Recent messages (24h): {len(recent_messages)}
• Stored summaries: ~{summary_count}
• Context depth: {len(context_info.split()) if context_info else 0} words

**Memory Health:**
• Database: ✅ Active
• AI Client: ✅ Connected ({ai_client.model})
• Context tracking: ✅ Enabled

Use `/memory context` to see conversation history or `/memory analyze @user` to analyze someone's communication patterns."""
            
            await interaction.followup.send(status)
            
        except Exception as e:
            await interaction.followup.send(f"Error checking memory status: {str(e)}")
    
    async def show_conversation_context(self, interaction: discord.Interaction, guild_id: str, channel_id: str):
        """Show conversation context"""
        try:
            context = await context_manager.get_conversation_context(guild_id, channel_id)
            
            if len(context) > 1900:
                # Split into chunks
                chunks = []
                current_chunk = "🧠 **Conversation Context**\n\n"
                
                lines = context.split('\n')
                for line in lines:
                    if len(current_chunk) + len(line) > 1900:
                        chunks.append(current_chunk)
                        current_chunk = line
                    else:
                        current_chunk += '\n' + line
                
                if current_chunk:
                    chunks.append(current_chunk)
                
                # Send chunks
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await interaction.followup.send(chunk)
                    else:
                        await interaction.channel.send(chunk)
            else:
                await interaction.followup.send(f"🧠 **Conversation Context**\n\n{context}")
                
        except Exception as e:
            await interaction.followup.send(f"Error retrieving context: {str(e)}")
    
    async def analyze_user(self, interaction: discord.Interaction, user: discord.Member, 
                          guild_id: str, channel_id: str):
        """Analyze a user's communication patterns"""
        try:
            # Get user's recent messages from their dedicated table
            user_messages_data = await context_manager.get_user_messages(str(user.id), guild_id, limit=200, hours=168)
            user_messages = [msg['content'] for msg in user_messages_data]
            
            if not user_messages:
                await interaction.followup.send(f"No recent messages found for {user.display_name} in this channel.")
                return
            
            # Analyze personality
            analysis = await ai_client.analyze_user_personality(user_messages, user.display_name)
            
            # Update context manager with new schema
            await context_manager.update_user_profile(
                str(user.id), 
                guild_id,
                user.display_name,
                analysis.get('personality_notes'),
                analysis.get('common_topics', []),
                analysis.get('interaction_style')
            )
            
            # Format response
            topics_str = ', '.join(analysis.get('common_topics', [])) if analysis.get('common_topics') else 'None identified'
            
            response = f"""🔍 **User Analysis: {user.display_name}**

**Communication Style:** {analysis.get('interaction_style', 'Not determined')}

**Common Topics:** {topics_str}

**Personality Notes:**
{analysis.get('personality_notes', 'No specific patterns identified')}

**Analysis based on {len(user_messages)} recent messages**

*This analysis has been saved to my memory for future interactions.*"""
            
            await interaction.followup.send(response)
            
        except Exception as e:
            await interaction.followup.send(f"Error analyzing user: {str(e)}")
    
    async def cleanup_memory(self, interaction: discord.Interaction):
        """Clean up old memory data"""
        try:
            await context_manager.cleanup_old_data()
            await interaction.followup.send("🧹 **Memory Cleanup Complete**\n\nOld messages and outdated summaries have been cleared while preserving important context.")
        except Exception as e:
            await interaction.followup.send(f"Error during cleanup: {str(e)}")