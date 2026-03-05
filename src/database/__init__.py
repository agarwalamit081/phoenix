"""Database connection and repositories for Phoenix AI Travel Companion."""

from src.database.base import Base, BaseModel
from src.database.connection import (
    DatabaseSessionManager,
    check_database_health,
    close_database,
    get_engine,
    get_session,
    get_session_maker,
    get_test_session,
    init_database,
    reset_engine,
)
from src.database.repositories import BaseRepository
from src.database.repositories.itinerary import (
    ItineraryItemRepository,
    ItineraryNoteRepository,
    ItineraryRepository,
)
from src.database.repositories.poi import POIRepository
from src.database.repositories.preference import (
    PreferenceConflictRepository,
    UserPreferenceRepository,
)
from src.database.repositories.user import (
    RefreshTokenRepository,
    UserRepository,
)

__all__ = [
    # Base
    "Base",
    "BaseModel",
    # Connection
    "init_database",
    "close_database",
    "get_session",
    "get_session_maker",
    "get_engine",
    "get_test_session",
    "reset_engine",
    "check_database_health",
    "DatabaseSessionManager",
    # Base repository
    "BaseRepository",
    # User repositories
    "UserRepository",
    "RefreshTokenRepository",
    # Preference repositories
    "UserPreferenceRepository",
    "PreferenceConflictRepository",
    # POI repositories
    "POIRepository",
    # Itinerary repositories
    "ItineraryRepository",
    "ItineraryItemRepository",
    "ItineraryNoteRepository",
]
