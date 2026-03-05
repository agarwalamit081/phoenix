"""Unit tests for tour modules."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from src.tour.orchestrator import (
    TourOrchestrator,
    TourState,
    TourStatus,
    TourEventType,
    TourCheckpoint,
)
from src.tour.tracker import (
    GPSTracker,
    LocationReading,
    LocationHistory,
    LocationAccuracy,
    MovementState,
)
from src.tour.content import (
    TourContentGenerator,
    ContentDeliveryManager,
    ContentItem,
    ContentContext,
    ContentType,
    DeliveryTrigger,
)
from src.tour.adaptive import (
    AdaptiveLearningEngine,
    AdaptiveParameters,
    FeedbackType,
    EngagementLevel,
)


@pytest.fixture
def sample_user_id():
    """Create sample user ID."""
    return uuid.uuid4()


@pytest.fixture
def sample_pois():
    """Create sample POIs."""
    return [
        {
            "id": "poi_1",
            "name": "Central Park",
            "category": "park",
            "latitude": 40.7829,
            "longitude": -73.9654,
            "rating": 4.8,
            "description": "A beautiful park in NYC",
        },
        {
            "id": "poi_2",
            "name": "Times Square",
            "category": "attraction",
            "latitude": 40.7580,
            "longitude": -73.9855,
            "rating": 4.5,
            "description": "Major commercial intersection",
        },
    ]


class TestTourOrchestrator:
    """Test tour orchestrator."""

    @pytest.mark.asyncio
    async def test_start_tour(self, sample_user_id, sample_pois):
        """Test starting a tour."""
        orchestrator = TourOrchestrator()

        state = await orchestrator.start_tour(
            user_id=sample_user_id,
            route_id="route_1",
            pois=sample_pois,
        )

        assert state.tour_id is not None
        assert state.user_id == sample_user_id
        assert state.route_id == "route_1"
        assert state.status == TourStatus.IN_PROGRESS
        assert len(state.checkpoints) == 2

    @pytest.mark.asyncio
    async def test_pause_tour(self, sample_user_id, sample_pois):
        """Test pausing a tour."""
        orchestrator = TourOrchestrator()

        state = await orchestrator.start_tour(
            user_id=sample_user_id,
            route_id="route_1",
            pois=sample_pois,
        )

        paused_state = await orchestrator.pause_tour(state.tour_id)

        assert paused_state.status == TourStatus.PAUSED
        assert paused_state.paused_at is not None

    @pytest.mark.asyncio
    async def test_resume_tour(self, sample_user_id, sample_pois):
        """Test resuming a tour."""
        orchestrator = TourOrchestrator()

        state = await orchestrator.start_tour(
            user_id=sample_user_id,
            route_id="route_1",
            pois=sample_pois,
        )

        await orchestrator.pause_tour(state.tour_id)
        resumed_state = await orchestrator.resume_tour(state.tour_id)

        assert resumed_state.status == TourStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_complete_tour(self, sample_user_id, sample_pois):
        """Test completing a tour."""
        orchestrator = TourOrchestrator()

        state = await orchestrator.start_tour(
            user_id=sample_user_id,
            route_id="route_1",
            pois=sample_pois,
        )

        completed_state = await orchestrator.complete_tour(state.tour_id)

        assert completed_state.status == TourStatus.COMPLETED
        assert completed_state.completed_at is not None

    @pytest.mark.asyncio
    async def test_cancel_tour(self, sample_user_id, sample_pois):
        """Test cancelling a tour."""
        orchestrator = TourOrchestrator()

        state = await orchestrator.start_tour(
            user_id=sample_user_id,
            route_id="route_1",
            pois=sample_pois,
        )

        cancelled_state = await orchestrator.cancel_tour(
            state.tour_id,
            reason="User requested",
        )

        assert cancelled_state.status == TourStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_update_location(self, sample_user_id, sample_pois):
        """Test updating location during tour."""
        orchestrator = TourOrchestrator()

        state = await orchestrator.start_tour(
            user_id=sample_user_id,
            route_id="route_1",
            pois=sample_pois,
        )

        location = {"lat": 40.7829, "lng": -73.9654}
        updated_state, events = await orchestrator.update_location(
            tour_id=state.tour_id,
            location=location,
        )

        assert updated_state.last_location == location
        assert isinstance(events, list)

    @pytest.mark.asyncio
    async def test_skip_poi(self, sample_user_id, sample_pois):
        """Test skipping a POI."""
        orchestrator = TourOrchestrator()

        state = await orchestrator.start_tour(
            user_id=sample_user_id,
            route_id="route_1",
            pois=sample_pois,
        )

        updated_state = await orchestrator.skip_poi(
            tour_id=state.tour_id,
            poi_id="poi_1",
        )

        assert updated_state.checkpoints["poi_1"].skipped is True


class TestGPSTracker:
    """Test GPS tracker."""

    @pytest.mark.asyncio
    async def test_start_tracking(self, sample_user_id):
        """Test starting GPS tracking."""
        tracker = GPSTracker()

        history = await tracker.start_tracking(
            tour_id="tour_1",
            user_id=sample_user_id,
        )

        assert history.tour_id == "tour_1"
        assert history.user_id == sample_user_id

    @pytest.mark.asyncio
    async def test_update_location(self, sample_user_id):
        """Test updating location."""
        tracker = GPSTracker()

        await tracker.start_tracking("tour_1", sample_user_id)

        reading, distance = await tracker.update_location(
            tour_id="tour_1",
            latitude=40.7829,
            longitude=-73.9654,
            accuracy=10.0,
        )

        assert reading is not None
        assert reading.latitude == 40.7829
        assert reading.longitude == -73.9654
        assert reading.accuracy == 10.0

    @pytest.mark.asyncio
    async def test_filter_poor_accuracy(self, sample_user_id):
        """Test filtering poor accuracy readings."""
        tracker = GPSTracker(min_accuracy=50.0)

        await tracker.start_tracking("tour_1", sample_user_id)

        reading, distance = await tracker.update_location(
            tour_id="tour_1",
            latitude=40.7829,
            longitude=-73.9654,
            accuracy=100.0,  # Poor accuracy
        )

        assert reading is None  # Should be filtered

    @pytest.mark.asyncio
    async def test_detect_movement_walking(self, sample_user_id):
        """Test detecting walking movement."""
        tracker = GPSTracker()

        await tracker.start_tracking("tour_1", sample_user_id)

        # Add multiple walking-speed readings to build history
        await tracker.update_location(
            tour_id="tour_1",
            latitude=40.7829,
            longitude=-73.9654,
            speed=1.5,  # m/s (walking)
        )
        await tracker.update_location(
            tour_id="tour_1",
            latitude=40.7830,
            longitude=-73.9655,
            speed=1.4,  # m/s (walking)
        )
        await tracker.update_location(
            tour_id="tour_1",
            latitude=40.7831,
            longitude=-73.9656,
            speed=1.6,  # m/s (walking)
        )

        movement = await tracker.detect_movement_state("tour_1")

        assert movement == MovementState.WALKING

    @pytest.mark.asyncio
    async def test_get_statistics(self, sample_user_id):
        """Test getting tracking statistics."""
        tracker = GPSTracker()

        await tracker.start_tracking("tour_1", sample_user_id)

        await tracker.update_location(
            tour_id="tour_1",
            latitude=40.7829,
            longitude=-73.9654,
        )

        stats = await tracker.get_statistics("tour_1")

        assert stats is not None
        assert stats["total_readings"] == 1
        assert stats["tour_id"] == "tour_1"


class TestTourContentGenerator:
    """Test tour content generator."""

    @pytest.mark.asyncio
    async def test_generate_poi_content(self):
        """Test generating POI content."""
        generator = TourContentGenerator()

        poi = {
            "id": "poi_1",
            "name": "Central Park",
            "category": "park",
            "description": "A beautiful park",
        }

        context = ContentContext(
            user_id=uuid.uuid4(),
            tour_id="tour_1",
            poi_id="poi_1",
            language="en",
        )

        with patch.object(generator.llm_service, 'chat_completion', return_value={"content": "Welcome to Central Park!\n\nIt's a great place."}):
            content = await generator.generate_poi_content(
                poi=poi,
                context=context,
                content_type=ContentType.AUDIO_NARRATION,
            )

            assert content.poi_id == "poi_1"
            assert content.content_type == ContentType.AUDIO_NARRATION
            assert content.title is not None

    @pytest.mark.asyncio
    async def test_generate_direction_content(self):
        """Test generating direction content."""
        generator = TourContentGenerator()

        from_poi = {"name": "Central Park"}
        to_poi = {"name": "Times Square"}

        context = ContentContext(
            user_id=uuid.uuid4(),
            tour_id="tour_1",
            language="en",
        )

        with patch.object(generator.llm_service, 'chat_completion', return_value={"content": "Head to Times Square\nIt's a 10-minute walk."}):
            content = await generator.generate_direction_content(
                from_poi=from_poi,
                to_poi=to_poi,
                distance_meters=500,
                duration_minutes=10,
                context=context,
            )

            assert content.content_type == ContentType.DIRECTION
            assert "Times Square" in content.body or "10" in content.body


class TestContentDeliveryManager:
    """Test content delivery manager."""

    @pytest.mark.asyncio
    async def test_queue_and_get_content(self):
        """Test queuing and getting content."""
        manager = ContentDeliveryManager()

        content = ContentItem(
            poi_id="poi_1",
            content_type=ContentType.AUDIO_NARRATION,
            title="Welcome",
            body="Welcome to our tour!",
            trigger=DeliveryTrigger.ON_ARRIVAL,
        )

        await manager.queue_content("tour_1", content)

        items = await manager.get_content_for_trigger(
            tour_id="tour_1",
            poi_id="poi_1",
            trigger=DeliveryTrigger.ON_ARRIVAL,
            context=ContentContext(user_id=uuid.uuid4(), tour_id="tour_1"),
        )

        assert len(items) == 1
        assert items[0].id == content.id

    @pytest.mark.asyncio
    async def test_clear_tour_content(self):
        """Test clearing tour content."""
        manager = ContentDeliveryManager()

        content = ContentItem(
            poi_id="poi_1",
            content_type=ContentType.TEXT_INFO,
            title="Info",
            body="Some info",
            trigger=DeliveryTrigger.ON_ARRIVAL,
        )

        await manager.queue_content("tour_1", content)
        assert manager.get_pending_count("tour_1") == 1

        manager.clear_tour_content("tour_1")
        assert manager.get_pending_count("tour_1") == 0


class TestAdaptiveLearningEngine:
    """Test adaptive learning engine."""

    @pytest.mark.asyncio
    async def test_record_behavior(self):
        """Test recording user behavior."""
        engine = AdaptiveLearningEngine()
        user_id = uuid.uuid4()

        await engine.record_behavior(
            user_id=user_id,
            behavior_type="photo_taken",
            tour_id="tour_1",
            poi_id="poi_1",
            data={"poi_category": "park"},
        )

        behaviors = engine._behaviors.get(user_id, [])
        assert len(behaviors) == 1
        assert behaviors[0].behavior_type == "photo_taken"

    @pytest.mark.asyncio
    async def test_record_feedback(self):
        """Test recording user feedback."""
        engine = AdaptiveLearningEngine()
        user_id = uuid.uuid4()

        await engine.record_feedback(
            user_id=user_id,
            feedback_type=FeedbackType.CONTENT_HELPFUL,
            tour_id="tour_1",
            rating=5,
        )

        feedback_list = engine._feedback.get(user_id, [])
        assert len(feedback_list) == 1

    @pytest.mark.asyncio
    async def test_calculate_engagement_high(self):
        """Test calculating high engagement."""
        engine = AdaptiveLearningEngine()
        user_id = uuid.uuid4()

        # Add positive behaviors
        await engine.record_behavior(user_id, "content_completed", "tour_1", "poi_1")
        await engine.record_behavior(user_id, "poi_reached", "tour_1", "poi_2")
        await engine.record_behavior(user_id, "photo_taken", "tour_1", "poi_1")

        engagement = await engine.calculate_engagement_level(user_id, "tour_1")

        assert engagement == EngagementLevel.HIGH

    @pytest.mark.asyncio
    async def test_recommend_pace_adjustment(self):
        """Test recommending pace adjustment."""
        engine = AdaptiveLearningEngine()
        user_id = uuid.uuid4()

        # Record feedback that pace is too fast
        await engine.record_feedback(
            user_id=user_id,
            feedback_type=FeedbackType.PACE_TOO_FAST,
            tour_id="tour_1",
        )

        pace, confidence = await engine.recommend_pace_adjustment(user_id, "medium")

        assert pace == "slow"

    @pytest.mark.asyncio
    async def test_get_user_parameters(self):
        """Test getting user parameters."""
        engine = AdaptiveLearningEngine()
        user_id = uuid.uuid4()

        params = await engine.get_user_parameters(user_id)

        assert params.preferred_content_length == "medium"
        assert params.preferred_pace == "medium"

    @pytest.mark.asyncio
    async def test_extract_interests(self):
        """Test extracting user interests."""
        engine = AdaptiveLearningEngine()
        user_id = uuid.uuid4()

        await engine.record_behavior(
            user_id,
            "photo_taken",
            "tour_1",
            "poi_1",
            data={"poi_category": "park"},
        )
        await engine.record_behavior(
            user_id,
            "photo_taken",
            "tour_1",
            "poi_2",
            data={"poi_category": "museum"},
        )

        interests = await engine.extract_interests(user_id)

        assert "park" in interests
        assert "museum" in interests

    @pytest.mark.asyncio
    async def test_reset_user_data(self):
        """Test resetting user data."""
        engine = AdaptiveLearningEngine()
        user_id = uuid.uuid4()

        await engine.record_behavior(user_id, "test", "tour_1", "poi_1")
        await engine.reset_user_data(user_id)

        assert user_id not in engine._behaviors


class TestTourState:
    """Test tour state serialization."""

    def test_to_dict(self, sample_user_id):
        """Test converting state to dictionary."""
        state = TourState(
            tour_id="tour_1",
            user_id=sample_user_id,
            route_id="route_1",
            status=TourStatus.IN_PROGRESS,
        )

        data = state.to_dict()

        assert data["tour_id"] == "tour_1"
        assert data["status"] == "in_progress"

    def test_from_dict(self, sample_user_id):
        """Test creating state from dictionary."""
        data = {
            "tour_id": "tour_1",
            "user_id": str(sample_user_id),
            "route_id": "route_1",
            "status": "in_progress",
            "current_poi_index": 0,
            "checkpoints": {},
            "started_at": datetime.now(timezone.utc).isoformat(),
            "paused_at": None,
            "completed_at": None,
            "last_location": None,
            "last_location_update": None,
            "total_distance_meters": 0.0,
            "estimated_remaining_minutes": 0,
            "events": [],
            "metadata": {},
        }

        state = TourState.from_dict(data)

        assert state.tour_id == "tour_1"
        assert state.user_id == sample_user_id
