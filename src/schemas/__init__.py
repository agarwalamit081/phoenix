"""Pydantic schemas for Phoenix AI Travel Companion."""

# User schemas
from src.schemas.user import (
    ErrorResponse,
    OAuthLoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    TokenRefreshRequest,
    TokenResponse,
    UserProfileResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserUpdateRequest,
)

# Chat schemas
from src.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ConversationHistory,
    ConversationListResponse,
    PreferenceExtraction,
    StreamingChunk,
)

# Preference schemas
from src.schemas.preference import (
    PreferenceBulkCreateRequest,
    PreferenceConflictResponse,
    PreferenceCreateRequest,
    PreferenceListResponse,
    PreferenceResponse,
    PreferenceUpdateRequest,
    UserProfileSummary,
)

# Route schemas
from src.schemas.route import (
    Location,
    POIBrief,
    RouteAnalytics,
    RouteGenerateRequest,
    RouteListResponse,
    RouteModifyRequest,
    RouteOptimizationRequest,
    RouteResponse,
    RouteStop,
)

# Tour schemas
from src.schemas.tour import (
    TourContent,
    TourEvent,
    TourLocationUpdate,
    TourPauseRequest,
    TourProximityAlert,
    TourResumeRequest,
    TourStartRequest,
    TourStatus,
    TourStopContent,
    TourSummary,
)

__all__ = [
    # User
    "UserRegisterRequest",
    "UserLoginRequest",
    "OAuthLoginRequest",
    "TokenResponse",
    "TokenRefreshRequest",
    "UserProfileResponse",
    "UserUpdateRequest",
    "PasswordChangeRequest",
    "PasswordResetRequest",
    "PasswordResetConfirmRequest",
    "ErrorResponse",
    # Chat
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ConversationHistory",
    "ConversationListResponse",
    "StreamingChunk",
    "PreferenceExtraction",
    # Preference
    "PreferenceCreateRequest",
    "PreferenceUpdateRequest",
    "PreferenceBulkCreateRequest",
    "PreferenceResponse",
    "PreferenceListResponse",
    "PreferenceConflictResponse",
    "UserProfileSummary",
    # Route
    "Location",
    "POIBrief",
    "RouteGenerateRequest",
    "RouteResponse",
    "RouteModifyRequest",
    "RouteOptimizationRequest",
    "RouteListResponse",
    "RouteAnalytics",
    # Tour
    "TourStartRequest",
    "TourStatus",
    "TourLocationUpdate",
    "TourProximityAlert",
    "TourPauseRequest",
    "TourResumeRequest",
    "TourStopContent",
    "TourContent",
    "TourEvent",
    "TourSummary",
]
