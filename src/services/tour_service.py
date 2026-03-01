"""Tour service for managing guided tours."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    NotFoundError,
    ValidationError,
)
from src.services.route_service import RouteService
from src.services.preference_service import PreferenceService
from src.services.map_service import MapService
from src.tour.orchestrator import (
    TourOrchestrator,
    TourStatus,
    TourEventType,
)
from src.tour.tracker import GPSTracker
from src.tour.content import (
    TourContentGenerator,
    ContentDeliveryManager,
    ContentContext,
    ContentType,
    DeliveryTrigger,
)
from src.tour.adaptive import (
    AdaptiveLearningEngine,
    FeedbackType,
)

logger = logging.getLogger(__name__)


class TourService:
    """Service for managing guided tours."""

    def __init__(
        self,
        db: AsyncSession,
        orchestrator: TourOrchestrator | None = None,
        tracker: GPSTracker | None = None,
        content_generator: TourContentGenerator | None = None,
        delivery_manager: ContentDeliveryManager | None = None,
        learning_engine: AdaptiveLearningEngine | None = None,
    ) -> None:
        """Initialize tour service.

        Args:
            db: Database session
            orchestrator: Optional tour orchestrator
            tracker: Optional GPS tracker
            content_generator: Optional content generator
            delivery_manager: Optional content delivery manager
            learning_engine: Optional adaptive learning engine
        """
        self.db = db
        self.orchestrator = orchestrator or TourOrchestrator()
        self.tracker = tracker or GPSTracker()
        self.content_generator = content_generator or TourContentGenerator()
        self.delivery_manager = delivery_manager or ContentDeliveryManager(self.content_generator)
        self.learning_engine = learning_engine or AdaptiveLearningEngine()
        self.route_service = RouteService(db)
        self.preference_service = PreferenceService(db)
        self.map_service = MapService(db)

    async def start_tour(
        self,
        user_id: uuid.UUID,
        route_id: str,
        language: str = "en",
    ) -> dict[str, Any]:
        """Start a new guided tour.

        Args:
            user_id: User ID
            route_id: Route ID
            language: Content language

        Returns:
            Tour data with state
        """
        # Get route details
        route = await self.route_service.get_route(route_id)
        if not route:
            raise NotFoundError(
                resource="Route",
                identifier=route_id,
            )

        pois = route.get("plan", {}).get("pois", [])
        if not pois:
            raise ValidationError(
                message="Route has no points of interest",
                details={"route_id": route_id},
            )

        # Start the tour
        state = await self.orchestrator.start_tour(
            user_id=user_id,
            route_id=route_id,
            pois=pois,
            metadata={"language": language},
        )

        # Start GPS tracking
        await self.tracker.start_tracking(state.tour_id, user_id)

        # Get user preferences for personalization
        preferences = await self.preference_service.get_user_preferences(str(user_id))

        # Generate and queue content for each POI
        for poi in pois:
            context = ContentContext(
                user_id=user_id,
                tour_id=state.tour_id,
                poi_id=poi.get("id"),
                user_preferences=preferences,
                language=language,
            )

            # Generate arrival content
            arrival_content = await self.content_generator.generate_poi_content(
                poi=poi,
                context=context,
                content_type=ContentType.AUDIO_NARRATION,
            )
            arrival_content.trigger = DeliveryTrigger.ON_ARRIVAL
            await self.delivery_manager.queue_content(state.tour_id, arrival_content)

            # Generate approach content (50m before)
            approach_content = await self.content_generator.generate_poi_content(
                poi=poi,
                context=context,
                content_type=ContentType.FUN_FACT,
            )
            approach_content.trigger = DeliveryTrigger.PROXIMITY_BASED
            approach_content.trigger_distance_meters = 50
            await self.delivery_manager.queue_content(state.tour_id, approach_content)

        logger.info(f"Started tour {state.tour_id} for user {user_id} with route {route_id}")

        return {
            "tour_id": state.tour_id,
            "route_id": route_id,
            "status": state.status.value,
            "total_pois": len(pois),
            "started_at": state.started_at.isoformat() if state.started_at else None,
            "language": language,
        }

    async def pause_tour(
        self,
        tour_id: str,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Pause a tour.

        Args:
            tour_id: Tour ID
            user_id: User ID

        Returns:
            Updated tour data
        """
        # Verify user owns this tour
        state = await self.orchestrator.get_tour_state(tour_id)
        if state.user_id != user_id:
            raise ValidationError(
                message="You don't have permission to pause this tour",
                details={"tour_id": tour_id},
            )

        updated_state = await self.orchestrator.pause_tour(tour_id)

        return {
            "tour_id": tour_id,
            "status": updated_state.status.value,
            "paused_at": updated_state.paused_at.isoformat() if updated_state.paused_at else None,
        }

    async def resume_tour(
        self,
        tour_id: str,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Resume a paused tour.

        Args:
            tour_id: Tour ID
            user_id: User ID

        Returns:
            Updated tour data
        """
        # Verify user owns this tour
        state = await self.orchestrator.get_tour_state(tour_id)
        if state.user_id != user_id:
            raise ValidationError(
                message="You don't have permission to resume this tour",
                details={"tour_id": tour_id},
            )

        updated_state = await self.orchestrator.resume_tour(tour_id)

        return {
            "tour_id": tour_id,
            "status": updated_state.status.value,
        }

    async def complete_tour(
        self,
        tour_id: str,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Complete a tour.

        Args:
            tour_id: Tour ID
            user_id: User ID

        Returns:
            Updated tour data
        """
        # Verify user owns this tour
        state = await self.orchestrator.get_tour_state(tour_id)
        if state.user_id != user_id:
            raise ValidationError(
                message="You don't have permission to complete this tour",
                details={"tour_id": tour_id},
            )

        # Complete the tour
        updated_state = await self.orchestrator.complete_tour(tour_id)

        # Stop GPS tracking
        await self.tracker.stop_tracking(tour_id)

        # Get final statistics
        stats = await self.tracker.get_statistics(tour_id)

        # Get personalization insights
        insights = await self.learning_engine.get_personalization_insights(user_id)

        return {
            "tour_id": tour_id,
            "status": updated_state.status.value,
            "completed_at": updated_state.completed_at.isoformat() if updated_state.completed_at else None,
            "statistics": stats,
            "insights": insights,
        }

    async def cancel_tour(
        self,
        tour_id: str,
        user_id: uuid.UUID,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Cancel a tour.

        Args:
            tour_id: Tour ID
            user_id: User ID
            reason: Optional cancellation reason

        Returns:
            Updated tour data
        """
        # Verify user owns this tour
        state = await self.orchestrator.get_tour_state(tour_id)
        if state.user_id != user_id:
            raise ValidationError(
                message="You don't have permission to cancel this tour",
                details={"tour_id": tour_id},
            )

        # Cancel the tour
        updated_state = await self.orchestrator.cancel_tour(tour_id, reason)

        # Stop GPS tracking
        await self.tracker.stop_tracking(tour_id)

        # Record cancellation behavior
        await self.learning_engine.record_behavior(
            user_id=user_id,
            behavior_type="tour_cancelled",
            tour_id=tour_id,
            data={"reason": reason},
        )

        return {
            "tour_id": tour_id,
            "status": updated_state.status.value,
        }

    async def update_location(
        self,
        tour_id: str,
        user_id: uuid.UUID,
        latitude: float,
        longitude: float,
        accuracy: float | None = None,
    ) -> dict[str, Any]:
        """Update user location during tour.

        Args:
            tour_id: Tour ID
            user_id: User ID
            latitude: Latitude
            longitude: Longitude
            accuracy: GPS accuracy in meters

        Returns:
            Location update result with any triggered content
        """
        # Verify user owns this tour
        state = await self.orchestrator.get_tour_state(tour_id)
        if state.user_id != user_id:
            raise ValidationError(
                message="You don't have permission to update this tour",
                details={"tour_id": tour_id},
            )

        # Update location in tracker
        reading, distance = await self.tracker.update_location(
            tour_id=tour_id,
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
        )

        if not reading:
            return {
                "tour_id": tour_id,
                "location_filtered": True,
                "reason": "Poor accuracy or stale reading",
            }

        # Update location in orchestrator
        location = {"lat": latitude, "lng": longitude}
        updated_state, triggered_events = await self.orchestrator.update_location(
            tour_id=tour_id,
            location=location,
            accuracy_meters=accuracy,
        )

        # Check for content to deliver
        content_to_deliver = []
        for event in triggered_events:
            if event.startswith("poi_reached:"):
                poi_id = event.split(":", 1)[1]

                # Get preferences for context
                preferences = await self.preference_service.get_user_preferences(str(user_id))

                context = ContentContext(
                    user_id=user_id,
                    tour_id=tour_id,
                    poi_id=poi_id,
                    user_preferences=preferences,
                    language=state.metadata.get("language", "en"),
                )

                # Get content for arrival
                items = await self.delivery_manager.get_content_for_trigger(
                    tour_id=tour_id,
                    poi_id=poi_id,
                    trigger=DeliveryTrigger.ON_ARRIVAL,
                    context=context,
                )
                content_to_deliver.extend(items)

        return {
            "tour_id": tour_id,
            "location": location,
            "accuracy": accuracy,
            "distance_traveled_meters": distance,
            "total_distance_meters": updated_state.total_distance_meters,
            "content_to_deliver": [c.to_dict() for c in content_to_deliver],
            "estimated_remaining_minutes": updated_state.estimated_remaining_minutes,
        }

    async def skip_poi(
        self,
        tour_id: str,
        user_id: uuid.UUID,
        poi_id: str,
    ) -> dict[str, Any]:
        """Skip a POI in the tour.

        Args:
            tour_id: Tour ID
            user_id: User ID
            poi_id: POI ID to skip

        Returns:
            Updated tour data
        """
        # Verify user owns this tour
        state = await self.orchestrator.get_tour_state(tour_id)
        if state.user_id != user_id:
            raise ValidationError(
                message="You don't have permission to modify this tour",
                details={"tour_id": tour_id},
            )

        updated_state = await self.orchestrator.skip_poi(tour_id, poi_id)

        # Record skip behavior
        await self.learning_engine.record_behavior(
            user_id=user_id,
            behavior_type="poi_skipped",
            tour_id=tour_id,
            poi_id=poi_id,
        )

        return {
            "tour_id": tour_id,
            "poi_id": poi_id,
            "skipped": True,
        }

    async def submit_feedback(
        self,
        tour_id: str,
        user_id: uuid.UUID,
        feedback_type: str,
        rating: int | None = None,
        poi_id: str | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Submit tour feedback.

        Args:
            tour_id: Tour ID
            user_id: User ID
            feedback_type: Type of feedback
            rating: Optional rating (1-5)
            poi_id: Optional POI ID
            comment: Optional comment

        Returns:
            Feedback confirmation
        """
        # Verify user owns this tour
        state = await self.orchestrator.get_tour_state(tour_id)
        if state.user_id != user_id:
            raise ValidationError(
                message="You don't have permission to submit feedback for this tour",
                details={"tour_id": tour_id},
            )

        # Validate feedback type
        try:
            fb_type = FeedbackType(feedback_type)
        except ValueError:
            raise ValidationError(
                message=f"Invalid feedback type: {feedback_type}",
                details={"valid_types": [t.value for t in FeedbackType]},
            )

        # Record feedback
        await self.learning_engine.record_feedback(
            user_id=user_id,
            feedback_type=fb_type,
            tour_id=tour_id,
            rating=rating,
            poi_id=poi_id,
            comment=comment,
        )

        logger.info(
            f"Recorded feedback {feedback_type} (rating={rating}) "
            f"for tour {tour_id} by user {user_id}"
        )

        return {
            "tour_id": tour_id,
            "feedback_type": feedback_type,
            "rating": rating,
            "recorded": True,
        }

    async def get_tour_status(
        self,
        tour_id: str,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Get tour status and details.

        Args:
            tour_id: Tour ID
            user_id: User ID

        Returns:
            Tour status details
        """
        state = await self.orchestrator.get_tour_state(tour_id)

        if state.user_id != user_id:
            raise ValidationError(
                message="You don't have permission to view this tour",
                details={"tour_id": tour_id},
            )

        # Get tracking statistics
        stats = await self.tracker.get_statistics(tour_id)

        # Get current location
        current_location = await self.tracker.get_current_location(tour_id)

        return {
            "tour_id": state.tour_id,
            "route_id": state.route_id,
            "status": state.status.value,
            "current_poi_index": state.current_poi_index,
            "started_at": state.started_at.isoformat() if state.started_at else None,
            "paused_at": state.paused_at.isoformat() if state.paused_at else None,
            "completed_at": state.completed_at.isoformat() if state.completed_at else None,
            "total_distance_meters": state.total_distance_meters,
            "estimated_remaining_minutes": state.estimated_remaining_minutes,
            "last_location": current_location.to_dict() if current_location else None,
            "tracking_statistics": stats,
        }

    async def get_user_active_tours(
        self,
        user_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Get active tours for a user.

        Args:
            user_id: User ID

        Returns:
            List of active tours
        """
        active_states = self.orchestrator.get_user_active_tours(user_id)

        tours = []
        for state in active_states:
            tours.append({
                "tour_id": state.tour_id,
                "route_id": state.route_id,
                "status": state.status.value,
                "started_at": state.started_at.isoformat() if state.started_at else None,
                "total_distance_meters": state.total_distance_meters,
            })

        return tours

    async def get_personalization_insights(
        self,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Get personalization insights for a user.

        Args:
            user_id: User ID

        Returns:
            Personalization insights
        """
        return await self.learning_engine.get_personalization_insights(user_id)

    async def suggest_content(
        self,
        tour_id: str,
        user_id: uuid.UUID,
        poi_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get suggested content for current location.

        Args:
            tour_id: Tour ID
            user_id: User ID
            poi_id: Optional POI ID

        Returns:
            List of suggested content items
        """
        # Verify user owns this tour
        state = await self.orchestrator.get_tour_state(tour_id)
        if state.user_id != user_id:
            raise ValidationError(
                message="You don't have permission to access this tour",
                details={"tour_id": tour_id},
            )

        # Get preferences
        preferences = await self.preference_service.get_user_preferences(str(user_id))

        context = ContentContext(
            user_id=user_id,
            tour_id=tour_id,
            poi_id=poi_id,
            user_preferences=preferences,
            language=state.metadata.get("language", "en"),
        )

        # Get adaptive parameters
        params = await self.learning_engine.get_user_parameters(user_id)

        # Generate content based on request
        if poi_id:
            # Get POI data
            route = await self.route_service.get_route(state.route_id)
            pois = route.get("plan", {}).get("pois", [])
            poi = next((p for p in pois if p.get("id") == poi_id), None)

            if poi:
                # Generate content based on preferences
                content = await self.content_generator.generate_poi_content(
                    poi=poi,
                    context=context,
                    content_type=ContentType.AUDIO_NARRATION,
                )

                # Personalize based on adaptive parameters
                content = await self.content_generator.personalize_content(
                    content,
                    preferences,
                )

                return [content.to_dict()]

        return []
