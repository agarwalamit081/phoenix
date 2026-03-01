"""Unit tests for preference service."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.preference import Preference
from src.services.preference_service import PreferenceService
from src.schemas.preference import PreferenceCreateRequest


@pytest.mark.asyncio
class TestPreferenceService:
    """Tests for PreferenceService."""

    async def test_create_preference(self) -> None:
        """Test creating a preference."""
        user_id = uuid.uuid4()
        mock_repo = AsyncMock()
        mock_repo.create.return_value = Preference(
            id=uuid.uuid4(),
            user_id=user_id,
            category="cuisine",
            value="Italian food",
            preference_type="like",
            confidence_score=0.9,
            source="explicit",
            created_at=datetime.now(timezone.utc),
        )

        preference_service = PreferenceService(mock_repo)

        request = PreferenceCreateRequest(
            category="cuisine",
            value="Italian food",
            preference_type="like",
            confidence=0.9,
        )

        result = await preference_service.create_preference(user_id, request)

        assert result.category == "cuisine"
        assert result.value == "Italian food"
        mock_repo.create.assert_called_once()

    async def test_get_user_preferences(self) -> None:
        """Test getting all user preferences."""
        user_id = uuid.uuid4()
        mock_repo = AsyncMock()
        mock_repo.find_by_user.return_value = [
            Preference(
                id=uuid.uuid4(),
                user_id=user_id,
                category="cuisine",
                value="Italian",
                preference_type="like",
                confidence_score=0.9,
                source="explicit",
            ),
            Preference(
                id=uuid.uuid4(),
                user_id=user_id,
                category="activity",
                value="Museums",
                preference_type="like",
                confidence_score=0.85,
                source="inferred",
            ),
        ]

        preference_service = PreferenceService(mock_repo)

        preferences = await preference_service.get_user_preferences(user_id)

        assert len(preferences) == 2
        mock_repo.find_by_user.assert_called_once_with(user_id)

    async def test_get_preferences_by_category(self) -> None:
        """Test getting preferences by category."""
        user_id = uuid.uuid4()
        mock_repo = AsyncMock()
        mock_repo.find_by_category.return_value = [
            Preference(
                id=uuid.uuid4(),
                user_id=user_id,
                category="cuisine",
                value="Italian",
                preference_type="like",
                confidence_score=0.9,
                source="explicit",
            ),
        ]

        preference_service = PreferenceService(mock_repo)

        preferences = await preference_service.get_preferences_by_category(
            user_id, "cuisine"
        )

        assert len(preferences) == 1
        assert preferences[0].category == "cuisine"

    async def test_update_preference(self) -> None:
        """Test updating a preference."""
        user_id = uuid.uuid4()
        pref_id = uuid.uuid4()

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = Preference(
            id=pref_id,
            user_id=user_id,
            category="cuisine",
            value="Italian",
            preference_type="like",
            confidence_score=0.7,
            source="explicit",
        )
        mock_repo.update.return_value = Preference(
            id=pref_id,
            user_id=user_id,
            category="cuisine",
            value="Italian",
            preference_type="like",
            confidence_score=0.95,
            source="explicit",
        )

        preference_service = PreferenceService(mock_repo)

        result = await preference_service.update_preference(
            user_id, pref_id, confidence=0.95
        )

        assert result.confidence_score == 0.95
        mock_repo.update.assert_called_once()

    async def test_delete_preference(self) -> None:
        """Test deleting a preference."""
        user_id = uuid.uuid4()
        pref_id = uuid.uuid4()

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = Preference(
            id=pref_id,
            user_id=user_id,
            category="cuisine",
            value="Italian",
            preference_type="like",
            confidence_score=0.9,
        )
        mock_repo.delete.return_value = None

        preference_service = PreferenceService(mock_repo)

        await preference_service.delete_preference(user_id, pref_id)

        mock_repo.delete.assert_called_once()

    async def test_extract_preferences(self) -> None:
        """Test extracting preferences from text."""
        mock_repo = AsyncMock()
        mock_llm_service = AsyncMock()
        mock_llm_service.extract_entities.return_value = [
            {"text": "Italian food", "type": "CUISINE", "confidence": 0.9},
            {"text": "art museums", "type": "ACTIVITY", "confidence": 0.85},
        ]

        preference_service = PreferenceService(mock_repo, mock_llm_service)

        text = "I love Italian food and visiting art museums"
        preferences = await preference_service.extract_preferences(text)

        assert len(preferences) == 2
        assert preferences[0]["value"] == "Italian food"
        assert preferences[1]["value"] == "art museums"

    async def test_get_profile_summary(self) -> None:
        """Test getting user profile summary."""
        user_id = uuid.uuid4()
        mock_repo = AsyncMock()
        mock_repo.find_by_user.return_value = [
            Preference(
                id=uuid.uuid4(),
                user_id=user_id,
                category="cuisine",
                value="Italian",
                preference_type="like",
                confidence_score=0.9,
                source="explicit",
            ),
            Preference(
                id=uuid.uuid4(),
                user_id=user_id,
                category="cuisine",
                value="Japanese",
                preference_type="like",
                confidence_score=0.85,
                source="explicit",
            ),
            Preference(
                id=uuid.uuid4(),
                user_id=user_id,
                category="activity",
                value="Museums",
                preference_type="like",
                confidence_score=0.95,
                source="inferred",
            ),
        ]

        preference_service = PreferenceService(mock_repo)

        summary = await preference_service.get_profile_summary(user_id)

        assert summary["total_preferences"] == 3
        assert summary["strong_preferences"] == 3
        assert "cuisine" in summary["categories"]
        assert summary["categories"]["cuisine"] == 2

    async def test_detect_conflicts(self) -> None:
        """Test detecting preference conflicts."""
        user_id = uuid.uuid4()
        mock_repo = AsyncMock()
        mock_repo.find_by_user.return_value = [
            Preference(
                id=uuid.uuid4(),
                user_id=user_id,
                category="cuisine",
                value="Italian",
                preference_type="like",
                confidence_score=0.9,
            ),
            Preference(
                id=uuid.uuid4(),
                user_id=user_id,
                category="cuisine",
                value="Italian",
                preference_type="dislike",
                confidence_score=0.7,
            ),
        ]

        preference_service = PreferenceService(mock_repo)

        conflicts = await preference_service.detect_conflicts(user_id)

        assert len(conflicts) > 0
        assert conflicts[0]["category"] == "cuisine"

    async def test_merge_preferences(self) -> None:
        """Test merging similar preferences."""
        user_id = uuid.uuid4()
        pref_id = uuid.uuid4()

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = Preference(
            id=pref_id,
            user_id=user_id,
            category="cuisine",
            value="Italian",
            preference_type="like",
            confidence_score=0.7,
        )
        mock_repo.update.return_value = Preference(
            id=pref_id,
            user_id=user_id,
            category="cuisine",
            value="Italian",
            preference_type="like",
            confidence_score=0.85,
        )
        mock_repo.delete.return_value = None

        preference_service = PreferenceService(mock_repo)

        new_pref = Preference(
            id=uuid.uuid4(),
            user_id=user_id,
            category="cuisine",
            value="Italian food",
            preference_type="like",
            confidence_score=0.8,
        )

        result = await preference_service.merge_preferences(new_pref, pref_id)

        assert result.confidence_score > 0.7

    async def test_decay_old_preferences(self) -> None:
        """Test decaying old preference confidence."""
        user_id = uuid.uuid4()
        old_date = datetime.now(timezone.utc) - timedelta(days=100)

        mock_repo = AsyncMock()
        mock_repo.find_by_user.return_value = [
            Preference(
                id=uuid.uuid4(),
                user_id=user_id,
                category="cuisine",
                value="Italian",
                preference_type="like",
                confidence_score=0.9,
                created_at=old_date,
            ),
        ]
        mock_repo.update.return_value = None

        preference_service = PreferenceService(mock_repo)

        await preference_service.decay_old_preferences(user_id, days=90)

        mock_repo.update.assert_called()
