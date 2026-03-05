"""Pydantic schemas for guided tour operations."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class TourStartRequest(BaseModel):
    """Request schema for starting a guided tour."""

    route_id: uuid.UUID = Field(..., description="Route ID to tour")
    start_time: datetime | None = Field(None, description="Tour start time (defaults to now)")
    enable_voice_guidance: bool = Field(True, description="Enable voice commentary")
    enable_proximity_alerts: bool = Field(True, description="Enable proximity-based alerts")
    language: str = Field("en", pattern="^[a-z]{2}$", description="Tour language")


class TourStopContent(BaseModel):
    """Content for a tour stop."""

    poi_id: uuid.UUID = Field(..., description="POI ID")
    poi_name: str = Field(..., description="POI name")
    audio_content_url: str | None = Field(None, description="URL to audio commentary")
    text_content: str | None = Field(None, description="Text commentary")
    images: list[str] = Field(default_factory=list, description="Content images")
    fun_facts: list[str] = Field(default_factory=list, description="Interesting facts")
    recommendations: list[str] = Field(default_factory=list, description="Personalized recommendations")


class TourLocationUpdate(BaseModel):
    """Location update during tour."""

    tour_id: uuid.UUID = Field(..., description="Tour ID")
    latitude: Decimal = Field(..., ge=-90, le=90, description="Current latitude")
    longitude: Decimal = Field(..., ge=-180, le=180, description="Current longitude")
    accuracy: float | None = Field(None, description="GPS accuracy in meters")
    timestamp: datetime = Field(..., description="Location timestamp")


class TourProximityAlert(BaseModel):
    """Proximity alert for nearby POI."""

    poi_id: uuid.UUID = Field(..., description="POI ID")
    poi_name: str = Field(..., description="POI name")
    distance_meters: float = Field(..., description="Distance to POI")
    estimated_arrival_minutes: int | None = Field(None, description="Estimated walking time")
    content: TourStopContent | None = Field(None, description="Content for the POI")


class TourStatus(BaseModel):
    """Tour status information."""

    tour_id: uuid.UUID = Field(..., description="Tour ID")
    route_id: uuid.UUID = Field(..., description="Route ID")
    status: str = Field(..., pattern="^(active|paused|completed|cancelled)$", description="Tour status")
    current_stop_index: int | None = Field(None, description="Current stop index")
    next_stop_index: int | None = Field(None, description="Next stop index")
    current_location: tuple[float, float] | None = Field(None, description="Current location")
    started_at: datetime | None = Field(None, description="Tour start time")
    estimated_end_time: datetime | None = Field(None, description="Estimated end time")
    progress_percentage: float = Field(..., ge=0, le=100, description="Tour completion percentage")
    stops_visited: int = Field(..., description="Number of stops visited")
    stops_remaining: int = Field(..., description="Number of stops remaining")


class TourPauseRequest(BaseModel):
    """Request schema for pausing a tour."""

    reason: str | None = Field(None, description="Reason for pausing")
    save_progress: bool = Field(True, description="Whether to save progress")


class TourResumeRequest(BaseModel):
    """Request schema for resuming a tour."""

    current_location: tuple[float, float] | None = Field(None, description="Current location")
    skip_missed_stops: bool = Field(False, description="Whether to skip missed stops")


class TourContent(BaseModel):
    """Tour content for delivery."""

    stop_index: int = Field(..., description="Stop index")
    content: TourStopContent = Field(..., description="Stop content")
    nearby_amenities: list[dict[str, Any]] | None = Field(None, description="Nearby amenities")
    safety_notes: list[str] | None = Field(None, description="Safety information")
    accessibility_info: dict[str, Any] | None = Field(None, description="Accessibility information")


class TourEvent(BaseModel):
    """Tour event for WebSocket communication."""

    event_type: str = Field(..., description="Event type")
    timestamp: datetime = Field(..., description="Event timestamp")
    data: dict[str, Any] = Field(..., description="Event data")


class TourSummary(BaseModel):
    """Summary of completed tour."""

    tour_id: uuid.UUID = Field(..., description="Tour ID")
    route_id: uuid.UUID = Field(..., description="Route ID")
    started_at: datetime = Field(..., description="Start time")
    completed_at: datetime = Field(..., description="Completion time")
    total_duration_minutes: int = Field(..., description="Actual tour duration")
    stops_completed: int = Field(..., description="Stops visited")
    stops_skipped: int = Field(..., description="Stops skipped")
    total_distance_km: float = Field(..., description="Actual distance traveled")
    user_ratings: dict[uuid.UUID, int] | None = Field(None, description="User ratings for stops")
    feedback: str | None = Field(None, description="User feedback")
