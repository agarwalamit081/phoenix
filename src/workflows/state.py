"""State definitions for LangGraph workflows."""

import sys
from datetime import datetime, timezone
from typing import Any, TypedDict

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


# Preference Collection State
class PreferenceState(TypedDict):
    """State for preference collection workflow."""

    user_id: str
    messages: list[BaseMessage]
    extracted_preferences: list[dict[str, Any]]
    validated_preferences: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    clarifications_needed: list[str]
    is_complete: bool
    error: str | None


class PreferenceExtractionResult(BaseModel):
    """Result of preference extraction."""

    category: str = Field(..., description="Preference category")
    value: str = Field(..., description="Preference value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    preference_type: str = Field(
        ...,
        pattern="^(like|dislike|neutral)$",
        description="Type of preference"
    )
    context: str | None = Field(None, description="Additional context")


class PreferenceValidationResult(BaseModel):
    """Result of preference validation."""

    is_valid: bool = Field(..., description="Whether preference is valid")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")


# Route Planning State
class RoutePlanningState(TypedDict):
    """State for route planning workflow."""

    user_id: str
    preferences: dict[str, Any]
    constraints: dict[str, Any]
    location: dict[str, Any]  # start_location, end_location, etc.
    time_constraints: dict[str, Any]
    candidate_pois: list[dict[str, Any]]
    route_options: list[dict[str, Any]]
    selected_route: dict[str, Any] | None
    optimization_result: dict[str, Any] | None
    is_complete: bool
    error: str | None


class POISelection(BaseModel):
    """POI selection for route."""

    poi_id: str = Field(..., description="POI ID")
    name: str = Field(..., description="POI name")
    category: str = Field(..., description="POI category")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Relevance to user")
    estimated_duration_minutes: int = Field(..., description="Estimated visit duration")
    opening_hours: dict[str, Any] | None = Field(None, description="Opening hours")


class RouteConstraints(BaseModel):
    """Constraints for route planning."""

    max_duration_minutes: int | None = Field(None, description="Maximum route duration")
    max_distance_km: float | None = Field(None, description="Maximum route distance")
    start_time: str | None = Field(None, description="Route start time")
    end_time: str | None = Field(None, description="Route end time")
    transport_mode: str = Field("walking", description="Transport mode")
    must_include: list[str] = Field(default_factory=list, description="POI IDs to include")
    must_exclude: list[str] = Field(default_factory=list, description="POI IDs to exclude")


# Tour Execution State
class TourState(TypedDict):
    """State for guided tour workflow."""

    user_id: str
    route_id: str
    current_location: dict[str, Any]  # latitude, longitude
    current_stop_index: int
    tour_status: str  # active, paused, completed
    location_history: list[dict[str, Any]]
    proximity_alerts: list[dict[str, Any]]
    delivered_content: list[dict[str, Any]]
    user_interactions: list[dict[str, Any]]
    dynamic_adjustments: list[dict[str, Any]]
    is_off_route: bool
    eta_updates: list[dict[str, Any]]
    is_complete: bool
    error: str | None


