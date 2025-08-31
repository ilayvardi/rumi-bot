#!/usr/bin/env python3
import sqlite3
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import os

class ContextManager:
    """Manages bot memory with relational database design and per-user tables"""
    
    def __init__(self, db_path: str = "rumi_memory.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with proper relational schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Enable foreign key support
        cursor.execute('PRAGMA foreign_keys = ON')
        
        # Core tables first
        
        # Guilds table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id TEXT PRIMARY KEY,
                guild_name TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Channels table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                channel_id TEXT PRIMARY KEY,
                guild_id TEXT,
                channel_name TEXT,
                channel_type TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            )
        ''')
        
        # Users table (master user registry)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                display_name TEXT,
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_messages INTEGER DEFAULT 0
            )
        ''')
        
        # User profiles (personality analysis per user per guild)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                guild_id TEXT,
                personality_notes TEXT,
                common_topics TEXT,  -- JSON array
                interaction_style TEXT,
                message_count INTEGER DEFAULT 0,
                analysis_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id),
                UNIQUE(user_id, guild_id)
            )
        ''')
        
        # Messages table (unified with foreign keys)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                guild_id TEXT,
                channel_id TEXT,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                message_type TEXT DEFAULT 'user',
                reply_to_id INTEGER,
                edited_at DATETIME,
                word_count INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id),
                FOREIGN KEY (channel_id) REFERENCES channels(channel_id),
                FOREIGN KEY (reply_to_id) REFERENCES messages(id)
            )
        ''')
        
        # Individual user message tables (dynamically created)
        # Format: user_messages_{user_id}
        
        # Context summaries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS context_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                channel_id TEXT,
                summary TEXT,
                message_count INTEGER,
                start_time DATETIME,
                end_time DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id),
                FOREIGN KEY (channel_id) REFERENCES channels(channel_id)
            )
        ''')
        
        # Conversation threads table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_threads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                channel_id TEXT,
                thread_name TEXT,
                participants TEXT,  -- JSON array of user_ids
                topic_keywords TEXT,  -- JSON array
                start_time DATETIME,
                last_activity DATETIME,
                message_count INTEGER DEFAULT 0,
                summary TEXT,
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id),
                FOREIGN KEY (channel_id) REFERENCES channels(channel_id)
            )
        ''')
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_user_time ON messages(user_id, timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_channel_time ON messages(channel_id, timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_guild_time ON messages(guild_id, timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen)')
        
        conn.commit()
        conn.close()
    
    async def store_message(self, guild_id: str, channel_id: str, user_id: str, 
                          username: str, display_name: str, content: str, 
                          message_type: str = 'user', reply_to_id: int = None):
        """Store a message with proper relational structure"""
        await asyncio.to_thread(self._store_message_sync, 
                              guild_id, channel_id, user_id, username, 
                              display_name, content, message_type, reply_to_id)
    
    def _store_message_sync(self, guild_id: str, channel_id: str, user_id: str,
                          username: str, display_name: str, content: str, 
                          message_type: str, reply_to_id: int):
        """Synchronous message storage with relational integrity"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Enable foreign keys
            cursor.execute('PRAGMA foreign_keys = ON')
            
            # Ensure guild exists
            cursor.execute('''
                INSERT OR IGNORE INTO guilds (guild_id, guild_name, last_activity)
                VALUES (?, ?, ?)
            ''', (guild_id, f"Guild_{guild_id}", datetime.utcnow()))
            
            # Update guild last activity
            cursor.execute('''
                UPDATE guilds SET last_activity = ? WHERE guild_id = ?
            ''', (datetime.utcnow(), guild_id))
            
            # Ensure channel exists
            cursor.execute('''
                INSERT OR IGNORE INTO channels (channel_id, guild_id, channel_name)
                VALUES (?, ?, ?)
            ''', (channel_id, guild_id, f"Channel_{channel_id}"))
            
            # Ensure user exists
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username, display_name, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, display_name, datetime.utcnow(), datetime.utcnow()))
            
            # Update user info
            cursor.execute('''
                UPDATE users 
                SET username = ?, display_name = ?, last_seen = ?, total_messages = total_messages + 1
                WHERE user_id = ?
            ''', (username, display_name, datetime.utcnow(), user_id))
            
            # Store message in main table
            word_count = len(content.split())
            cursor.execute('''
                INSERT INTO messages (user_id, guild_id, channel_id, content, timestamp, 
                                    message_type, reply_to_id, word_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, guild_id, channel_id, content, datetime.utcnow(), 
                  message_type, reply_to_id, word_count))
            
            message_id = cursor.lastrowid
            
            # Create user-specific table if it doesn't exist
            safe_user_id = user_id.replace('-', '_').replace('@', '_').replace('.', '_')
            user_table = f"user_messages_{safe_user_id}"
            
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {user_table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER,
                    guild_id TEXT,
                    channel_id TEXT,
                    content TEXT,
                    timestamp DATETIME,
                    word_count INTEGER,
                    reply_to_id INTEGER,
                    FOREIGN KEY (message_id) REFERENCES messages(id)
                )
            ''')
            
            # Store in user-specific table
            cursor.execute(f'''
                INSERT INTO {user_table} (message_id, guild_id, channel_id, content, timestamp, word_count, reply_to_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (message_id, guild_id, channel_id, content, datetime.utcnow(), word_count, reply_to_id))
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            print(f"Error storing message: {e}")
        finally:
            conn.close()
    
    async def get_recent_context(self, guild_id: str, channel_id: str, 
                               hours: int = 24, limit: int = 100) -> List[Dict]:
        """Get recent messages for context with user details"""
        return await asyncio.to_thread(self._get_recent_context_sync, 
                                     guild_id, channel_id, hours, limit)
    
    def _get_recent_context_sync(self, guild_id: str, channel_id: str, 
                               hours: int, limit: int) -> List[Dict]:
        """Synchronous context retrieval with JOIN"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = datetime.utcnow() - timedelta(hours=hours)
        
        cursor.execute('''
            SELECT m.user_id, u.username, u.display_name, m.content, m.timestamp, 
                   m.message_type, m.word_count, m.reply_to_id
            FROM messages m
            JOIN users u ON m.user_id = u.user_id
            WHERE m.guild_id = ? AND m.channel_id = ? AND m.timestamp > ?
            ORDER BY m.timestamp DESC
            LIMIT ?
        ''', (guild_id, channel_id, since, limit))
        
        messages = []
        for row in cursor.fetchall():
            messages.append({
                'user_id': row[0],
                'username': row[1],
                'display_name': row[2],
                'content': row[3],
                'timestamp': row[4],
                'message_type': row[5],
                'word_count': row[6],
                'reply_to_id': row[7]
            })
        
        conn.close()
        return list(reversed(messages))  # Return chronological order
    
    async def store_summary(self, guild_id: str, channel_id: str, summary: str,
                          message_count: int, start_time: datetime, end_time: datetime):
        """Store a conversation summary"""
        await asyncio.to_thread(self._store_summary_sync, 
                              guild_id, channel_id, summary, message_count, start_time, end_time)
    
    def _store_summary_sync(self, guild_id: str, channel_id: str, summary: str,
                          message_count: int, start_time: datetime, end_time: datetime):
        """Synchronous summary storage"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO context_summaries (guild_id, channel_id, summary, message_count, start_time, end_time)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (guild_id, channel_id, summary, message_count, start_time, end_time))
        
        conn.commit()
        conn.close()
    
    async def get_conversation_context(self, guild_id: str, channel_id: str,
                                     days_back: int = 7) -> str:
        """Get conversation context including recent summaries"""
        return await asyncio.to_thread(self._get_conversation_context_sync,
                                     guild_id, channel_id, days_back)
    
    def _get_conversation_context_sync(self, guild_id: str, channel_id: str,
                                     days_back: int) -> str:
        """Get conversation context synchronously"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = datetime.utcnow() - timedelta(days=days_back)
        
        # Get recent summaries
        cursor.execute('''
            SELECT summary, start_time, end_time, message_count
            FROM context_summaries 
            WHERE guild_id = ? AND channel_id = ? AND created_at > ?
            ORDER BY created_at ASC
        ''', (guild_id, channel_id, since))
        
        summaries = cursor.fetchall()
        conn.close()
        
        if not summaries:
            return "No recent conversation context available."
        
        context_parts = ["## Recent Conversation Context\n"]
        for summary, start_time, end_time, msg_count in summaries:
            context_parts.append(f"**{start_time} - {end_time}** ({msg_count} messages):")
            context_parts.append(summary)
            context_parts.append("---")
        
        return "\n".join(context_parts)
    
    async def update_user_profile(self, user_id: str, guild_id: str, username: str,
                                personality_notes: str = None,
                                common_topics: List[str] = None,
                                interaction_style: str = None):
        """Update user personality/context data per guild"""
        await asyncio.to_thread(self._update_user_profile_sync,
                              user_id, guild_id, username, personality_notes, common_topics, interaction_style)
    
    def _update_user_profile_sync(self, user_id: str, guild_id: str, username: str,
                                personality_notes: str, common_topics: List[str],
                                interaction_style: str):
        """Synchronous user profile update"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('PRAGMA foreign_keys = ON')
            
            # Get message count for this user in this guild
            cursor.execute('''
                SELECT COUNT(*) FROM messages WHERE user_id = ? AND guild_id = ?
            ''', (user_id, guild_id))
            message_count = cursor.fetchone()[0]
            
            # Upsert user profile
            cursor.execute('''
                INSERT OR REPLACE INTO user_profiles 
                (user_id, guild_id, personality_notes, common_topics, interaction_style, message_count, analysis_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, guild_id, personality_notes, 
                  json.dumps(common_topics) if common_topics else None,
                  interaction_style, message_count, datetime.utcnow()))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error updating user profile: {e}")
        finally:
            conn.close()
    
    async def get_user_profile(self, user_id: str, guild_id: str) -> Optional[Dict]:
        """Get user profile data for specific guild"""
        return await asyncio.to_thread(self._get_user_profile_sync, user_id, guild_id)
    
    def _get_user_profile_sync(self, user_id: str, guild_id: str) -> Optional[Dict]:
        """Synchronous user profile retrieval"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.username, u.display_name, u.total_messages, u.last_seen,
                   p.personality_notes, p.common_topics, p.interaction_style, p.message_count
            FROM users u
            LEFT JOIN user_profiles p ON u.user_id = p.user_id AND p.guild_id = ?
            WHERE u.user_id = ?
        ''', (guild_id, user_id))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'username': row[0],
                'display_name': row[1],
                'total_messages': row[2],
                'last_seen': row[3],
                'personality_notes': row[4],
                'common_topics': json.loads(row[5]) if row[5] else [],
                'interaction_style': row[6],
                'guild_message_count': row[7] or 0
            }
        return None
    
    async def get_user_messages(self, user_id: str, guild_id: str = None, 
                              limit: int = 100, hours: int = None) -> List[Dict]:
        """Get messages from user-specific table"""
        return await asyncio.to_thread(self._get_user_messages_sync, user_id, guild_id, limit, hours)
    
    def _get_user_messages_sync(self, user_id: str, guild_id: str, 
                              limit: int, hours: int) -> List[Dict]:
        """Get user messages from their dedicated table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        safe_user_id = user_id.replace('-', '_').replace('@', '_').replace('.', '_')
        user_table = f"user_messages_{safe_user_id}"
        
        try:
            # Check if user table exists
            cursor.execute('''
                SELECT name FROM sqlite_master WHERE type='table' AND name=?
            ''', (user_table,))
            
            if not cursor.fetchone():
                return []
            
            query = f'SELECT * FROM {user_table}'
            params = []
            
            conditions = []
            if guild_id:
                conditions.append('guild_id = ?')
                params.append(guild_id)
            
            if hours:
                since = datetime.utcnow() - timedelta(hours=hours)
                conditions.append('timestamp > ?')
                params.append(since)
            
            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)
            
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            
            messages = []
            for row in cursor.fetchall():
                messages.append({
                    'id': row[0],
                    'message_id': row[1],
                    'guild_id': row[2],
                    'channel_id': row[3],
                    'content': row[4],
                    'timestamp': row[5],
                    'word_count': row[6],
                    'reply_to_id': row[7]
                })
            
            return list(reversed(messages))  # Chronological order
            
        except Exception as e:
            print(f"Error getting user messages: {e}")
            return []
        finally:
            conn.close()
    
    async def get_user_stats(self, user_id: str, guild_id: str = None) -> Dict:
        """Get comprehensive user statistics"""
        return await asyncio.to_thread(self._get_user_stats_sync, user_id, guild_id)
    
    def _get_user_stats_sync(self, user_id: str, guild_id: str) -> Dict:
        """Get user statistics from both main and user tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {'user_id': user_id}
        
        try:
            # Basic user info
            cursor.execute('''
                SELECT username, display_name, total_messages, first_seen, last_seen
                FROM users WHERE user_id = ?
            ''', (user_id,))
            
            row = cursor.fetchone()
            if row:
                stats.update({
                    'username': row[0],
                    'display_name': row[1],
                    'total_messages': row[2],
                    'first_seen': row[3],
                    'last_seen': row[4]
                })
            
            # Guild-specific stats if requested
            if guild_id:
                cursor.execute('''
                    SELECT COUNT(*), AVG(word_count), MIN(timestamp), MAX(timestamp)
                    FROM messages WHERE user_id = ? AND guild_id = ?
                ''', (user_id, guild_id))
                
                row = cursor.fetchone()
                if row and row[0]:
                    stats.update({
                        'guild_message_count': row[0],
                        'avg_word_count': round(row[1], 2) if row[1] else 0,
                        'first_message': row[2],
                        'last_message': row[3]
                    })
            
            # Check if user has dedicated table
            safe_user_id = user_id.replace('-', '_').replace('@', '_').replace('.', '_')
            user_table = f"user_messages_{safe_user_id}"
            
            cursor.execute('''
                SELECT name FROM sqlite_master WHERE type='table' AND name=?
            ''', (user_table,))
            
            stats['has_dedicated_table'] = bool(cursor.fetchone())
            
        except Exception as e:
            print(f"Error getting user stats: {e}")
        finally:
            conn.close()
        
        return stats
    
    async def list_users(self, guild_id: str = None, limit: int = 50) -> List[Dict]:
        """List users with basic stats"""
        return await asyncio.to_thread(self._list_users_sync, guild_id, limit)
    
    def _list_users_sync(self, guild_id: str, limit: int) -> List[Dict]:
        """List users synchronously"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if guild_id:
            cursor.execute('''
                SELECT u.user_id, u.username, u.display_name, u.total_messages, u.last_seen,
                       COUNT(m.id) as guild_messages
                FROM users u
                LEFT JOIN messages m ON u.user_id = m.user_id AND m.guild_id = ?
                GROUP BY u.user_id
                ORDER BY u.last_seen DESC
                LIMIT ?
            ''', (guild_id, limit))
        else:
            cursor.execute('''
                SELECT user_id, username, display_name, total_messages, last_seen
                FROM users
                ORDER BY last_seen DESC
                LIMIT ?
            ''', (limit,))
        
        users = []
        for row in cursor.fetchall():
            user_data = {
                'user_id': row[0],
                'username': row[1],
                'display_name': row[2],
                'total_messages': row[3],
                'last_seen': row[4]
            }
            if guild_id:
                user_data['guild_messages'] = row[5]
            users.append(user_data)
        
        conn.close()
        return users
    
    async def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old messages and summaries"""
        await asyncio.to_thread(self._cleanup_old_data_sync, days_to_keep)
    
    def _cleanup_old_data_sync(self, days_to_keep: int):
        """Synchronous cleanup of old data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
        
        # Clean old messages from main table (keep summaries longer)
        cursor.execute('DELETE FROM messages WHERE timestamp < ?', (cutoff,))
        
        # Clean old messages from user tables
        cursor.execute('''
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE 'user_messages_%'
        ''')
        
        user_tables = cursor.fetchall()
        for (table_name,) in user_tables:
            cursor.execute(f'DELETE FROM {table_name} WHERE timestamp < ?', (cutoff,))
        
        # Clean very old summaries (keep 90 days)
        summary_cutoff = datetime.utcnow() - timedelta(days=90)
        cursor.execute('DELETE FROM context_summaries WHERE created_at < ?', (summary_cutoff,))
        
        conn.commit()
        conn.close()