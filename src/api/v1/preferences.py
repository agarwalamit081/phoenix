"""Preferences API endpoints."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DBSession
from src.schemas.preference import (
    PreferenceBulkCreateRequest,
    PreferenceConflictResponse,
    PreferenceCreateRequest,
    PreferenceListResponse,
    PreferenceResponse,
    PreferenceUpdateRequest,
    UserProfileSummary,
)
from src.services.preference_service import PreferenceService

router = APIRouter()


@router.get("/", response_model=PreferenceListResponse)
async def get_preferences(
    user: CurrentUser,
    session: DBSession,
    preference_type: str | None = Query(None, description="Filter by preference type"),
    category: str | None = Query(None, description="Filter by category"),
) -> PreferenceListResponse:
    """Get user preferences.

    Args:
        user: Current user
        session: Database session
        preference_type: Optional preference type filter
        category: Optional category filter

    Returns:
        List of user preferences
    """
    pref_service = PreferenceService(session)
    preferences = await pref_service.get_preferences(
        user.id,
        preference_type=preference_type,
        category=category,
    )

    # Get all categories
    all_preferences = await pref_service.get_preferences(user.id)
    categories = list(set(p.category for p in all_preferences))

    return PreferenceListResponse(
        preferences=preferences,
        total=len(preferences),
        categories=categories,
    )


@router.post("/", response_model=PreferenceResponse, status_code=201)
async def create_preference(
    data: PreferenceCreateRequest,
    user: CurrentUser,
    session: DBSession,
) -> PreferenceResponse:
    """Create a new preference.

    Args:
        data: Preference creation data
        user: Current user
        session: Database session

    Returns:
        Created preference
    """
    pref_service = PreferenceService(session)
    return await pref_service.create_preference(user.id, data)


@router.post("/bulk", response_model=list[PreferenceResponse], status_code=201)
async def bulk_create_preferences(
    data: PreferenceBulkCreateRequest,
    user: CurrentUser,
    session: DBSession,
) -> list[PreferenceResponse]:
    """Create multiple preferences at once.

    Args:
        data: Bulk preference creation data
        user: Current user
        session: Database session

    Returns:
        List of created preferences
    """
    pref_service = PreferenceService(session)
    preferences_data = [p.model_dump() for p in data.preferences]
    return await pref_service.bulk_create_preferences(user.id, preferences_data)


@router.get("/{preference_id}", response_model=PreferenceResponse)
async def get_preference(
    preference_id: uuid.UUID,
    user: CurrentUser,
    session: DBSession,
) -> PreferenceResponse:
    """Get a specific preference.

    Args:
        preference_id: Preference ID
        user: Current user
        session: Database session

    Returns:
        Preference details

    Raises:
        NotFoundError: If preference not found
    """
    pref_service = PreferenceService(session)
    preferences = await pref_service.get_preferences(user.id)

    for pref in preferences:
        if pref.id == preference_id:
            return pref

    from src.core.exceptions import NotFoundError

    raise NotFoundError("Preference", str(preference_id))


@router.patch("/{preference_id}", response_model=PreferenceResponse)
async def update_preference(
    preference_id: uuid.UUID,
    data: PreferenceUpdateRequest,
    user: CurrentUser,
    session: DBSession,
) -> PreferenceResponse:
    """Update a preference.

    Args:
        preference_id: Preference ID
        data: Update data
        user: Current user
        session: Database session

    Returns:
        Updated preference

    Raises:
        NotFoundError: If preference not found
    """
    pref_service = PreferenceService(session)
    update_data = data.model_dump(exclude_unset=True)
    return await pref_service.update_preference(user.id, preference_id, update_data)


@router.delete("/{preference_id}")
async def delete_preference(
    preference_id: uuid.UUID,
    user: CurrentUser,
    session: DBSession,
) -> dict[str, str]:
    """Delete a preference.

    Args:
        preference_id: Preference ID
        user: Current user
        session: Database session

    Returns:
        Deletion confirmation

    Raises:
        NotFoundError: If preference not found
    """
    pref_service = PreferenceService(session)
    deleted = await pref_service.delete_preference(user.id, preference_id)

    if not deleted:
        from src.core.exceptions import NotFoundError

        raise NotFoundError("Preference", str(preference_id))

    return {"message": "Preference deleted"}


@router.get("/summary/profile", response_model=UserProfileSummary)
async def get_profile_summary(
    user: CurrentUser,
    session: DBSession,
) -> UserProfileSummary:
    """Get user preference profile summary.

    Args:
        user: Current user
        session: Database session

    Returns:
        User profile summary
    """
    pref_service = PreferenceService(session)
    return await pref_service.get_profile_summary(user.id)


@router.get("/conflicts", response_model=list[PreferenceConflictResponse])
async def get_conflicts(
    user: CurrentUser,
    session: DBSession,
    unresolved_only: bool = Query(True, description="Only show unresolved conflicts"),
) -> list[PreferenceConflictResponse]:
    """Get preference conflicts.

    Args:
        user: Current user
        session: Database session
        unresolved_only: Only return unresolved conflicts

    Returns:
        List of preference conflicts
    """
    pref_service = PreferenceService(session)
    conflicts = await pref_service.get_conflicts(user.id, unresolved_only=unresolved_only)
    return [PreferenceConflictResponse(**c) for c in conflicts]


@router.post("/extract")
async def extract_from_text(
    user: CurrentUser,
    session: DBSession,
    text: str = Query(..., description="Text to extract preferences from"),
) -> dict[str, Any]:
    """Extract preferences from text.

    Args:
        text: Text to analyze
        user: Current user
        session: Database session

    Returns:
        Extracted preferences
    """
    pref_service = PreferenceService(session)
    preferences = await pref_service.extract_from_text(user.id, text)

    return {
        "preferences": [
            {
                "category": p.category,
                "value": p.value,
                "confidence": p.confidence_score,
                "preference_type": p.preference_type,
            }
            for p in preferences
        ],
        "count": len(preferences),
    }


@router.delete("/expired")
async def cleanup_expired(
    user: CurrentUser,
    session: DBSession,
) -> dict[str, Any]:
    """Clean up expired temporary preferences.

    Args:
        user: Current user
        session: Database session

    Returns:
        Cleanup result
    """
    pref_service = PreferenceService(session)
    count = await pref_service.cleanup_expired_preferences(user.id)

    return {
        "message": f"Cleaned up {count} expired preferences",
        "deleted_count": count,
    }
