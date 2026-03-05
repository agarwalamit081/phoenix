"""Itinerary and itinerary item models for travel plans."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import BaseModel

if TYPE_CHECKING:
    from src.models.poi import PointOfInterest
    from src.models.user import User


class Itinerary(BaseModel):
    """Itinerary model representing a travel plan."""

    __tablename__ = "itineraries"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(50),
        default="draft",
        nullable=False,
        index=True,
    )  # 'draft', 'confirmed', 'active', 'completed', 'cancelled'

    # Timing
    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    total_duration_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Route information
    start_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    end_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_distance_km: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    # Optimization metrics
    satisfaction_score: Mapped[float | None] = mapped_column(
        nullable=True,
    )  # Predicted user satisfaction (0.0 to 1.0)
    optimization_version: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="itineraries",
    )
    items: Mapped[list["ItineraryItem"]] = relationship(
        "ItineraryItem",
        back_populates="itinerary",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ItineraryItem.sequence_order",
    )

    def is_active(self) -> bool:
        """Check if itinerary is currently active.

        Returns:
            bool: True if itinerary status is 'active'
        """
        return self.status == "active"

    def is_completed(self) -> bool:
        """Check if itinerary is completed.

        Returns:
            bool: True if itinerary status is 'completed'
        """
        return self.status == "completed"

    def is_in_progress(self) -> bool:
        """Check if itinerary is currently in progress based on time.

        Returns:
            bool: True if current time is within start and end time
        """
        if not self.start_time or not self.end_time:
            return False
        now = datetime.now(self.start_time.tzinfo)
        return self.start_time <= now <= self.end_time

    def get_completion_percentage(self) -> float:
        """Calculate completion percentage based on visited items.

        Returns:
            float: Completion percentage (0.0 to 100.0)
        """
        if not self.items:
            return 0.0

        total = len(self.items)
        visited = sum(1 for item in self.items if item.status == "visited")
        return (visited / total) * 100.0

    def to_dict(self) -> dict:
        """Convert itinerary to dictionary.

        Returns:
            dict: Dictionary representation of the itinerary
        """
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_duration_minutes": self.total_duration_minutes,
            "start_location": self.start_location,
            "end_location": self.end_location,
            "total_distance_km": self.total_distance_km,
            "satisfaction_score": self.satisfaction_score,
            "completion_percentage": self.get_completion_percentage(),
            "item_count": len(self.items) if self.items else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ItineraryItem(BaseModel):
    """Individual item within an itinerary (POI visit)."""

    __tablename__ = "itinerary_items"

    itinerary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("itineraries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    poi_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("points_of_interest.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Sequencing
    sequence_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Time estimates
    estimated_duration_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    estimated_arrival_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    estimated_departure_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Actual times (tracked during tour)
    actual_arrival_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    actual_departure_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Navigation
    distance_from_previous_km: Mapped[float | None] = mapped_column(
        nullable=True,
    )
    travel_time_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    transport_mode: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )  # 'walking', 'driving', 'transit', 'cycling'

    # Status and notes
    status: Mapped[str] = mapped_column(
        String(50),
        default="planned",
        nullable=False,
    )  # 'planned', 'visited', 'skipped', 'modified'
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # User interaction
    user_rating: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )  # 1 to 5 stars
    user_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    itinerary: Mapped["Itinerary"] = relationship(
        "Itinerary",
        back_populates="items",
    )
    poi: Mapped["PointOfInterest | None"] = relationship(
        "PointOfInterest",
        lazy="joined",
    )

    def is_visited(self) -> bool:
        """Check if the item has been visited.

        Returns:
            bool: True if status is 'visited'
        """
        return self.status == "visited"

    def is_skipped(self) -> bool:
        """Check if the item was skipped.

        Returns:
            bool: True if status is 'skipped'
        """
        return self.status == "skipped"

    def get_actual_duration_minutes(self) -> int | None:
        """Calculate actual duration spent at this location.

        Returns:
            int | None: Duration in minutes, or None if not visited
        """
        if not self.actual_arrival_time or not self.actual_departure_time:
            return None
        delta = self.actual_departure_time - self.actual_arrival_time
        return int(delta.total_seconds() / 60)

    def to_dict(self) -> dict:
        """Convert itinerary item to dictionary.

        Returns:
            dict: Dictionary representation of the itinerary item
        """
        return {
            "id": str(self.id),
            "itinerary_id": str(self.itinerary_id),
            "poi_id": str(self.poi_id) if self.poi_id else None,
            "poi": self.poi.to_summary_dict() if self.poi else None,
            "sequence_order": self.sequence_order,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "estimated_arrival_time": (
                self.estimated_arrival_time.isoformat() if self.estimated_arrival_time else None
            ),
            "estimated_departure_time": (
                self.estimated_departure_time.isoformat() if self.estimated_departure_time else None
            ),
            "actual_arrival_time": (
                self.actual_arrival_time.isoformat() if self.actual_arrival_time else None
            ),
            "actual_departure_time": (
                self.actual_departure_time.isoformat() if self.actual_departure_time else None
            ),
            "distance_from_previous_km": self.distance_from_previous_km,
            "travel_time_minutes": self.travel_time_minutes,
            "transport_mode": self.transport_mode,
            "status": self.status,
            "notes": self.notes,
            "user_rating": self.user_rating,
            "user_feedback": self.user_feedback,
            "actual_duration_minutes": self.get_actual_duration_minutes(),
        }


class ItineraryNote(BaseModel):
    """Notes and highlights from itinerary execution."""

    __tablename__ = "itinerary_notes"

    itinerary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("itineraries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[str] = mapped_column(
        String(50),
        default="general",
        nullable=False,
    )  # 'general', 'highlight', 'issue', 'tip'
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)

    def to_dict(self) -> dict:
        """Convert note to dictionary.

        Returns:
            dict: Dictionary representation of the note
        """
        return {
            "id": str(self.id),
            "itinerary_id": str(self.itinerary_id),
            "user_id": str(self.user_id),
            "title": self.title,
            "content": self.content,
            "note_type": self.note_type,
            "location": self.location,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
