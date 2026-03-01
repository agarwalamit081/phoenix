"""End-to-end tests for complete user journeys."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User


@pytest.mark.asyncio
@pytest.mark.e2e
class TestUserRegistrationJourney:
    """Tests for complete user registration and onboarding journey."""

    async def test_new_user_registration_and_login(
        self,
        test_client: TestClient,
        test_session: AsyncSession,
    ) -> None:
        """Test complete journey from registration to first chat interaction.

        This test verifies:
        1. User registration
        2. User login
        3. Accessing profile
        4. First preference creation
        5. First chat message
        """
        # Step 1: Register new user
        register_response = test_client.post(
            "/api/v1/auth/register",
            json={
                "email": "journey@example.com",
                "password": "SecurePass123",
                "display_name": "Traveler",
                "preferred_language": "en",
            },
        )
        assert register_response.status_code == 201
        tokens = register_response.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        # Step 2: Verify we can access protected endpoint
        profile_response = test_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert profile_response.status_code == 200
        profile = profile_response.json()
        assert profile["email"] == "journey@example.com"

        # Step 3: Create some travel preferences
        preference_response = test_client.post(
            "/api/v1/preferences/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "category": "cuisine",
                "value": "Italian food",
                "preference_type": "like",
                "confidence": 0.9,
            },
        )
        assert preference_response.status_code == 201
        preference = preference_response.json()
        assert preference["category"] == "cuisine"

        # Step 4: Send first chat message
        chat_response = test_client.post(
            "/api/v1/chat/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "message": "Hi Phoenix! I love Italian food and art museums.",
                "include_preferences": True,
            },
        )
        assert chat_response.status_code == 200
        chat_data = chat_response.json()
        assert chat_data["role"] == "assistant"
        assert chat_data["content"] is not None

        # Step 5: Logout
        logout_response = test_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert logout_response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.e2e
class TestPreferenceCollectionJourney:
    """Tests for preference collection journey."""

    async def test_preference_extraction_from_chat(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test extracting preferences from natural conversation.

        This test verifies:
        1. Sending preferences in chat
        2. Extraction of preferences
        3. Storing preferences
        4. Retrieving preferences
        """
        from src.core.security import create_access_token

        access_token = create_access_token(str(test_user.id))

        # Step 1: Send message with preferences
        response = test_client.post(
            "/api/v1/chat/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "message": "I really love Italian and Japanese food, but I hate crowds. I enjoy art museums.",
                "include_preferences": True,
            },
        )
        assert response.status_code == 200

        # Step 2: Check extracted preferences
        response = test_client.post(
            "/api/v1/preferences/extract",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"text": "I love Italian and Japanese food"},
        )
        assert response.status_code == 200
        extracted = response.json()
        assert "preferences" in extracted
        assert "count" in extracted

        # Step 3: Get all preferences
        response = test_client.get(
            "/api/v1/preferences/",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        preferences = response.json()
        assert "preferences" in preferences

        # Step 4: Get profile summary
        response = test_client.get(
            "/api/v1/preferences/summary/profile",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        summary = response.json()
        assert summary["total_preferences"] >= 0


@pytest.mark.asyncio
@pytest.mark.e2e
class TestTokenRefreshJourney:
    """Tests for token refresh journey."""

    async def test_access_token_expiration_and_refresh(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test journey of access token expiration and refresh.

        This test verifies:
        1. Initial login
        2. Using access token
        3. Refreshing with refresh token
        4. Using new access token
        """
        from src.core.security import create_access_token, create_refresh_token

        # Initial tokens
        access_token = create_access_token(str(test_user.id))
        refresh_token_str = create_refresh_token(str(test_user.id))

        # Use access token
        response = test_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200

        # Refresh tokens
        response = test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token_str},
        )
        assert response.status_code == 200
        new_tokens = response.json()
        new_access_token = new_tokens["access_token"]

        # Use new access token
        response = test_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {new_access_token}"},
        )
        assert response.status_code == 200
