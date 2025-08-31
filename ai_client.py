#!/usr/bin/env python3
import os
import asyncio
from typing import List, Dict, Optional
from openai import AsyncOpenAI
import json

class AIClient:
    """Unified AI client supporting OpenAI API and compatible providers"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL")  # For OpenAI-compatible APIs
        self.model = os.getenv("AI_MODEL", "gpt-4o-mini")  # Default to GPT-4o-mini
        
        if not self.api_key:
            raise ValueError("Missing OPENAI_API_KEY or GROQ_API_KEY in environment")
        
        # Initialize client
        if self.base_url:
            # Custom endpoint (e.g., local LLM, other providers)
            self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            # Standard OpenAI
            self.client = AsyncOpenAI(api_key=self.api_key)
    
    async def get_completion(self, 
                           messages: List[Dict[str, str]], 
                           temperature: float = 0.7,
                           max_tokens: Optional[int] = None,
                           stream: bool = False) -> str:
        """Get completion from AI model"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )
            
            if stream:
                # Handle streaming response
                content = ""
                async for chunk in response:
                    if chunk.choices[0].delta.content:
                        content += chunk.choices[0].delta.content
                return content
            else:
                return response.choices[0].message.content
                
        except Exception as e:
            print(f"AI API Error: {e}")
            return f"Error generating response: {str(e)}"
    
    async def summarize_conversation(self, 
                                   messages: List[str], 
                                   context: str,
                                   personality: str,
                                   previous_context: str = None) -> str:
        """Generate conversation summary with context awareness"""
        
        # Join messages
        chat_log = "\n".join(messages)
        
        # Build context-aware prompt
        system_prompt = f"""{personality}

You are analyzing Discord conversations with full context awareness. You maintain continuity across conversations and remember patterns, personalities, and ongoing discussions.

CONTEXT INTEGRATION:
- Use previous conversation context to maintain continuity
- Reference ongoing topics and unresolved questions
- Note how current discussion relates to past conversations
- Identify evolving themes and relationship dynamics

ADAPTIVE ANALYSIS:
- Match response depth to actual content richness
- Technical discussions → detailed analysis
- Casual chat → lighter summary
- Mixed content → balanced approach
- Empty periods → brief, witty acknowledgment

STRUCTURE (adapt based on content):
• **Continuity** (how this connects to previous conversations)
• **The Vibe** (energy and atmosphere)
• **Core Themes** (main topics and ideas)
• **Key Developments** (important moments or decisions)
• **Interpersonal Dynamics** (relationships, tensions, alliances)
• **Intellectual Highlights** (clever insights, technical depth)
• **Comedy & Culture** (humor, inside jokes, memes)
• **Unresolved Threads** (ongoing questions, topics to revisit)
• **Notable Quotes** (memorable or significant statements)"""

        user_prompt = f"""PREVIOUS CONTEXT:
{previous_context if previous_context else "No previous context available."}

CURRENT CONVERSATION ({context}):
{chat_log}

Analyze this conversation with full awareness of the ongoing context and relationships."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return await self.get_completion(messages, temperature=0.8)
    
    async def analyze_user_personality(self, 
                                     user_messages: List[str], 
                                     username: str) -> Dict[str, any]:
        """Analyze user personality and communication patterns"""
        
        if not user_messages:
            return {"personality_notes": "No messages to analyze", "common_topics": [], "interaction_style": "Unknown"}
        
        messages_text = "\n".join(user_messages[-50:])  # Last 50 messages
        
        system_prompt = """Analyze this user's communication patterns and personality. Return a JSON object with:
- personality_notes: 2-3 sentences describing their style, interests, and behavior
- common_topics: Array of their frequent discussion topics
- interaction_style: Brief description of how they communicate (formal/casual/humorous/technical/etc.)

Be observant but not intrusive. Focus on communication patterns, not personal details."""

        user_prompt = f"User: {username}\nRecent messages:\n{messages_text}"
        
        response = await self.get_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], temperature=0.3)
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return {
                "personality_notes": response,
                "common_topics": [],
                "interaction_style": "Analysis available in notes"
            }
    
    async def generate_contextual_response(self, 
                                         current_message: str,
                                         user_context: Dict,
                                         conversation_context: str,
                                         personality: str) -> str:
        """Generate a contextual response to a direct message/mention"""
        
        system_prompt = f"""{personality}

You have context about this user and the ongoing conversation. Respond naturally and appropriately, showing awareness of:
- The user's communication style and personality
- Recent conversation topics and themes
- Your established relationships and inside jokes
- The current discussion context

Keep responses concise unless the situation calls for elaboration."""

        context_info = ""
        if user_context:
            context_info = f"""
USER CONTEXT:
- Style: {user_context.get('interaction_style', 'Unknown')}
- Common topics: {', '.join(user_context.get('common_topics', []))}
- Notes: {user_context.get('personality_notes', 'No specific notes')}
"""

        user_prompt = f"""{context_info}

RECENT CONVERSATION CONTEXT:
{conversation_context}

CURRENT MESSAGE: {current_message}

Respond as Rumi, showing contextual awareness and continuity."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return await self.get_completion(messages, temperature=0.9)