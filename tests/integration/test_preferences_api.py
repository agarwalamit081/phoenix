"""Integration tests for preferences API."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.user import User


@pytest.mark.asyncio
class TestPreferencesAPI:
    """Tests for preferences API endpoints."""

    async def test_get_all_preferences(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test getting all user preferences."""
        access_token = create_access_token(str(test_user.id))

        response = test_client.get(
            "/api/v1/preferences/",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "preferences" in data
        assert isinstance(data["preferences"], list)

    async def test_get_preferences_by_category(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test getting preferences filtered by category."""
        access_token = create_access_token(str(test_user.id))

        # First create a preference
        test_client.post(
            "/api/v1/preferences/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "category": "cuisine",
                "value": "Italian food",
                "preference_type": "like",
                "confidence": 0.9,
            },
        )

        # Get by category
        response = test_client.get(
            "/api/v1/preferences/?category=cuisine",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "preferences" in data

    async def test_create_preference_success(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test creating a preference."""
        access_token = create_access_token(str(test_user.id))

        response = test_client.post(
            "/api/v1/preferences/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "category": "cuisine",
                "value": "Japanese food",
                "preference_type": "like",
                "confidence": 0.85,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["category"] == "cuisine"
        assert data["value"] == "Japanese food"

    async def test_create_preference_invalid_type(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test creating preference with invalid type."""
        access_token = create_access_token(str(test_user.id))

        response = test_client.post(
            "/api/v1/preferences/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "category": "cuisine",
                "value": "Italian",
                "preference_type": "invalid_type",
                "confidence": 0.9,
            },
        )

        assert response.status_code == 422  # Validation error

    async def test_create_preference_invalid_confidence(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test creating preference with invalid confidence."""
        access_token = create_access_token(str(test_user.id))

        response = test_client.post(
            "/api/v1/preferences/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "category": "activity",
                "value": "Museums",
                "preference_type": "like",
                "confidence": 1.5,  # Invalid (> 1.0)
            },
        )

        assert response.status_code == 422

    async def test_get_preference_by_id(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test getting a specific preference."""
        access_token = create_access_token(str(test_user.id))

        # Create a preference
        create_response = test_client.post(
            "/api/v1/preferences/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "category": "cuisine",
                "value": "French food",
                "preference_type": "like",
                "confidence": 0.8,
            },
        )
        pref_id = create_response.json()["id"]

        # Get the preference
        response = test_client.get(
            f"/api/v1/preferences/{pref_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == pref_id

    async def test_update_preference(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test updating a preference."""
        access_token = create_access_token(str(test_user.id))

        # Create a preference
        create_response = test_client.post(
            "/api/v1/preferences/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "category": "cuisine",
                "value": "Thai food",
                "preference_type": "like",
                "confidence": 0.7,
            },
        )
        pref_id = create_response.json()["id"]

        # Update the preference
        response = test_client.patch(
            f"/api/v1/preferences/{pref_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"confidence": 0.95},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["confidence"] == 0.95

    async def test_delete_preference(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test deleting a preference."""
        access_token = create_access_token(str(test_user.id))

        # Create a preference
        create_response = test_client.post(
            "/api/v1/preferences/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "category": "activity",
                "value": "Hiking",
                "preference_type": "dislike",
                "confidence": 0.8,
            },
        )
        pref_id = create_response.json()["id"]

        # Delete the preference
        response = test_client.delete(
            f"/api/v1/preferences/{pref_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 204

        # Verify it's deleted
        get_response = test_client.get(
            f"/api/v1/preferences/{pref_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert get_response.status_code == 404

    async def test_extract_preferences_from_text(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test extracting preferences from text."""
        access_token = create_access_token(str(test_user.id))

        response = test_client.post(
            "/api/v1/preferences/extract",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "text": "I love Italian and Japanese food, but I hate crowded places",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "preferences" in data
        assert "count" in data

    async def test_get_profile_summary(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test getting user profile summary."""
        access_token = create_access_token(str(test_user.id))

        # Add some preferences
        test_client.post(
            "/api/v1/preferences/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "category": "cuisine",
                "value": "Italian",
                "preference_type": "like",
                "confidence": 0.9,
            },
        )
        test_client.post(
            "/api/v1/preferences/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "category": "activity",
                "value": "Museums",
                "preference_type": "like",
                "confidence": 0.85,
            },
        )

        # Get summary
        response = test_client.get(
            "/api/v1/preferences/summary/profile",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_preferences" in data
        assert "categories" in data
        assert data["total_preferences"] >= 2

    async def test_get_conflicts(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test getting preference conflicts."""
        access_token = create_access_token(str(test_user.id))

        # Create conflicting preferences
        test_client.post(
            "/api/v1/preferences/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "category": "cuisine",
                "value": "Italian",
                "preference_type": "like",
                "confidence": 0.9,
            },
        )
        test_client.post(
            "/api/v1/preferences/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "category": "cuisine",
                "value": "Italian",
                "preference_type": "dislike",
                "confidence": 0.7,
            },
        )

        # Get conflicts
        response = test_client.get(
            "/api/v1/preferences/summary/conflicts",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "conflicts" in data

    async def test_batch_create_preferences(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test creating multiple preferences at once."""
        access_token = create_access_token(str(test_user.id))

        response = test_client.post(
            "/api/v1/preferences/batch",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "preferences": [
                    {
                        "category": "cuisine",
                        "value": "Italian",
                        "preference_type": "like",
                        "confidence": 0.9,
                    },
                    {
                        "category": "activity",
                        "value": "Museums",
                        "preference_type": "like",
                        "confidence": 0.85,
                    },
                ]
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "created" in data
        assert data["created"] >= 0

    async def test_unauthorized_access(
        self,
        test_client: TestClient,
    ) -> None:
        """Test accessing preferences without authentication."""
        response = test_client.get("/api/v1/preferences/")

        assert response.status_code == 401

    async def test_get_preferences_by_source(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test getting preferences filtered by source."""
        access_token = create_access_token(str(test_user.id))

        response = test_client.get(
            "/api/v1/preferences/?source=explicit",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "preferences" in data
