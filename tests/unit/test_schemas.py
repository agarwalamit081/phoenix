"""Unit tests for Pydantic schemas."""

import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.schemas.user import (
    TokenResponse,
    UserRegisterRequest,
    UserProfileResponse,
)
from src.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ConversationHistory,
)
from src.schemas.preference import (
    PreferenceCreateRequest,
    PreferenceResponse,
    UserProfileSummary,
)
from src.schemas.route import (
    Location,
    POIBrief,
    RouteGenerateRequest,
    RouteResponse,
    RouteStop,
)
from src.schemas.tour import (
    TourStartRequest,
    TourStatus,
    TourStopContent,
)


class TestUserSchemas:
    """Tests for user-related schemas."""

    def test_user_register_request_valid(self) -> None:
        """Test valid user registration request."""
        data = {
            "email": "test@example.com",
            "password": "Password123",
            "display_name": "Test User",
            "preferred_language": "en",
        }
        schema = UserRegisterRequest(**data)
        assert schema.email == "test@example.com"
        assert schema.password == "Password123"
        assert schema.display_name == "Test User"

    def test_user_register_request_invalid_password(self) -> None:
        """Test user registration with invalid password."""
        data = {
            "email": "test@example.com",
            "password": "weak",  # Missing uppercase, digit
            "display_name": "Test User",
        }
        with pytest.raises(ValidationError):
            UserRegisterRequest(**data)

    def test_user_register_request_invalid_email(self) -> None:
        """Test user registration with invalid email."""
        data = {
            "email": "not-an-email",
            "password": "Password123",
            "display_name": "Test User",
        }
        with pytest.raises(ValidationError):
            UserRegisterRequest(**data)

    def test_token_response(self) -> None:
        """Test token response schema."""
        data = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "token_type": "bearer",
            "expires_in": 900,
        }
        schema = TokenResponse(**data)
        assert schema.access_token == "test-access-token"
        assert schema.expires_in == 900

    def test_user_profile_response(self) -> None:
        """Test user profile response schema."""
        data = {
            "id": uuid.uuid4(),
            "email": "test@example.com",
            "display_name": "Test User",
            "preferred_language": "en",
            "timezone": "UTC",
            "bio": None,
            "avatar_url": None,
            "home_city": None,
            "home_country": None,
            "is_verified": True,
            "created_at": datetime.now(),
        }
        schema = UserProfileResponse(**data)
        assert schema.email == "test@example.com"
        assert schema.is_verified is True


