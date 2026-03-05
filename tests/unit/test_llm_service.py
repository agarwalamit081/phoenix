"""Unit tests for LLM service."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.llm_service import LLMService, Message, ChatCompletionResponse


@pytest.mark.asyncio
class TestLLMService:
    """Tests for LLMService."""

    async def test_chat_completion(self) -> None:
        """Test basic chat completion."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello! How can I help you today?"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30

        mock_client.chat.completions.create.return_value = mock_response

        llm_service = LLMService(mock_client)

        messages = [
            Message(role="user", content="Hello!")
        ]
        response = await llm_service.chat_completion(messages)

        assert response["content"] == "Hello! How can I help you today?"
        assert response["model"] == "gpt-4o-mini"
        assert response["usage"]["total_tokens"] == 30

    async def test_chat_completion_with_system_message(self) -> None:
        """Test chat completion with system message."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "I am Phoenix, your travel companion."
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 25

        mock_client.chat.completions.create.return_value = mock_response

        llm_service = LLMService(mock_client)

        messages = [
            Message(role="system", content="You are Phoenix, a travel companion."),
            Message(role="user", content="Who are you?"),
        ]
        response = await llm_service.chat_completion(messages)

        assert "Phoenix" in response["content"]

    async def test_chat_completion_with_history(self) -> None:
        """Test chat completion with conversation history."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "I can help you plan a trip to Paris!"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 50

        mock_client.chat.completions.create.return_value = mock_response

        llm_service = LLMService(mock_client)

        messages = [
            Message(role="user", content="I want to visit Paris"),
            Message(role="assistant", content="Paris is wonderful! What interests you?"),
            Message(role="user", content="I love art museums"),
        ]
        response = await llm_service.chat_completion(messages)

        assert response["content"] is not None

    async def test_chat_completion_with_temperature(self) -> None:
        """Test chat completion with custom temperature."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Creative response!"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 20

        mock_client.chat.completions.create.return_value = mock_response

        llm_service = LLMService(mock_client)

        messages = [Message(role="user", content="Tell me a story")]
        response = await llm_service.chat_completion(messages, temperature=0.9)

        assert response["content"] == "Creative response!"

    async def test_generate_json_response(self) -> None:
        """Test generating JSON response."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"preference": "Italian food", "confidence": 0.9}'
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 30

        mock_client.chat.completions.create.return_value = mock_response

        llm_service = LLMService(mock_client)

        prompt = "Extract the preference from: I love Italian food"
        response = await llm_service.generate_json(prompt)

        assert response["preference"] == "Italian food"
        assert response["confidence"] == 0.9

    async def test_generate_json_with_schema(self) -> None:
        """Test generating JSON with schema."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"name": "Eiffel Tower", "category": "landmark"}'
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 40

        mock_client.chat.completions.create.return_value = mock_response

        llm_service = LLMService(mock_client)

        prompt = "Extract POI info"
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "category": {"type": "string"}
            }
        }
        response = await llm_service.generate_json(prompt, schema=schema)

        assert response["name"] == "Eiffel Tower"

    async def test_extract_entities(self) -> None:
        """Test entity extraction."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '''[
            {"text": "Paris", "type": "LOCATION", "confidence": 0.95},
            {"text": "Louvre Museum", "type": "POI", "confidence": 0.98}
        ]'''
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 50

        mock_client.chat.completions.create.return_value = mock_response

        llm_service = LLMService(mock_client)

        text = "I want to visit the Louvre Museum in Paris"
        entities = await llm_service.extract_entities(text)

        assert len(entities) == 2
        assert entities[0]["text"] == "Paris"
        assert entities[0]["type"] == "LOCATION"
        assert entities[1]["text"] == "Louvre Museum"

    async def test_classify_intent(self) -> None:
        """Test intent classification."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '''{
            "intent": "travel_planning",
            "confidence": 0.92,
            "reasoning": "User is asking about planning a trip"
        }'''
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 35

        mock_client.chat.completions.create.return_value = mock_response

        llm_service = LLMService(mock_client)

        text = "Help me plan a trip to Japan"
        result = await llm_service.classify_intent(text)

        assert result["intent"] == "travel_planning"
        assert result["confidence"] == 0.92

    async def test_summarize_conversation(self) -> None:
        """Test conversation summarization."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "User is interested in visiting Paris, specifically art museums and Italian restaurants."
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 100

        mock_client.chat.completions.create.return_value = mock_response

        llm_service = LLMService(mock_client)

        messages = [
            Message(role="user", content="I want to visit Paris"),
            Message(role="assistant", content="What interests you?"),
            Message(role="user", content="Art museums and Italian food"),
        ]
        summary = await llm_service.summarize_conversation(messages)

        assert "Paris" in summary
        assert "art museums" in summary

    async def test_generate_embedding(self) -> None:
        """Test embedding generation."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3] * 512)]
        mock_response.model = "text-embedding-3-small"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 5

        mock_client.embeddings.create.return_value = mock_response

        llm_service = LLMService(mock_client)

        text = "Italian food is delicious"
        embedding = await llm_service.generate_embedding(text)

        assert len(embedding) == 1536
        assert embedding[0] == 0.1

    async def test_generate_embeddings_batch(self) -> None:
        """Test batch embedding generation."""
        mock_client = AsyncMock()

        def create_embedding(text):
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = len(text.split())
            return mock_response

        mock_client.embeddings.create.side_effect = [
            create_embedding("First text"),
            create_embedding("Second text"),
            create_embedding("Third text"),
        ]

        llm_service = LLMService(mock_client)

        texts = ["First text", "Second text", "Third text"]
        embeddings = await llm_service.generate_embeddings(texts)

        assert len(embeddings) == 3
        assert all(len(emb) == 1536 for emb in embeddings)

    async def test_function_calling(self) -> None:
        """Test function calling."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [
            MagicMock(
                function=MagicMock(
                    name="search_pois",
                    arguments='{"query": "museums in Paris", "category": "museum"}'
                )
            )
        ]
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 45

        mock_client.chat.completions.create.return_value = mock_response

        llm_service = LLMService(mock_client)

        messages = [Message(role="user", content="Find museums in Paris")]
        functions = [
            {
                "name": "search_pois",
                "description": "Search for points of interest",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "category": {"type": "string"}
                    }
                }
            }
        ]

        response = await llm_service.chat_completion(messages, functions=functions)

        assert "tool_calls" in response
        assert response["tool_calls"][0]["name"] == "search_pois"

    async def test_stream_chat(self) -> None:
        """Test streaming chat completion."""
        mock_client = AsyncMock()

        async def mock_stream():
            chunks = ["Hello", " there", "!"]
            for chunk in chunks:
                mock_chunk = MagicMock()
                mock_chunk.choices = [MagicMock()]
                mock_chunk.choices[0].delta.content = chunk
                mock_chunk.choices[0].finish_reason = None
                yield mock_chunk

            # Final chunk
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock()]
            mock_chunk.choices[0].delta.content = None
            mock_chunk.choices[0].finish_reason = "stop"
            yield mock_chunk

        mock_client.chat.completions.create.return_value = mock_stream()

        llm_service = LLMService(mock_client)

        messages = [Message(role="user", content="Say hello")]
        chunks = []

        async for chunk in llm_service.stream_chat(messages):
            chunks.append(chunk)

        assert "".join(chunks) == "Hello there!"

    async def test_rate_limiting_retry(self) -> None:
        """Test retry on rate limit."""
        mock_client = AsyncMock()

        # First call: rate limit error
        # Second call: success
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Success after retry"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 20

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                from openai import RateLimitError
                raise RateLimitError("Rate limit exceeded", response=MagicMock(), body=None)
            return mock_response

        mock_client.chat.completions.create.side_effect = side_effect

        llm_service = LLMService(mock_client, max_retries=2)

        messages = [Message(role="user", content="Test")]
        response = await llm_service.chat_completion(messages)

        assert response["content"] == "Success after retry"
        assert call_count == 2
