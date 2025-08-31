# Rumi Bot

<img width="1024" height="1024" alt="rumi" src="https://github.com/user-attachments/assets/7ac9f87e-a787-4c45-9811-6cb18c74ab1d" />

Enhanced Discord bot with persistent memory and OpenAI-compatible API support. Provides intelligent conversation summaries with context awareness and personality analysis.

## Features

- **Smart Summaries**: Contextual conversation analysis with memory of previous discussions
- **Persistent Memory**: SQLite-based storage of conversations, summaries, and user patterns
- **OpenAI Compatible**: Works with OpenAI, Groq, and other compatible API providers
- **User Analysis**: Automatic personality and communication pattern recognition
- **Context Continuity**: Maintains conversation threads across sessions

## Commands

**Summary & Analysis:**
- `/summary [timeframe] [amount]` - Generate intelligent conversation summaries
- `/memory status` - View memory system status
- `/memory context` - Show recent conversation context
- `/memory analyze @user` - Analyze user communication patterns
- `/memory cleanup` - Clean up old data

**Database Management:**
- `/database schema` - Show database structure
- `/database users` - List all users in database
- `/database user_stats @user` - Show detailed user statistics
- `/database user_messages @user` - Show recent messages from user's table
- `/database tables` - List all database tables

## Setup

1. **Environment Configuration**:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` with your configuration:
   ```env
   DISCORD_TOKEN=your_discord_bot_token
   OPENAI_API_KEY=your_openai_key  # or GROQ_API_KEY for Groq
   AI_MODEL=gpt-4o-mini  # or meta-llama/llama-4-maverick-17b-128e-instruct
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Discord Bot Setup**:
   - Create application at https://discord.com/developers/applications
   - Create bot user and get token
   - Enable "Message Content Intent" in bot settings
   - Invite bot with appropriate permissions

4. **Run**:
   ```bash
   python3 rumi.py
   ```

## API Provider Configuration

### OpenAI (Default)
```env
OPENAI_API_KEY=your_openai_key
AI_MODEL=gpt-4o-mini
```

### Groq
```env
GROQ_API_KEY=your_groq_key
OPENAI_BASE_URL=https://api.groq.com/openai/v1
AI_MODEL=meta-llama/llama-4-maverick-17b-128e-instruct
```

### Other OpenAI-Compatible APIs
```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://your-endpoint.com/v1
AI_MODEL=your_model_name
```

## Enhanced Memory System

### Relational Database Design
**Core Tables:**
- `guilds` - Guild information and activity tracking
- `channels` - Channel registry with foreign key relationships
- `users` - Master user registry (cross-guild)
- `messages` - Unified message storage with foreign keys
- `user_profiles` - Personality analysis per user per guild
- `context_summaries` - Generated conversation summaries
- `conversation_threads` - Topic and participant tracking

### Per-User Tables
- `user_messages_{user_id}` - Individual user message storage
- Automatically created for each user
- Contains user's messages across all guilds
- Linked to main messages table via foreign keys
- Optimized for user-specific queries

### Key Features
- **Foreign Key Relationships**: Data integrity and referential consistency
- **Per-User Storage**: Efficient querying of individual user data
- **Automatic Registration**: Users, guilds, and channels auto-created
- **Comprehensive Indexing**: Optimized performance for time-based queries
- **Relational Queries**: JOIN operations for complex data analysis

Data stored in SQLite (`rumi_memory.db`) with automatic cleanup and maintenance.

## Architecture

- `rumi.py` - Main bot entry point
- `ai_client.py` - Unified OpenAI-compatible API client
- `context_manager.py` - Relational database system with per-user tables
- `commands/database.py` - Database exploration and management commands
- `commands/summary.py` - Enhanced summary command with context
- `commands/memory.py` - Memory management commands
- `personality.py` - Bot personality configuration

## Contributing

Just make a pull request. Add features, fix bugs, whatever you want.
