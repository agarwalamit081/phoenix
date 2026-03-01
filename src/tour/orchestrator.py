"""Guided tour orchestrator for managing real-time tour execution."""

import asyncio
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

from src.core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class TourStatus(str, Enum):
    """Tour execution status."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class TourEventType(str, Enum):
    """Tour event types."""

    TOUR_STARTED = "tour_started"
    TOUR_PAUSED = "tour_paused"
    TOUR_RESUMED = "tour_resumed"
    TOUR_COMPLETED = "tour_completed"
    TOUR_CANCELLED = "tour_cancelled"
    POI_REACHED = "poi_reached"
    POI_SKIPPED = "poi_skipped"
    LOCATION_UPDATED = "location_updated"
    ROUTE_DEVIATED = "route_deviated"
    TIME_REMAINING = "time_remaining"
    CONTENT_DELIVERED = "content_delivered"
    ERROR_OCCURRED = "error_occurred"


@dataclass
class TourCheckpoint:
    """Tour checkpoint for state persistence."""

    poi_id: str
    reached_at: datetime | None = None
    skipped: bool = False
    time_spent_seconds: int = 0
    content_delivered: list[str] = field(default_factory=list)


@dataclass
class TourState:
    """Tour execution state."""

    tour_id: str
    user_id: uuid.UUID
    route_id: str
    status: TourStatus = TourStatus.NOT_STARTED
    current_poi_index: int = 0
    checkpoints: dict[str, TourCheckpoint] = field(default_factory=dict)
    started_at: datetime | None = None
    paused_at: datetime | None = None
    completed_at: datetime | None = None
    last_location: dict[str, float] | None = None
    last_location_update: datetime | None = None
    total_distance_meters: float = 0.0
    estimated_remaining_minutes: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "tour_id": self.tour_id,
            "user_id": str(self.user_id),
            "route_id": self.route_id,
            "status": self.status.value,
            "current_poi_index": self.current_poi_index,
            "checkpoints": {
                k: {
                    "poi_id": v.poi_id,
                    "reached_at": v.reached_at.isoformat() if v.reached_at else None,
                    "skipped": v.skipped,
                    "time_spent_seconds": v.time_spent_seconds,
                    "content_delivered": v.content_delivered,
                }
                for k, v in self.checkpoints.items()
            },
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "paused_at": self.paused_at.isoformat() if self.paused_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "last_location": self.last_location,
            "last_location_update": self.last_location_update.isoformat() if self.last_location_update else None,
            "total_distance_meters": self.total_distance_meters,
            "estimated_remaining_minutes": self.estimated_remaining_minutes,
            "events": self.events,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TourState":
        """Create from dictionary.

        Args:
            data: Dictionary data

        Returns:
            Tour state instance
        """
        checkpoints = {}
        for k, v in data.get("checkpoints", {}).items():
            checkpoints[k] = TourCheckpoint(
                poi_id=v["poi_id"],
                reached_at=datetime.fromisoformat(v["reached_at"]) if v.get("reached_at") else None,
                skipped=v.get("skipped", False),
                time_spent_seconds=v.get("time_spent_seconds", 0),
                content_delivered=v.get("content_delivered", []),
            )

        return cls(
            tour_id=data["tour_id"],
            user_id=uuid.UUID(data["user_id"]),
            route_id=data["route_id"],
            status=TourStatus(data.get("status", TourStatus.NOT_STARTED)),
            current_poi_index=data.get("current_poi_index", 0),
            checkpoints=checkpoints,
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            paused_at=datetime.fromisoformat(data["paused_at"]) if data.get("paused_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            last_location=data.get("last_location"),
            last_location_update=datetime.fromisoformat(data["last_location_update"]) if data.get("last_location_update") else None,
            total_distance_meters=data.get("total_distance_meters", 0.0),
            estimated_remaining_minutes=data.get("estimated_remaining_minutes", 0),
            events=data.get("events", []),
            metadata=data.get("metadata", {}),
        )


class TourOrchestrator:
    """Orchestrates guided tour execution."""

    def __init__(
        self,
        state_store: Any | None = None,
    ) -> None:
        """Initialize tour orchestrator.

        Args:
            state_store: Optional state store for persistence
        """
        self.state_store = state_store
        self._active_tours: dict[str, TourState] = {}
        self._event_handlers: dict[TourEventType, list[Any]] = defaultdict(list)

    async def start_tour(
        self,
        user_id: uuid.UUID,
        route_id: str,
        pois: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> TourState:
        """Start a new guided tour.

        Args:
            user_id: User ID
            route_id: Route ID
            pois: List of POIs in the route
            metadata: Optional metadata

        Returns:
            Tour state
        """
        tour_id = str(uuid.uuid4())

        # Create checkpoints for each POI
        checkpoints = {}
        for poi in pois:
            poi_id = poi.get("id", str(uuid.uuid4()))
            checkpoints[poi_id] = TourCheckpoint(poi_id=poi_id)

        state = TourState(
            tour_id=tour_id,
            user_id=user_id,
            route_id=route_id,
            status=TourStatus.IN_PROGRESS,
            started_at=datetime.now(timezone.utc),
            checkpoints=checkpoints,
            metadata=metadata or {},
        )

        self._active_tours[tour_id] = state

        # Persist state
        if self.state_store:
            await self._persist_state(state)

        # Emit event
        await self._emit_event(
            tour_id,
            TourEventType.TOUR_STARTED,
            {"route_id": route_id, "total_pois": len(pois)},
        )

        logger.info(f"Started tour {tour_id} for user {user_id}")

        return state

    async def pause_tour(self, tour_id: str) -> TourState:
        """Pause a tour.

        Args:
            tour_id: Tour ID

        Returns:
            Updated tour state

        Raises:
            NotFoundError: If tour not found
        """
        state = await self._get_tour_state(tour_id)

        if state.status != TourStatus.IN_PROGRESS:
            raise ValidationError(
                message=f"Cannot pause tour with status {state.status.value}",
                details={"tour_id": tour_id, "current_status": state.status.value},
            )

        state.status = TourStatus.PAUSED
        state.paused_at = datetime.now(timezone.utc)

        if self.state_store:
            await self._persist_state(state)

        await self._emit_event(
            tour_id,
            TourEventType.TOUR_PAUSED,
            {"paused_at": state.paused_at.isoformat()},
        )

        logger.info(f"Paused tour {tour_id}")

        return state

    async def resume_tour(self, tour_id: str) -> TourState:
        """Resume a paused tour.

        Args:
            tour_id: Tour ID

        Returns:
            Updated tour state

        Raises:
            NotFoundError: If tour not found
        """
        state = await self._get_tour_state(tour_id)

        if state.status != TourStatus.PAUSED:
            raise ValidationError(
                message=f"Cannot resume tour with status {state.status.value}",
                details={"tour_id": tour_id, "current_status": state.status.value},
            )

        state.status = TourStatus.IN_PROGRESS
        state.paused_at = None

        if self.state_store:
            await self._persist_state(state)

        await self._emit_event(
            tour_id,
            TourEventType.TOUR_RESUMED,
            {"resumed_at": datetime.now(timezone.utc).isoformat()},
        )

        logger.info(f"Resumed tour {tour_id}")

        return state

    async def complete_tour(self, tour_id: str) -> TourState:
        """Complete a tour.

        Args:
            tour_id: Tour ID

        Returns:
            Updated tour state

        Raises:
            NotFoundError: If tour not found
        """
        state = await self._get_tour_state(tour_id)

        state.status = TourStatus.COMPLETED
        state.completed_at = datetime.now(timezone.utc)

        if self.state_store:
            await self._persist_state(state)

        await self._emit_event(
            tour_id,
            TourEventType.TOUR_COMPLETED,
            {
                "completed_at": state.completed_at.isoformat(),
                "total_distance_meters": state.total_distance_meters,
            },
        )

        logger.info(f"Completed tour {tour_id}")

        return state

    async def cancel_tour(self, tour_id: str, reason: str | None = None) -> TourState:
        """Cancel a tour.

        Args:
            tour_id: Tour ID
            reason: Optional cancellation reason

        Returns:
            Updated tour state

        Raises:
            NotFoundError: If tour not found
        """
        state = await self._get_tour_state(tour_id)

        state.status = TourStatus.CANCELLED

        if self.state_store:
            await self._persist_state(state)

        await self._emit_event(
            tour_id,
            TourEventType.TOUR_CANCELLED,
            {"reason": reason or "User cancelled"},
        )

        logger.info(f"Cancelled tour {tour_id}: {reason}")

        return state

    async def update_location(
        self,
        tour_id: str,
        location: dict[str, float],
        accuracy_meters: float | None = None,
    ) -> tuple[TourState, list[str]]:
        """Update user location during tour.

        Args:
            tour_id: Tour ID
            location: Location coordinates (lat, lng)
            accuracy_meters: GPS accuracy in meters

        Returns:
            Tuple of (updated state, triggered events)

        Raises:
            NotFoundError: If tour not found
        """
        state = await self._get_tour_state(tour_id)

        if state.status != TourStatus.IN_PROGRESS:
            return state, []

        # Update location
        state.last_location = location
        state.last_location_update = datetime.now(timezone.utc)

        triggered_events = []

        # Check for proximity to POIs
        nearby_pois = await self._check_nearby_pois(state, location)
        for poi_id, distance_m in nearby_pois:
            if poi_id not in state.checkpoints:
                continue

            checkpoint = state.checkpoints[poi_id]

            # Mark as reached if not already
            if not checkpoint.reached_at and distance_m < 50:  # 50m threshold
                checkpoint.reached_at = datetime.now(timezone.utc)
                triggered_events.append(f"poi_reached:{poi_id}")

                await self._emit_event(
                    tour_id,
                    TourEventType.POI_REACHED,
                    {
                        "poi_id": poi_id,
                        "distance_meters": distance_m,
                    },
                )

        # Calculate total distance
        if state.last_location:
            distance = await self._calculate_distance(
                state.last_location,
                location,
            )
            state.total_distance_meters += distance

        # Estimate remaining time
        state.estimated_remaining_minutes = await self._estimate_remaining_time(state)

        if self.state_store:
            await self._persist_state(state)

        await self._emit_event(
            tour_id,
            TourEventType.LOCATION_UPDATED,
            {
                "location": location,
                "accuracy_meters": accuracy_meters,
            },
        )

        return state, triggered_events

    async def skip_poi(self, tour_id: str, poi_id: str) -> TourState:
        """Skip a POI in the tour.

        Args:
            tour_id: Tour ID
            poi_id: POI ID to skip

        Returns:
            Updated tour state

        Raises:
            NotFoundError: If tour or POI not found
        """
        state = await self._get_tour_state(tour_id)

        if poi_id not in state.checkpoints:
            raise NotFoundError(
                resource="POI",
                identifier=poi_id,
                details={"tour_id": tour_id},
            )

        checkpoint = state.checkpoints[poi_id]
        if checkpoint.reached_at:
            raise ValidationError(
                message="Cannot skip POI that has already been reached",
                details={"tour_id": tour_id, "poi_id": poi_id},
            )

        checkpoint.skipped = True

        if self.state_store:
            await self._persist_state(state)

        await self._emit_event(
            tour_id,
            TourEventType.POI_SKIPPED,
            {"poi_id": poi_id},
        )

        logger.info(f"Skipped POI {poi_id} in tour {tour_id}")

        return state

    async def record_content_delivery(
        self,
        tour_id: str,
        poi_id: str,
        content_type: str,
        content_id: str,
    ) -> TourState:
        """Record that content was delivered to user.

        Args:
            tour_id: Tour ID
            poi_id: POI ID
            content_type: Type of content (audio, text, image, etc.)
            content_id: Content ID

        Returns:
            Updated tour state

        Raises:
            NotFoundError: If tour or POI not found
        """
        state = await self._get_tour_state(tour_id)

        if poi_id not in state.checkpoints:
            raise NotFoundError(
                resource="POI",
                identifier=poi_id,
                details={"tour_id": tour_id},
            )

        checkpoint = state.checkpoints[poi_id]
        content_key = f"{content_type}:{content_id}"

        if content_key not in checkpoint.content_delivered:
            checkpoint.content_delivered.append(content_key)

        if self.state_store:
            await self._persist_state(state)

        await self._emit_event(
            tour_id,
            TourEventType.CONTENT_DELIVERED,
            {
                "poi_id": poi_id,
                "content_type": content_type,
                "content_id": content_id,
            },
        )

        return state

    async def get_tour_state(self, tour_id: str) -> TourState:
        """Get tour state.

        Args:
            tour_id: Tour ID

        Returns:
            Tour state

        Raises:
            NotFoundError: If tour not found
        """
        return self._get_tour_state(tour_id)

    def get_all_active_tours(self) -> list[TourState]:
        """Get all active tours.

        Returns:
            List of active tour states
        """
        return [
            state for state in self._active_tours.values()
            if state.status in (TourStatus.IN_PROGRESS, TourStatus.PAUSED)
        ]

    def get_user_active_tours(self, user_id: uuid.UUID) -> list[TourState]:
        """Get active tours for a user.

        Args:
            user_id: User ID

        Returns:
            List of active tour states
        """
        return [
            state for state in self._active_tours.values()
            if state.user_id == user_id
            and state.status in (TourStatus.IN_PROGRESS, TourStatus.PAUSED)
        ]

    def register_event_handler(
        self,
        event_type: TourEventType,
        handler: Any,
    ) -> None:
        """Register an event handler.

        Args:
            event_type: Event type to handle
            handler: Handler callback
        """
        self._event_handlers[event_type].append(handler)

    async def _get_tour_state(self, tour_id: str) -> TourState:
        """Get tour state from memory or store.

        Args:
            tour_id: Tour ID

        Returns:
            Tour state

        Raises:
            NotFoundError: If tour not found
        """
        if tour_id in self._active_tours:
            return self._active_tours[tour_id]

        # Try to load from store
        if self.state_store:
            state_data = await self.state_store.get(f"tour:{tour_id}")
            if state_data:
                state = TourState.from_dict(state_data)
                self._active_tours[tour_id] = state
                return state

        raise NotFoundError(
            resource="Tour",
            identifier=tour_id,
        )

    async def _persist_state(self, state: TourState) -> None:
        """Persist tour state to store.

        Args:
            state: Tour state to persist
        """
        if self.state_store:
            # Calculate TTL based on tour duration
            ttl_seconds = None
            if state.started_at:
                elapsed = (datetime.now(timezone.utc) - state.started_at).total_seconds()
                ttl_seconds = max(86400, 86400 - int(elapsed))  # 24 hours base

            await self.state_store.set(
                f"tour:{state.tour_id}",
                state.to_dict(),
                ttl=ttl_seconds,
            )

    async def _check_nearby_pois(
        self,
        state: TourState,
        location: dict[str, float],
    ) -> list[tuple[str, float]]:
        """Check for nearby POIs.

        Args:
            state: Tour state
            location: Current location

        Returns:
            List of (poi_id, distance_meters)
        """
        # This would integrate with route/poi services
        # For now, return empty list
        return []

    async def _calculate_distance(
        self,
        from_loc: dict[str, float],
        to_loc: dict[str, float],
    ) -> float:
        """Calculate distance between two locations.

        Args:
            from_loc: From location
            to_loc: To location

        Returns:
            Distance in meters
        """
        import math

        lat1 = math.radians(from_loc["lat"])
        lon1 = math.radians(from_loc["lng"])
        lat2 = math.radians(to_loc["lat"])
        lon2 = math.radians(to_loc["lng"])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))

        r = 6371000  # Earth radius in meters
        return r * c

    async def _estimate_remaining_time(self, state: TourState) -> int:
        """Estimate remaining tour time.

        Args:
            state: Tour state

        Returns:
            Estimated remaining minutes
        """
        # Simple estimation: 30 minutes per unvisited POI
        remaining_pois = sum(
            1 for cp in state.checkpoints.values()
            if not cp.reached_at and not cp.skipped
        )
        return remaining_pois * 30

    async def _emit_event(
        self,
        tour_id: str,
        event_type: TourEventType,
        data: dict[str, Any],
    ) -> None:
        """Emit a tour event.

        Args:
            tour_id: Tour ID
            event_type: Event type
            data: Event data
        """
        event = {
            "type": event_type.value,
            "tour_id": tour_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

        # Add to state events
        if tour_id in self._active_tours:
            self._active_tours[tour_id].events.append(event)

        # Call registered handlers
        for handler in self._event_handlers.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}")


# Global instance
orchestrator = TourOrchestrator()


def get_orchestrator() -> TourOrchestrator:
    """Get global tour orchestrator instance.

    Returns:
        Tour orchestrator instance
    """
    return orchestrator
