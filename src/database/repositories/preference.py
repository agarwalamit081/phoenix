"""Preference repository for database operations."""

import uuid
from typing import Any

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.logging import logger
from src.database.repositories import BaseRepository
from src.models.preference import PreferenceConflict, UserPreference


class UserPreferenceRepository(BaseRepository[UserPreference]):
    """Repository for UserPreference model operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the user preference repository.

        Args:
            session: The database session
        """
        super().__init__(session, UserPreference)

    async def get_user_preferences(
        self,
        user_id: uuid.UUID,
        preference_type: str | None = None,
        category: str | None = None,
    ) -> list[UserPreference]:
        """Get preferences for a user, optionally filtered by type and category.

        Args:
            user_id: The user ID
            preference_type: Optional preference type filter
            category: Optional category filter

        Returns:
            List of user preferences
        """
        stmt = select(UserPreference).where(UserPreference.user_id == user_id)

        filters: list[Any] = []
        if preference_type:
            filters.append(UserPreference.preference_type == preference_type)
        if category:
            filters.append(UserPreference.category == category)
        if filters:
            stmt = stmt.where(and_(*filters))

        stmt = stmt.order_by(UserPreference.confidence_score.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_preferences(
        self,
        user_id: uuid.UUID,
    ) -> list[UserPreference]:
        """Get all non-expired preferences for a user.

        Args:
            user_id: The user ID

        Returns:
            List of active preferences
        """
        stmt = select(UserPreference).where(
            UserPreference.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        all_prefs = list(result.scalars().all())
        return [p for p in all_prefs if not p.is_expired()]

    async def get_strong_preferences(
        self,
        user_id: uuid.UUID,
        min_confidence: float = 0.7,
    ) -> list[UserPreference]:
        """Get strong preferences (high confidence) for a user.

        Args:
            user_id: The user ID
            min_confidence: Minimum confidence score

        Returns:
            List of strong preferences
        """
        stmt = select(UserPreference).where(
            UserPreference.user_id == user_id,
            UserPreference.confidence_score >= min_confidence,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_preferences_by_category(
        self,
        user_id: uuid.UUID,
        category: str,
    ) -> list[UserPreference]:
        """Get preferences for a user in a specific category.

        Args:
            user_id: The user ID
            category: The preference category

        Returns:
            List of preferences in the category
        """
        stmt = select(UserPreference).where(
            UserPreference.user_id == user_id,
            UserPreference.category == category,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_likes(self, user_id: uuid.UUID) -> list[UserPreference]:
        """Get all likes for a user.

        Args:
            user_id: The user ID

        Returns:
            List of liked preferences
        """
        return await self.get_user_preferences(user_id, preference_type="like")

    async def get_dislikes(self, user_id: uuid.UUID) -> list[UserPreference]:
        """Get all dislikes for a user.

        Args:
            user_id: The user ID

        Returns:
            List of disliked preferences
        """
        return await self.get_user_preferences(user_id, preference_type="dislike")

    async def delete_user_preferences(
        self,
        user_id: uuid.UUID,
        category: str | None = None,
    ) -> int:
        """Delete preferences for a user, optionally by category.

        Args:
            user_id: The user ID
            category: Optional category filter

        Returns:
            Number of preferences deleted
        """
        stmt = delete(UserPreference).where(UserPreference.user_id == user_id)
        if category:
            stmt = stmt.where(UserPreference.category == category)
        result = await self.session.execute(stmt)
        count = result.rowcount
        logger.info(f"Deleted {count} preferences for user {user_id}")
        return count

    async def cleanup_expired_preferences(self, user_id: uuid.UUID) -> int:
        """Delete expired preferences for a user.

        Args:
            user_id: The user ID

        Returns:
            Number of preferences deleted
        """
        stmt = select(UserPreference).where(UserPreference.user_id == user_id)
        result = await self.session.execute(stmt)
        all_prefs = result.scalars().all()
        expired = [p for p in all_prefs if p.is_expired()]
        count = 0
        for pref in expired:
            await self.session.delete(pref)
            count += 1
        if count > 0:
            logger.info(f"Cleaned up {count} expired preferences for user {user_id}")
        return count

    async def bulk_create_preferences(
        self,
        user_id: uuid.UUID,
        preferences: list[dict[str, Any]],
    ) -> list[UserPreference]:
        """Create multiple preferences for a user.

        Args:
            user_id: The user ID
            preferences: List of preference dictionaries

        Returns:
            List of created preferences
        """
        for pref in preferences:
            pref["user_id"] = user_id
        return await self.bulk_create(preferences)


class PreferenceConflictRepository(BaseRepository[PreferenceConflict]):
    """Repository for PreferenceConflict model operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the preference conflict repository.

        Args:
            session: The database session
        """
        super().__init__(session, PreferenceConflict)

    async def get_user_conflicts(
        self,
        user_id: uuid.UUID,
        unresolved_only: bool = False,
    ) -> list[PreferenceConflict]:
        """Get conflicts for a user.

        Args:
            user_id: The user ID
            unresolved_only: Only return unresolved conflicts

        Returns:
            List of preference conflicts
        """
        stmt = select(PreferenceConflict).where(
            PreferenceConflict.user_id == user_id,
        )
        if unresolved_only:
            stmt = stmt.where(PreferenceConflict.resolved == False)
        stmt = stmt.order_by(
            PreferenceConflict.created_at.desc(),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_high_severity_conflicts(
        self,
        user_id: uuid.UUID,
    ) -> list[PreferenceConflict]:
        """Get high severity conflicts for a user.

        Args:
            user_id: The user ID

        Returns:
            List of high severity conflicts
        """
        stmt = select(PreferenceConflict).where(
            PreferenceConflict.user_id == user_id,
            PreferenceConflict.severity == "high",
            PreferenceConflict.resolved == False,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_resolved(
        self,
        conflict_id: uuid.UUID,
        resolution: str,
    ) -> PreferenceConflict | None:
        """Mark a conflict as resolved.

        Args:
            conflict_id: The conflict ID
            resolution: Resolution description

        Returns:
            The updated conflict if found, None otherwise
        """
        conflict = await self.get_by_id(conflict_id)
        if conflict:
            conflict.resolved = True
            conflict.resolution = resolution
            logger.info(f"Resolved conflict {conflict_id}")
        return conflict
