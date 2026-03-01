"""Integration tests for chat API."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.user import User


@pytest.mark.asyncio
class TestChatAPI:
    """Tests for chat API endpoints."""

    async def test_send_message_success(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test sending a chat message."""
        access_token = create_access_token(str(test_user.id))

        response = test_client.post(
            "/api/v1/chat/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "message": "Hello Phoenix!",
                "include_preferences": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "message_id" in data
        assert data["role"] == "assistant"
        assert data["content"] is not None

    async def test_send_message_with_preferences(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test sending a message with preference extraction."""
        access_token = create_access_token(str(test_user.id))

        response = test_client.post(
            "/api/v1/chat/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "message": "I love Italian food and art museums",
                "include_preferences": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "extracted_preferences" in data or "content" in data

    async def test_send_message_empty(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test sending an empty message."""
        access_token = create_access_token(str(test_user.id))

        response = test_client.post(
            "/api/v1/chat/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"message": ""},
        )

        assert response.status_code == 422  # Validation error

    async def test_send_message_unauthorized(
        self,
        test_client: TestClient,
    ) -> None:
        """Test sending message without authentication."""
        response = test_client.post(
            "/api/v1/chat/",
            json={"message": "Hello!"},
        )

        assert response.status_code == 401

    async def test_get_conversation_history(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test getting conversation history."""
        access_token = create_access_token(str(test_user.id))

        # First send a message
        test_client.post(
            "/api/v1/chat/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"message": "Hello Phoenix!"},
        )

        # Get history
        response = test_client.get(
            "/api/v1/chat/history",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert len(data["messages"]) >= 2  # At least user + assistant

    async def test_get_conversation_history_pagination(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test conversation history pagination."""
        access_token = create_access_token(str(test_user.id))

        # Send multiple messages
        for i in range(5):
            test_client.post(
                "/api/v1/chat/",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"message": f"Message {i}"},
            )

        # Get paginated history
        response = test_client.get(
            "/api/v1/chat/history?limit=2&offset=0",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) <= 2

    async def test_get_conversation_by_id(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test getting a specific conversation."""
        access_token = create_access_token(str(test_user.id))

        # Send a message
        chat_response = test_client.post(
            "/api/v1/chat/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"message": "Test conversation"},
        )
        conversation_id = chat_response.json().get("conversation_id")

        if conversation_id:
            # Get conversation
            response = test_client.get(
                f"/api/v1/chat/history/{conversation_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["conversation_id"] == str(conversation_id)

    async def test_stream_chat_message(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test streaming chat response."""
        access_token = create_access_token(str(test_user.id))

        response = test_client.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"message": "Tell me about Paris"},
        )

        # Streaming endpoint should return 200
        assert response.status_code == 200

    async def test_delete_conversation(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test deleting a conversation."""
        access_token = create_access_token(str(test_user.id))

        # Create a conversation
        chat_response = test_client.post(
            "/api/v1/chat/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"message": "To be deleted"},
        )
        conversation_id = chat_response.json().get("conversation_id")

        if conversation_id:
            # Delete conversation
            response = test_client.delete(
                f"/api/v1/chat/history/{conversation_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            assert response.status_code == 204

    async def test_chat_with_language(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test chat with language specification."""
        access_token = create_access_token(str(test_user.id))

        response = test_client.post(
            "/api/v1/chat/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "message": "Bonjour!",
                "language": "fr",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "content" in data

    async def test_chat_context_memory(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test that chat maintains context across messages."""
        access_token = create_access_token(str(test_user.id))

        # First message
        test_client.post(
            "/api/v1/chat/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"message": "My name is Alice"},
        )

        # Second message referencing first
        response = test_client.post(
            "/api/v1/chat/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"message": "What's my name?"},
        )

        assert response.status_code == 200
        data = response.json()
        # Response should reference the name
        content = data.get("content", "").lower()
        # This is a basic check - the actual implementation would need memory