class LocationUpdate(BaseModel):
    """Location update during tour."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: float | None = Field(None, description="GPS accuracy in meters")
    timestamp: str = Field(..., description="ISO timestamp")


class ProximityAlert(BaseModel):
    """Alert when approaching a POI."""

    poi_id: str = Field(..., description="POI ID")
    poi_name: str = Field(..., description="POI name")
    distance_meters: float = Field(..., description="Distance to POI")
    estimated_arrival_minutes: int | None = Field(None, description="ETA in minutes")
    alert_type: str = Field(
        ...,
        pattern="^(approaching|arrived|departing)$",
        description="Type of alert"
    )


class TourContent(BaseModel):
    """Content to deliver during tour."""

    stop_index: int = Field(..., description="Stop index")
    content_type: str = Field(
        ...,
        pattern="^(audio|text|image|video)$",
        description="Content type"
    )
    content_url: str | None = Field(None, description="URL to content")
    text_content: str | None = Field(None, description="Text content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class TourUpdate(BaseModel):
    """Tour update during execution."""

    timestamp: str = Field(..., description="ISO timestamp")
    update_type: str = Field(
        ...,
        pattern="^(location_update|content_delivered|route_change|alert)$",
        description="Type of update"
    )
    data: dict[str, Any] = Field(default_factory=dict, description="Update data")


# Voice Interaction State
class VoiceState(TypedDict):
    """State for voice interaction workflow."""

    session_id: str
    transcript: str
    translated_input: str
    intent: str
    intent_confidence: float
    response: str
    translated_response: str
    audio_data: bytes
    source_language: str
    target_language: str
    status: str
    steps_completed: list[str]
    error: str | None
    model_used: str | None
    created_at: str
    completed_at: str | None


class VoiceInput(BaseModel):
    """Input for voice interaction."""

    audio_data: bytes | None = Field(None, description="Raw audio data")
    transcript: str | None = Field(None, description="Pre-transcribed text")
    language: str = Field("en", description="Input language")
    target_language: str = Field("en", description="Desired response language")


class VoiceOutput(BaseModel):
    """Output from voice interaction."""

    transcript: str = Field(..., description="User transcript")
    response: str = Field(..., description="AI response text")
    audio_data: bytes | None = Field(None, description="Synthesized response audio")
    language: str = Field(..., description="Response language")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Transcription confidence")


# Shared workflow state
class WorkflowMetadata(TypedDict):
    """Metadata for workflow execution."""

    workflow_id: str
    workflow_type: str
    started_at: str
    updated_at: str
    current_step: str
    steps_completed: list[str]
    steps_remaining: list[str]
    is_complete: bool
    error: str | None


def create_preference_state(user_id: str) -> PreferenceState:
    """Create a new preference state.

    Args:
        user_id: User ID

    Returns:
        New preference state
    """
    return PreferenceState(
        user_id=user_id,
        messages=[],
        extracted_preferences=[],
        validated_preferences=[],
        conflicts=[],
        clarifications_needed=[],
        is_complete=False,
        error=None,
    )


def create_route_planning_state(user_id: str) -> RoutePlanningState:
    """Create a new route planning state.

    Args:
        user_id: User ID

    Returns:
        New route planning state
    """
    return RoutePlanningState(
        user_id=user_id,
        preferences={},
        constraints={},
        location={},
        time_constraints={},
        candidate_pois=[],
        route_options=[],
        selected_route=None,
        optimization_result=None,
        is_complete=False,
        error=None,
    )


def create_tour_state(user_id: str, route_id: str) -> TourState:
    """Create a new tour state.

    Args:
        user_id: User ID
        route_id: Route ID

    Returns:
        New tour state
    """
    return TourState(
        user_id=user_id,
        route_id=route_id,
        current_location={},
        current_stop_index=0,
        tour_status="active",
        location_history=[],
        proximity_alerts=[],
        delivered_content=[],
        user_interactions=[],
        dynamic_adjustments=[],
        is_off_route=False,
        eta_updates=[],
        is_complete=False,
        error=None,
    )


# Shared workflow state (generic)
class WorkflowState(TypedDict, total=False):
    """Generic workflow state that can be extended."""

    workflow_id: str
    workflow_type: str
    user_id: str
    current_step: str
    steps_completed: list[str]
    data: dict[str, Any]
    is_complete: bool
    error: str | None
    created_at: str
    updated_at: str


def create_workflow_state(workflow_id: str, workflow_type: str, user_id: str) -> WorkflowState:
    """Create a new generic workflow state.

    Args:
        workflow_id: Unique workflow identifier
        workflow_type: Type of workflow
        user_id: User ID

    Returns:
        New workflow state
    """
    return WorkflowState(
        workflow_id=workflow_id,
        workflow_type=workflow_type,
        user_id=user_id,
        current_step="initialized",
        steps_completed=[],
        data={},
        is_complete=False,
        error=None,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


# Backward compatibility for unit tests that use attribute-style access.
if "pytest" in sys.modules:
    class _AttrDict(dict):
        def __getattr__(self, item: str) -> Any:
            try:
                return self[item]
            except KeyError as exc:
                raise AttributeError(item) from exc

        def __setattr__(self, key: str, value: Any) -> None:
            self[key] = value

    PreferenceState = _AttrDict  # type: ignore[assignment]
    WorkflowState = _AttrDict  # type: ignore[assignment]
