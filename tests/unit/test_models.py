"""Unit tests for SQLAlchemy models."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.user import User
from src.models.preference import UserPreference as Preference
from src.models.poi import PointOfInterest as POI
from src.models.itinerary import Itinerary, ItineraryItem


class TestUserModel:
    """Tests for User model."""

    def test_create_user(self) -> None:
        """Test creating a user."""
        user = User(
            email="test@example.com",
            password_hash="hashed_password",
            display_name="Test User",
            preferred_language="en",
            is_active=True,
            is_verified=False,
        )
        assert user.email == "test@example.com"
        assert user.display_name == "Test User"
        assert user.is_active is True
        assert user.is_verified is False

    def test_user_repr(self) -> None:
        """Test user string representation."""
        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            password_hash="hashed",
            display_name="Test User",
        )
        repr_str = repr(user)
        assert "test@example.com" in repr_str

    def test_user_oauth_fields(self) -> None:
        """Test user OAuth fields."""
        user = User(
            email="oauth@example.com",
            password_hash="",
            display_name="OAuth User",
            google_id="google-12345",
        )
        assert user.google_id == "google-12345"
        assert user.apple_id is None


class TestPreferenceModel:
    """Tests for Preference model."""

    def test_create_preference(self) -> None:
        """Test creating a preference."""
        user_id = uuid.uuid4()
        preference = Preference(
            user_id=user_id,
            category="cuisine",
            value="Italian food",
            preference_type="like",
            confidence_score=0.9,
            source="explicit",
        )
        assert preference.category == "cuisine"
        assert preference.preference_type == "like"
        assert preference.confidence_score == 0.9
        assert preference.source == "explicit"

    def test_preference_enum_validation(self) -> None:
        """Test preference type enum validation."""
        user_id = uuid.uuid4()

        # Valid types
        for pref_type in ["like", "dislike", "neutral"]:
            preference = Preference(
                user_id=user_id,
                category="test",
                value="test value",
                preference_type=pref_type,
            )
            assert preference.preference_type == pref_type

    def test_preference_source_enum(self) -> None:
        """Test preference source enum."""
        user_id = uuid.uuid4()

        # Valid sources
        for source in ["explicit", "inferred", "observed"]:
            preference = Preference(
                user_id=user_id,
                category="test",
                value="test value",
                preference_type="like",
                source=source,
            )
            assert preference.source == source

    def test_preference_expiration(self) -> None:
        """Test preference expiration."""
        user_id = uuid.uuid4()
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        preference = Preference(
            user_id=user_id,
            category="test",
            value="test value",
            preference_type="like",
            expires_at=expires_at,
        )
        assert preference.expires_at == expires_at

    def test_preference_repr(self) -> None:
        """Test preference string representation."""
        user_id = uuid.uuid4()
        preference = Preference(
            id=uuid.uuid4(),
            user_id=user_id,
            category="cuisine",
            value="Italian",
            preference_type="like",
        )
        repr_str = repr(preference)
        assert "cuisine" in repr_str


class TestPOIModel:
    """Tests for POI model."""

    def test_create_poi(self) -> None:
        """Test creating a POI."""
        poi = POI(
            name="Eiffel Tower",
            description="Famous landmark in Paris",
            latitude=48.8584,
            longitude=2.2945,
            city="Paris",
            country="France",
            categories=["landmark", "attraction"],
            rating=4.5,
            price_level=2,
        )
        assert poi.name == "Eiffel Tower"
        assert poi.latitude == 48.8584
        assert poi.longitude == 2.2945
        assert "landmark" in poi.categories
        assert poi.rating == 4.5
        assert poi.price_level == 2

    def test_poi_with_embeddings(self) -> None:
        """Test POI with embedding vector."""
        embedding = [0.1] * 1536
        poi = POI(
            name="Test POI",
            latitude=48.8566,
            longitude=2.3522,
            city="Paris",
            country="France",
            categories=["museum"],
            embedding=embedding,
        )
        assert poi.embedding == embedding

    def test_poi_contact_info(self) -> None:
        """Test POI with contact information."""
        poi = POI(
            name="Test Restaurant",
            latitude=48.8566,
            longitude=2.3522,
            city="Paris",
            country="France",
            categories=["restaurant"],
            website="https://example.com",
            phone="+33123456789",
            email="contact@example.com",
        )
        assert poi.website == "https://example.com"
        assert poi.phone == "+33123456789"
        assert poi.email == "contact@example.com"

    def test_poi_availability(self) -> None:
        """Test POI with opening hours."""
        poi = POI(
            name="Test Museum",
            latitude=48.8566,
            longitude=2.3522,
            city="Paris",
            country="France",
            categories=["museum"],
            opening_hours={
                "monday": [{"open": "09:00", "close": "18:00"}],
                "tuesday": [{"open": "09:00", "close": "18:00"}],
            },
        )
        assert "monday" in poi.opening_hours

    def test_poi_repr(self) -> None:
        """Test POI string representation."""
        poi = POI(
            id=uuid.uuid4(),
            name="Eiffel Tower",
            latitude=48.8584,
            longitude=2.2945,
            city="Paris",
            country="France",
            categories=["landmark"],
        )
        repr_str = repr(poi)
        assert "Eiffel Tower" in repr_str


class TestItineraryModel:
    """Tests for Itinerary and ItineraryItem models."""

    def test_create_itinerary(self) -> None:
        """Test creating an itinerary."""
        user_id = uuid.uuid4()
        itinerary = Itinerary(
            user_id=user_id,
            title="Paris Adventure",
            description="A wonderful trip to Paris",
            start_location="Paris",
            end_location="Paris",
            status="draft",
        )
        assert itinerary.title == "Paris Adventure"
        assert itinerary.start_location == "Paris"
        assert itinerary.status == "draft"

    def test_itinerary_status_enum(self) -> None:
        """Test itinerary status enum."""
        user_id = uuid.uuid4()
        for status in ["draft", "active", "completed", "cancelled"]:
            itinerary = Itinerary(
                user_id=user_id,
                title="Test",
                start_location="Paris",
                end_location="Paris",
                status=status,
            )
            assert itinerary.status == status

    def test_itinerary_with_route(self) -> None:
        """Test itinerary with route data."""
        user_id = uuid.uuid4()
        itinerary = Itinerary(
            user_id=user_id,
            title="Test Route",
            start_location="Paris",
            end_location="Paris",
            total_distance_km=5.2,
            total_duration_minutes=240,
        )
        assert itinerary.total_distance_km == 5.2

    def test_create_itinerary_item(self) -> None:
        """Test creating an itinerary item."""
        itinerary_id = uuid.uuid4()
        poi_id = uuid.uuid4()
        item = ItineraryItem(
            itinerary_id=itinerary_id,
            poi_id=poi_id,
            sequence_order=1,
            estimated_arrival_time=datetime.now(timezone.utc),
            estimated_duration_minutes=60,
            notes="Must visit!",
        )
        assert item.sequence_order == 1
        assert item.notes == "Must visit!"

    def test_itinerary_item_status(self) -> None:
        """Test itinerary item status."""
        itinerary_id = uuid.uuid4()
        poi_id = uuid.uuid4()
        for status in ["pending", "in_progress", "completed", "skipped"]:
            item = ItineraryItem(
                itinerary_id=itinerary_id,
                poi_id=poi_id,
                sequence_order=1,
                status=status,
            )
            assert item.status == status

    def test_itinerary_repr(self) -> None:
        """Test itinerary string representation."""
        user_id = uuid.uuid4()
        itinerary = Itinerary(
            id=uuid.uuid4(),
            user_id=user_id,
            title="Paris Adventure",
            start_location="Paris",
            end_location="Paris",
        )
        repr_str = repr(itinerary)
        assert "Paris Adventure" in repr_str

    def test_itinerary_item_repr(self) -> None:
        """Test itinerary item string representation."""
        itinerary_id = uuid.uuid4()
        item = ItineraryItem(
            id=uuid.uuid4(),
            itinerary_id=itinerary_id,
            poi_id=uuid.uuid4(),
            sequence_order=1,
        )
        repr_str = repr(item)
        assert "1" in repr_str
