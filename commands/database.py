import discord
from discord import app_commands
from typing import Optional
import asyncio
import os
import sys

# Import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from context_manager import ContextManager

# Initialize context manager
context_manager = ContextManager()

class DatabaseCommand(app_commands.Command):
    def __init__(self):
        super().__init__(
            name="database",
            description="Explore database structure and user tables",
            callback=self.execute
        )
    
    @app_commands.describe(
        action="Database action to perform",
        user="User to examine their dedicated table"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Schema", value="schema"),
        app_commands.Choice(name="Users", value="users"),
        app_commands.Choice(name="User Stats", value="user_stats"),
        app_commands.Choice(name="User Messages", value="user_messages"),
        app_commands.Choice(name="Tables", value="tables"),
    ])
    async def execute(
        self,
        interaction: discord.Interaction,
        action: str = "schema",
        user: Optional[discord.Member] = None
    ):
        await interaction.response.defer(thinking=True)
        
        guild_id = str(interaction.guild_id)
        
        if action == "schema":
            await self.show_schema(interaction)
        elif action == "users":
            await self.list_users(interaction, guild_id)
        elif action == "user_stats" and user:
            await self.show_user_stats(interaction, user, guild_id)
        elif action == "user_messages" and user:
            await self.show_user_messages(interaction, user, guild_id)
        elif action == "tables":
            await self.list_tables(interaction)
        else:
            await interaction.followup.send("Invalid action or missing user parameter.")
    
    async def show_schema(self, interaction: discord.Interaction):
        """Show database schema"""
        schema_info = """🗄️ **Database Schema**

**Core Tables:**
• `guilds` - Guild information and activity tracking
• `channels` - Channel registry with guild relationships
• `users` - Master user registry (cross-guild)
• `messages` - Unified message storage with foreign keys

**Analysis Tables:**
• `user_profiles` - Personality analysis per user per guild
• `context_summaries` - Generated conversation summaries
• `conversation_threads` - Topic and participant tracking

**Dynamic Tables:**
• `user_messages_{user_id}` - Individual user message storage
  - Created automatically for each user
  - Contains user's messages across all guilds
  - Linked to main messages table via foreign key

**Key Features:**
• Foreign key relationships for data integrity
• Per-user tables for efficient querying
• Automatic user/guild/channel registration
• Comprehensive indexing for performance"""
        
        await interaction.followup.send(schema_info)
    
    async def list_users(self, interaction: discord.Interaction, guild_id: str):
        """List users in database"""
        try:
            users = await context_manager.list_users(guild_id, limit=20)
            
            if not users:
                await interaction.followup.send("No users found in database.")
                return
            
            user_list = ["👥 **Users in Database**\n"]
            
            for user in users:
                user_line = f"• **{user['display_name']}** (@{user['username']})"
                if 'guild_messages' in user:
                    user_line += f" - {user['guild_messages']} messages in this guild"
                else:
                    user_line += f" - {user['total_messages']} total messages"
                user_line += f" (last seen: {user['last_seen'][:10]})"
                user_list.append(user_line)
            
            response = "\n".join(user_list)
            
            if len(response) > 2000:
                # Split response
                chunks = []
                current = "👥 **Users in Database**\n"
                for line in user_list[1:]:  # Skip header
                    if len(current) + len(line) > 1900:
                        chunks.append(current)
                        current = line
                    else:
                        current += "\n" + line
                if current:
                    chunks.append(current)
                
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await interaction.followup.send(chunk)
                    else:
                        await interaction.channel.send(chunk)
            else:
                await interaction.followup.send(response)
                
        except Exception as e:
            await interaction.followup.send(f"Error listing users: {str(e)}")
    
    async def show_user_stats(self, interaction: discord.Interaction, user: discord.Member, guild_id: str):
        """Show detailed user statistics"""
        try:
            stats = await context_manager.get_user_stats(str(user.id), guild_id)
            
            if not stats.get('username'):
                await interaction.followup.send(f"No data found for {user.display_name} in database.")
                return
            
            response = f"""📊 **User Statistics: {user.display_name}**

**Basic Info:**
• Username: @{stats['username']}
• Display Name: {stats['display_name']}
• User ID: `{stats['user_id']}`

**Activity:**
• Total Messages: {stats['total_messages']}
• First Seen: {stats.get('first_seen', 'Unknown')[:16]}
• Last Seen: {stats.get('last_seen', 'Unknown')[:16]}"""
            
            if guild_id and stats.get('guild_message_count'):
                response += f"""

**This Guild:**
• Messages: {stats['guild_message_count']}
• Avg Words/Message: {stats.get('avg_word_count', 0)}
• First Message: {stats.get('first_message', 'Unknown')[:16]}
• Last Message: {stats.get('last_message', 'Unknown')[:16]}"""
            
            response += f"""

**Database:**
• Has Dedicated Table: {'✅' if stats.get('has_dedicated_table') else '❌'}"""
            
            # Get profile if exists
            profile = await context_manager.get_user_profile(str(user.id), guild_id)
            if profile and profile.get('personality_notes'):
                response += f"""

**Profile Analysis:**
• Style: {profile.get('interaction_style', 'Unknown')}
• Topics: {', '.join(profile.get('common_topics', []))}
• Notes: {profile.get('personality_notes', 'None')[:200]}"""
            
            await interaction.followup.send(response)
            
        except Exception as e:
            await interaction.followup.send(f"Error getting user stats: {str(e)}")
    
    async def show_user_messages(self, interaction: discord.Interaction, user: discord.Member, guild_id: str):
        """Show recent messages from user's dedicated table"""
        try:
            messages = await context_manager.get_user_messages(str(user.id), guild_id, limit=10)
            
            if not messages:
                await interaction.followup.send(f"No messages found for {user.display_name} in their dedicated table.")
                return
            
            response = f"💬 **Recent Messages from {user.display_name}'s Table**\n\n"
            
            for msg in messages[-5:]:  # Show last 5 messages
                timestamp = msg['timestamp'][:16]  # YYYY-MM-DD HH:MM
                content = msg['content'][:100] + ('...' if len(msg['content']) > 100 else '')
                response += f"**{timestamp}** ({msg['word_count']} words): {content}\n\n"
            
            response += f"*Showing 5 of {len(messages)} recent messages*"
            
            await interaction.followup.send(response)
            
        except Exception as e:
            await interaction.followup.send(f"Error getting user messages: {str(e)}")
    
    async def list_tables(self, interaction: discord.Interaction):
        """List all tables in database"""
        try:
            import sqlite3
            import asyncio
            
            def get_tables():
                conn = sqlite3.connect(context_manager.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                tables = cursor.fetchall()
                conn.close()
                return [table[0] for table in tables]
            
            tables = await asyncio.to_thread(get_tables)
            
            core_tables = []
            user_tables = []
            
            for table in tables:
                if table.startswith('user_messages_'):
                    user_tables.append(table)
                else:
                    core_tables.append(table)
            
            response = f"""🗃️ **Database Tables**

**Core Tables ({len(core_tables)}):**
{chr(10).join(f'• `{table}`' for table in core_tables)}

**User Message Tables ({len(user_tables)}):**
{chr(10).join(f'• `{table}`' for table in user_tables[:10])}"""
            
            if len(user_tables) > 10:
                response += f"\n• ... and {len(user_tables) - 10} more user tables"
            
            await interaction.followup.send(response)
            
        except Exception as e:
            await interaction.followup.send(f"Error listing tables: {str(e)}")