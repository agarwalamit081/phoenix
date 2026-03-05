"""Database models for Phoenix AI Travel Companion."""

from src.models.itinerary import (
    Itinerary,
    ItineraryItem,
    ItineraryNote,
)
from src.models.poi import (
    POISearchIndex,
    PointOfInterest,
)
from src.models.preference import (
    PreferenceConflict,
    UserPreference,
)
from src.models.user import (
    PasswordReset,
    RefreshToken,
    User,
)

__all__ = [
    # User models
    "User",
    "RefreshToken",
    "PasswordReset",
    # Preference models
    "UserPreference",
    "PreferenceConflict",
    # POI models
    "PointOfInterest",
    "POISearchIndex",
    # Itinerary models
    "Itinerary",
    "ItineraryItem",
    "ItineraryNote",
]
