"""LangGraph workflows for Phoenix AI Travel Companion."""

from src.workflows.preference_collection import PreferenceCollectionWorkflow
from src.workflows.state import (
    PreferenceState,
    PreferenceExtractionResult,
    PreferenceValidationResult,
    POISelection,
    ProximityAlert,
    RouteConstraints,
    RoutePlanningState,
    TourContent,
    TourState,
    TourUpdate,
    WorkflowMetadata,
    create_preference_state,
    create_route_planning_state,
    create_tour_state,
)

__all__ = [
    # State
    "PreferenceState",
    "RoutePlanningState",
    "TourState",
    "WorkflowMetadata",
    "PreferenceExtractionResult",
    "PreferenceValidationResult",
    "POISelection",
    "RouteConstraints",
    "ProximityAlert",
    "TourContent",
    "TourUpdate",
    # State factories
    "create_preference_state",
    "create_route_planning_state",
    "create_tour_state",
    # Workflows
    "PreferenceCollectionWorkflow",
]