class TestChatSchemas:
    """Tests for chat-related schemas."""

    def test_chat_message(self) -> None:
        """Test chat message schema."""
        data = {
            "role": "user",
            "content": "Hello, Phoenix!",
            "timestamp": datetime.now(),
        }
        schema = ChatMessage(**data)
        assert schema.role == "user"
        assert schema.content == "Hello, Phoenix!"

    def test_chat_message_invalid_role(self) -> None:
        """Test chat message with invalid role."""
        data = {
            "role": "invalid",
            "content": "Test",
        }
        with pytest.raises(ValidationError):
            ChatMessage(**data)

    def test_chat_request(self) -> None:
        """Test chat request schema."""
        data = {
            "message": "Tell me about Paris",
            "conversation_id": uuid.uuid4(),
            "language": "en",
            "include_preferences": True,
        }
        schema = ChatRequest(**data)
        assert schema.message == "Tell me about Paris"
        assert schema.include_preferences is True

    def test_chat_request_empty_message(self) -> None:
        """Test chat request with empty message."""
        data = {
            "message": "",
        }
        with pytest.raises(ValidationError):
            ChatRequest(**data)

    def test_chat_response(self) -> None:
        """Test chat response schema."""
        message_id = uuid.uuid4()
        data = {
            "message_id": message_id,
            "role": "assistant",
            "content": "Paris is a beautiful city!",
            "timestamp": datetime.now(),
        }
        schema = ChatResponse(**data)
        assert schema.content == "Paris is a beautiful city!"

    def test_conversation_history(self) -> None:
        """Test conversation history schema."""
        conv_id = uuid.uuid4()
        messages = [
            ChatMessage(role="user", content="Hello", timestamp=datetime.now()),
            ChatMessage(role="assistant", content="Hi!", timestamp=datetime.now()),
        ]
        data = {
            "conversation_id": conv_id,
            "messages": messages,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        schema = ConversationHistory(**data)
        assert len(schema.messages) == 2


class TestPreferenceSchemas:
    """Tests for preference-related schemas."""

    def test_preference_create_request(self) -> None:
        """Test preference creation request."""
        data = {
            "category": "cuisine",
            "value": "Italian food",
            "preference_type": "like",
            "confidence": 0.9,
            "context": "I love pasta and pizza",
        }
        schema = PreferenceCreateRequest(**data)
        assert schema.category == "cuisine"
        assert schema.preference_type == "like"
        assert schema.confidence == 0.9

    def test_preference_create_request_invalid_type(self) -> None:
        """Test preference with invalid type."""
        data = {
            "category": "cuisine",
            "value": "Italian food",
            "preference_type": "invalid",  # Must be like/dislike/neutral
        }
        with pytest.raises(ValidationError):
            PreferenceCreateRequest(**data)

    def test_preference_create_request_invalid_confidence(self) -> None:
        """Test preference with invalid confidence."""
        data = {
            "category": "cuisine",
            "value": "Italian food",
            "preference_type": "like",
            "confidence": 1.5,  # Must be 0-1
        }
        with pytest.raises(ValidationError):
            PreferenceCreateRequest(**data)

    def test_preference_response(self) -> None:
        """Test preference response schema."""
        data = {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "preference_type": "like",
            "category": "cuisine",
            "value": "Italian food",
            "confidence_score": 0.9,
            "source": "explicit",
            "expires_at": None,
            "context": "Test context",
            "created_at": datetime.now(),
        }
        schema = PreferenceResponse(**data)
        assert schema.category == "cuisine"
        assert schema.source == "explicit"

    def test_user_profile_summary(self) -> None:
        """Test user profile summary schema."""
        data = {
            "total_preferences": 10,
            "strong_preferences": 7,
            "categories": {"cuisine": 3, "activity": 2},
            "top_interests": [
                {"category": "cuisine", "value": "Italian", "confidence": 0.9}
            ],
            "dislikes": ["crowds", "tourist traps"],
            "unresolved_conflicts": 1,
        }
        schema = UserProfileSummary(**data)
        assert schema.total_preferences == 10
        assert len(schema.top_interests) == 1


class TestRouteSchemas:
    """Tests for route-related schemas."""

    def test_location(self) -> None:
        """Test location schema."""
        data = {
            "latitude": Decimal("48.8566"),
            "longitude": Decimal("2.3522"),
            "address": "Paris, France",
            "city": "Paris",
            "country": "France",
        }
        schema = Location(**data)
        assert schema.city == "Paris"
        assert schema.latitude == Decimal("48.8566")

    def test_location_invalid_latitude(self) -> None:
        """Test location with invalid latitude."""
        data = {
            "latitude": Decimal("100"),  # Invalid (> 90)
            "longitude": Decimal("2.3522"),
        }
        with pytest.raises(ValidationError):
            Location(**data)

    def test_poi_brief(self) -> None:
        """Test POI brief schema."""
        data = {
            "id": uuid.uuid4(),
            "name": "Eiffel Tower",
            "categories": ["landmark", "attraction"],
            "latitude": Decimal("48.8584"),
            "longitude": Decimal("2.2945"),
            "rating": 4.5,
            "price_level": 2,
            "estimated_duration_minutes": 60,
        }
        schema = POIBrief(**data)
        assert schema.name == "Eiffel Tower"
        assert "landmark" in schema.categories

    def test_route_generate_request(self) -> None:
        """Test route generation request."""
        data = {
            "start_location": {
                "latitude": Decimal("48.8566"),
                "longitude": Decimal("2.3522"),
                "city": "Paris",
                "country": "France",
            },
            "max_duration_minutes": 240,
            "preferred_categories": ["museum", "landmark"],
            "transport_mode": "walking",
            "optimize_for": "satisfaction",
        }
        schema = RouteGenerateRequest(**data)
        assert schema.start_location.city == "Paris"
        assert schema.transport_mode == "walking"

    def test_route_generate_request_invalid_transport_mode(self) -> None:
        """Test route generation with invalid transport mode."""
        data = {
            "start_location": {
                "latitude": Decimal("48.8566"),
                "longitude": Decimal("2.3522"),
            },
            "transport_mode": "invalid",  # Must be walking/driving/transit/cycling
        }
        with pytest.raises(ValidationError):
            RouteGenerateRequest(**data)

    def test_route_stop(self) -> None:
        """Test route stop schema."""
        data = {
            "sequence_order": 1,
            "poi": {
                "id": uuid.uuid4(),
                "name": "Eiffel Tower",
                "categories": ["landmark"],
                "latitude": Decimal("48.8584"),
                "longitude": Decimal("2.2945"),
                "rating": 4.5,
                "price_level": 2,
                "estimated_duration_minutes": 60,
            },
            "estimated_arrival_time": datetime.now(),
            "estimated_duration_minutes": 60,
            "travel_time_minutes": 10,
        }
        schema = RouteStop(**data)
        assert schema.sequence_order == 1
        assert schema.travel_time_minutes == 10

    def test_route_response(self) -> None:
        """Test route response schema."""
        route_id = uuid.uuid4()
        data = {
            "id": route_id,
            "title": "Paris City Tour",
            "description": "A tour of Paris highlights",
            "status": "draft",
            "stops": [],
            "total_distance_km": 5.2,
            "total_duration_minutes": 240,
            "estimated_start_time": datetime.now(),
            "estimated_end_time": datetime.now(),
            "satisfaction_score": 0.85,
            "created_at": datetime.now(),
        }
        schema = RouteResponse(**data)
        assert schema.title == "Paris City Tour"
        assert schema.satisfaction_score == 0.85


class TestTourSchemas:
    """Tests for tour-related schemas."""

    def test_tour_start_request(self) -> None:
        """Test tour start request."""
        data = {
            "route_id": uuid.uuid4(),
            "enable_voice_guidance": True,
            "enable_proximity_alerts": True,
            "language": "en",
        }
        schema = TourStartRequest(**data)
        assert schema.enable_voice_guidance is True
        assert schema.language == "en"

    def test_tour_status(self) -> None:
        """Test tour status schema."""
        data = {
            "tour_id": uuid.uuid4(),
            "route_id": uuid.uuid4(),
            "status": "active",
            "current_stop_index": 0,
            "current_location": (48.8566, 2.3522),
            "started_at": datetime.now(),
            "estimated_end_time": datetime.now(),
            "progress_percentage": 0.0,
            "stops_visited": 0,
            "stops_remaining": 5,
        }
        schema = TourStatus(**data)
        assert schema.status == "active"
        assert schema.stops_remaining == 5

    def test_tour_stop_content(self) -> None:
        """Test tour stop content schema."""
        data = {
            "poi_id": uuid.uuid4(),
            "poi_name": "Eiffel Tower",
            "audio_content_url": "https://example.com/audio.mp3",
            "text_content": "The Eiffel Tower is a wrought-iron lattice tower...",
            "images": ["https://example.com/image1.jpg"],
            "fun_facts": ["Built in 1889", "324 meters tall"],
            "recommendations": ["Best view from Trocadero"],
        }
        schema = TourStopContent(**data)
        assert schema.poi_name == "Eiffel Tower"
        assert len(schema.fun_facts) == 2
