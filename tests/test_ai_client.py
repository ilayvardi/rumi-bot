#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from ai_client import AIClient

@pytest.fixture
def mock_env(monkeypatch):
    """Mock environment variables"""
    monkeypatch.setenv('OPENAI_API_KEY', 'test_key')
    monkeypatch.setenv('AI_MODEL', 'gpt-4o-mini')

def test_client_initialization_openai(mock_env):
    """Test AIClient initializes with OpenAI configuration"""
    client = AIClient()
    assert client.api_key == 'test_key'
    assert client.model == 'gpt-4o-mini'
    assert client.base_url is None

def test_client_initialization_groq(monkeypatch):
    """Test AIClient initializes with Groq configuration"""
    monkeypatch.setenv('GROQ_API_KEY', 'groq_test_key')
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://api.groq.com/openai/v1')
    monkeypatch.setenv('AI_MODEL', 'meta-llama/llama-4-maverick-17b-128e-instruct')
    
    client = AIClient()
    assert client.api_key == 'groq_test_key'
    assert client.base_url == 'https://api.groq.com/openai/v1'
    assert client.model == 'meta-llama/llama-4-maverick-17b-128e-instruct'

def test_client_initialization_missing_key(monkeypatch):
    """Test AIClient raises error when API key is missing"""
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    
    with pytest.raises(ValueError, match="Missing OPENAI_API_KEY or GROQ_API_KEY"):
        AIClient()

@pytest.mark.asyncio
async def test_get_completion(mock_env):
    """Test get_completion method"""
    client = AIClient()
    
    # Mock the OpenAI client
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Test response"))]
    
    with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        
        messages = [{"role": "user", "content": "Hello"}]
        result = await client.get_completion(messages)
        
        assert result == "Test response"
        mock_create.assert_called_once_with(
            model='gpt-4o-mini',
            messages=messages,
            temperature=0.7,
            max_tokens=None,
            stream=False
        )

@pytest.mark.asyncio
async def test_get_completion_error_handling(mock_env):
    """Test error handling in get_completion"""
    client = AIClient()
    
    with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = Exception("API Error")
        
        messages = [{"role": "user", "content": "Hello"}]
        result = await client.get_completion(messages)
        
        assert "Error generating response" in result
        assert "API Error" in result

@pytest.mark.asyncio
async def test_summarize_conversation(mock_env):
    """Test summarize_conversation method"""
    client = AIClient()
    
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Summary of conversation"))]
    
    with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        
        messages = ["User1: Hello", "User2: Hi there"]
        context = "last 2 messages"
        personality = "Analytical bot"
        previous_context = "Previous discussion about Python"
        
        result = await client.summarize_conversation(
            messages, context, personality, previous_context
        )
        
        assert result == "Summary of conversation"
        
        # Verify the prompt includes context awareness elements
        call_args = mock_create.call_args
        sent_messages = call_args.kwargs['messages']
        
        assert len(sent_messages) == 2
        assert 'CONTEXT INTEGRATION' in sent_messages[0]['content']
        assert 'Previous discussion about Python' in sent_messages[1]['content']

@pytest.mark.asyncio
async def test_analyze_user_personality(mock_env):
    """Test analyze_user_personality method"""
    client = AIClient()
    
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="User is technical and friendly"))]
    
    with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        
        messages = ["User1: Let's discuss Python", "User1: I love coding"]
        
        result = await client.analyze_user_personality(messages)
        
        assert result == "User is technical and friendly"
        
        # Verify the prompt is for personality analysis
        call_args = mock_create.call_args
        sent_messages = call_args.kwargs['messages']
        
        assert 'personality' in sent_messages[0]['content'].lower()
        assert 'communication style' in sent_messages[0]['content'].lower()

if __name__ == '__main__':
    pytest.main([__file__, '-v'])