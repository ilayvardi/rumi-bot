#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import sqlite3
import tempfile
from datetime import datetime, timedelta
import asyncio
from context_manager import ContextManager

@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        temp_path = tmp.name
    yield temp_path
    os.unlink(temp_path)

@pytest.fixture
def context_manager(temp_db):
    """Create ContextManager with temporary database"""
    return ContextManager(db_path=temp_db)

def test_database_initialization(context_manager, temp_db):
    """Test that database initializes with all required tables"""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    # Check all core tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    required_tables = [
        'guilds', 'channels', 'users', 'messages',
        'user_profiles', 'context_summaries', 'conversation_threads'
    ]
    
    for table in required_tables:
        assert table in tables, f"Table {table} not found in database"
    
    conn.close()

def test_foreign_key_constraints(context_manager, temp_db):
    """Test that foreign key constraints are properly enforced"""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = ON')
    
    # Try to insert message without user - should fail
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute("""
            INSERT INTO messages (user_id, guild_id, channel_id, content)
            VALUES ('nonexistent_user', 'guild1', 'channel1', 'test')
        """)
    
    conn.close()

@pytest.mark.asyncio
async def test_store_message(context_manager):
    """Test message storage with auto-registration"""
    await context_manager.store_message(
        guild_id='test_guild',
        channel_id='test_channel',
        user_id='test_user',
        username='TestUser',
        display_name='Test Display',
        content='Test message content',
        message_type='user'
    )
    
    # Verify message was stored
    conn = sqlite3.connect(context_manager.db_path)
    cursor = conn.cursor()
    
    # Check main messages table
    cursor.execute("SELECT * FROM messages WHERE user_id = 'test_user'")
    message = cursor.fetchone()
    assert message is not None
    assert 'Test message content' in str(message)
    
    # Check user was auto-registered
    cursor.execute("SELECT * FROM users WHERE user_id = 'test_user'")
    user = cursor.fetchone()
    assert user is not None
    assert 'TestUser' in str(user)
    
    # Check per-user table was created
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_messages_test_user'")
    user_table = cursor.fetchone()
    assert user_table is not None
    
    conn.close()

@pytest.mark.asyncio
async def test_user_profile_analysis(context_manager):
    """Test user profile analysis functionality"""
    # Store multiple messages
    for i in range(5):
        await context_manager.store_message(
            guild_id='guild1',
            channel_id='channel1',
            user_id='user1',
            username='User1',
            display_name='User One',
            content=f'Python is great! Message {i}',
            message_type='user'
        )
    
    # Analyze user
    profile = await context_manager.analyze_user('user1', 'guild1')
    
    assert profile is not None
    assert profile['message_count'] == 5
    assert 'Python' in str(profile.get('common_topics', []))

@pytest.mark.asyncio
async def test_conversation_context(context_manager):
    """Test conversation context retrieval"""
    # Store a summary
    await context_manager.store_summary(
        guild_id='guild1',
        channel_id='channel1',
        summary='Previous discussion about Python',
        message_count=10,
        start_time=datetime.utcnow() - timedelta(days=2),
        end_time=datetime.utcnow() - timedelta(days=1)
    )
    
    # Get context
    context = await context_manager.get_conversation_context('guild1', 'channel1')
    
    assert context is not None
    assert 'Python' in context

@pytest.mark.asyncio
async def test_cleanup_old_data(context_manager):
    """Test data cleanup functionality"""
    # Store old message
    conn = sqlite3.connect(context_manager.db_path)
    cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = ON')
    
    # Register entities first
    cursor.execute("INSERT INTO guilds (guild_id) VALUES ('old_guild')")
    cursor.execute("INSERT INTO channels (channel_id, guild_id) VALUES ('old_channel', 'old_guild')")
    cursor.execute("INSERT INTO users (user_id, username) VALUES ('old_user', 'OldUser')")
    
    # Insert old message
    old_time = datetime.utcnow() - timedelta(days=40)
    cursor.execute("""
        INSERT INTO messages (user_id, guild_id, channel_id, content, timestamp)
        VALUES ('old_user', 'old_guild', 'old_channel', 'Old message', ?)
    """, (old_time,))
    
    # Insert recent message
    cursor.execute("""
        INSERT INTO messages (user_id, guild_id, channel_id, content)
        VALUES ('old_user', 'old_guild', 'old_channel', 'Recent message')
    """)
    
    conn.commit()
    conn.close()
    
    # Run cleanup
    await context_manager.cleanup_old_data(days=30)
    
    # Check results
    conn = sqlite3.connect(context_manager.db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT content FROM messages")
    messages = cursor.fetchall()
    
    assert len(messages) == 1
    assert 'Recent message' in str(messages[0])
    
    conn.close()

if __name__ == '__main__':
    pytest.main([__file__, '-v'])