"""Preference service for managing user travel preferences."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.logging import logger
from src.core.exceptions import NotFoundError, ValidationError
from src.database.repositories.preference import (
    PreferenceConflictRepository,
    UserPreferenceRepository,
)
from src.models.preference import UserPreference
from src.schemas.preference import (
    PreferenceCreateRequest,
    PreferenceResponse,
    UserProfileSummary,
)
from src.services.embedding_service import EmbeddingService
from src.services.llm_service import LLMService


class PreferenceService:
    """Service for managing user travel preferences."""

    def __init__(self, session: AsyncSession | Any, llm_service: LLMService | None = None) -> None:
        """Initialize the preference service.

        Args:
            session: Database session or legacy repository mock
            llm_service: Optional llm service (legacy compatibility)
        """
        self._legacy_mode = not isinstance(session, AsyncSession)

        if self._legacy_mode:
            self.session = None
            self.preference_repo = session
            self.conflict_repo = None
            self.llm_service = llm_service or LLMService()
            self.embedding_service = None
        else:
            self.session = session
            self.preference_repo = UserPreferenceRepository(session)
            self.conflict_repo = PreferenceConflictRepository(session)
            self.llm_service = llm_service or LLMService()
            self.embedding_service = EmbeddingService(session)

    async def create_preference(
        self,
        user_id: uuid.UUID,
        data: PreferenceCreateRequest,
        source: str = "explicit",
    ) -> PreferenceResponse:
        """Create a new user preference.

        Args:
            user_id: User ID
            data: Preference data
            source: Preference source

        Returns:
            Created preference

        Raises:
            ValidationError: If validation fails
        """
        preference_data = data.model_dump()
        preference_data["user_id"] = user_id
        preference_data["source"] = source
        if "confidence" in preference_data:
            preference_data["confidence_score"] = preference_data.pop("confidence")

        if self._legacy_mode:
            preference = await self.preference_repo.create(preference_data)
        else:
            # Generate embedding for the preference
            embedding = await self.embedding_service.embed_user_preference(
                data.category,
                data.value,
                data.preference_type,
            )
            preference_data["embedding"] = embedding
            preference = await self.preference_repo.create(preference_data)

        # Check for conflicts
        if not self._legacy_mode:
            await self._check_and_create_conflicts(user_id, preference)

        logger.info(f"Created preference {preference.id} for user {user_id}")
        return PreferenceResponse.model_validate(preference)

    async def get_preferences(
        self,
        user_id: uuid.UUID,
        preference_type: str | None = None,
        category: str | None = None,
    ) -> list[PreferenceResponse]:
        """Get user preferences.

        Args:
            user_id: User ID
            preference_type: Optional preference type filter
            category: Optional category filter

        Returns:
            List of preferences
        """
        preferences = await self.preference_repo.get_user_preferences(
            user_id,
            preference_type=preference_type,
            category=category,
        )

        return [PreferenceResponse.model_validate(p) for p in preferences]

    async def get_user_preferences(self, user_id: uuid.UUID) -> list[PreferenceResponse]:
        """Backward-compatible alias for fetching all user preferences."""
        if self._legacy_mode and hasattr(self.preference_repo, "find_by_user"):
            return await self.preference_repo.find_by_user(user_id)
        return await self.get_preferences(user_id)

    async def get_preferences_by_category(
        self,
        user_id: uuid.UUID,
        category: str,
    ) -> list[PreferenceResponse]:
        """Backward-compatible category filter helper."""
        if self._legacy_mode and hasattr(self.preference_repo, "find_by_category"):
            return await self.preference_repo.find_by_category(user_id, category)
        return await self.get_preferences(user_id, category=category)

    async def get_profile_summary(
        self,
        user_id: uuid.UUID,
    ) -> UserProfileSummary:
        """Get a summary of user's preference profile.

        Args:
            user_id: User ID

        Returns:
            User profile summary
        """
        if self._legacy_mode and hasattr(self.preference_repo, "find_by_user"):
            preferences = await self.preference_repo.find_by_user(user_id)
        else:
            # Get all active preferences
            preferences = await self.preference_repo.get_active_preferences(user_id)

        # Count by type
        total = len(preferences)
        strong_prefs = len([p for p in preferences if p.is_strong_preference()])

        # Group by category
        categories: dict[str, int] = {}
        for pref in preferences:
            categories[pref.category] = categories.get(pref.category, 0) + 1

        # Top interests (high confidence likes)
        likes = [p for p in preferences if p.preference_type == "like"]
        top_interests = [
            {"category": p.category, "value": p.value, "confidence": p.confidence_score}
            for p in sorted(likes, key=lambda x: x.confidence_score, reverse=True)[:5]
        ]

        # Key dislikes
        dislikes = [p for p in preferences if p.preference_type == "dislike"]
        dislike_list = [f"{p.category}: {p.value}" for p in dislikes[:5]]

        # Unresolved conflicts
        conflicts = []
        if not self._legacy_mode:
            conflicts = await self.conflict_repo.get_user_conflicts(user_id, unresolved_only=True)
        summary = {
            "total_preferences": total,
            "strong_preferences": strong_prefs,
            "categories": categories,
            "top_interests": top_interests,
            "dislikes": dislike_list,
            "unresolved_conflicts": len(conflicts),
        }
        if self._legacy_mode:
            return summary  # type: ignore[return-value]
        return UserProfileSummary(**summary)

    async def update_preference(
        self,
        user_id: uuid.UUID,
        preference_id: uuid.UUID,
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> PreferenceResponse:
        """Update a preference.

        Args:
            user_id: User ID
            preference_id: Preference ID
            data: Fields to update

        Returns:
            Updated preference

        Raises:
            NotFoundError: If preference not found
        """
        if self._legacy_mode and hasattr(self.preference_repo, "find_by_id"):
            preference = await self.preference_repo.find_by_id(preference_id)
        else:
            preference = await self.preference_repo.get_by_id(preference_id)
        if not preference or preference.user_id != user_id:
            raise NotFoundError("Preference", str(preference_id))

        # Update fields
        raw_data = data.copy() if data else {}
        raw_data.update(kwargs)
        if "confidence" in raw_data:
            raw_data["confidence_score"] = raw_data.pop("confidence")
        update_data = {k: v for k, v in raw_data.items() if v is not None}
        if update_data:
            if self._legacy_mode and hasattr(self.preference_repo, "update"):
                preference = await self.preference_repo.update(preference_id, update_data)
            else:
                for key, value in update_data.items():
                    if hasattr(preference, key):
                        setattr(preference, key, value)

        # Regenerate embedding if value changed
        if "value" in update_data:
            if not self._legacy_mode:
                preference.embedding = await self.embedding_service.embed_user_preference(
                    preference.category,
                    preference.value,
                    preference.preference_type,
                )

        logger.info(f"Updated preference {preference_id}")
        if self._legacy_mode:
            return preference  # type: ignore[return-value]
        return PreferenceResponse.model_validate(preference)

    async def delete_preference(
        self,
        user_id: uuid.UUID,
        preference_id: uuid.UUID,
    ) -> bool:
        """Delete a preference.

        Args:
            user_id: User ID
            preference_id: Preference ID

        Returns:
            True if deleted, False otherwise

        Raises:
            NotFoundError: If preference not found
        """
        if self._legacy_mode and hasattr(self.preference_repo, "find_by_id"):
            preference = await self.preference_repo.find_by_id(preference_id)
        else:
            preference = await self.preference_repo.get_by_id(preference_id)
        if not preference or preference.user_id != user_id:
            raise NotFoundError("Preference", str(preference_id))

        deleted = await self.preference_repo.delete(preference_id)
        if deleted:
            logger.info(f"Deleted preference {preference_id} for user {user_id}")
        return deleted

    async def extract_preferences(self, text: str) -> list[dict[str, Any]]:
        """Backward-compatible extraction helper for unit tests."""
        entities = await self.llm_service.extract_entities(text)
        prefs = []
        for entity in entities:
            prefs.append(
                {
                    "category": str(entity.get("type", "")).lower(),
                    "value": entity.get("text", ""),
                    "confidence": entity.get("confidence", 0.0),
                    "preference_type": "like",
                }
            )
        return prefs

    async def detect_conflicts(self, user_id: uuid.UUID) -> list[dict[str, Any]]:
        """Detect basic preference conflicts (legacy helper)."""
        preferences = await self.get_user_preferences(user_id)
        conflicts = []
        for i, pref1 in enumerate(preferences):
            for pref2 in preferences[i + 1 :]:
                if (
                    pref1.category == pref2.category
                    and pref1.value.lower() == pref2.value.lower()
                    and pref1.preference_type != pref2.preference_type
                ):
                    conflicts.append(
                        {
                            "category": pref1.category,
                            "value": pref1.value,
                            "preference_id_1": str(pref1.id),
                            "preference_id_2": str(pref2.id),
                        }
                    )
        return conflicts

    async def merge_preferences(self, new_preference: Any, existing_pref_id: uuid.UUID) -> Any:
        """Merge two similar preferences (legacy helper)."""
        if self._legacy_mode and hasattr(self.preference_repo, "find_by_id"):
            existing = await self.preference_repo.find_by_id(existing_pref_id)
        else:
            existing = await self.preference_repo.get_by_id(existing_pref_id)

        if not existing:
            raise NotFoundError("Preference", str(existing_pref_id))

        merged_confidence = max(existing.confidence_score, new_preference.confidence_score)
        update_data = {"confidence_score": merged_confidence}

        if self._legacy_mode and hasattr(self.preference_repo, "update"):
            return await self.preference_repo.update(existing_pref_id, update_data)

        for key, value in update_data.items():
            setattr(existing, key, value)
        return existing

    async def decay_old_preferences(self, user_id: uuid.UUID, days: int = 90) -> int:
        """Decay confidence of old preferences (legacy helper)."""
        preferences = await self.get_user_preferences(user_id)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        updated = 0

        for pref in preferences:
            created_at = pref.created_at
            if created_at and created_at < cutoff:
                new_confidence = max(0.1, pref.confidence_score * 0.9)
                if self._legacy_mode and hasattr(self.preference_repo, "update"):
                    await self.preference_repo.update(pref.id, {"confidence_score": new_confidence})
                else:
                    pref.confidence_score = new_confidence
                updated += 1

        return updated

    async def bulk_create_preferences(
        self,
        user_id: uuid.UUID,
        preferences_data: list[dict[str, Any]],
    ) -> list[PreferenceResponse]:
        """Create multiple preferences at once.

        Args:
            user_id: User ID
            preferences_data: List of preference data

        Returns:
            List of created preferences
        """
        preferences = []
        for pref_data in preferences_data:
            pref = await self.create_preference(
                user_id,
                PreferenceCreateRequest(**pref_data),
            )
            preferences.append(pref)

        logger.info(f"Bulk created {len(preferences)} preferences for user {user_id}")
        return preferences

    async def extract_from_text(
        self,
        user_id: uuid.UUID,
        text: str,
    ) -> list[UserPreference]:
        """Extract preferences from user text using LLM.

        Args:
            user_id: User ID
            text: Text to extract preferences from

        Returns:
            List of extracted preferences
        """
        # Define preference categories
        categories = [
            "cuisine",
            "activity",
            "art_style",
            "transport",
            "accommodation",
            "atmosphere",
            "budget",
            "pace",
        ]

        # Use LLM to extract entities
        entities = await self.llm_service.extract_entities(text, categories)

        preferences = []
        for entity in entities:
            try:
                # Determine preference type from context
                pref_type = self._infer_preference_type(text, entity["value"])

                pref_data = {
                    "category": entity["type"],
                    "value": entity["value"],
                    "preference_type": pref_type,
                    "confidence": entity.get("confidence", 0.7),
                }

                # Check if similar preference exists
                existing = await self._find_similar_preference(user_id, pref_data)
                if existing:
                    # Update confidence if higher
                    if pref_data["confidence"] > existing.confidence_score:
                        existing.confidence_score = pref_data["confidence"]
                        preferences.append(existing)
                else:
                    # Create new preference
                    pref = await self.create_preference(
                        user_id,
                        PreferenceCreateRequest(**pref_data),
                        source="inferred",
                    )
                    preferences.append(pref)

            except Exception as e:
                logger.warning(f"Failed to process extracted entity {entity}: {e}")
                continue

        return preferences

    def _infer_preference_type(self, text: str, value: str) -> str:
        """Infer preference type (like/dislike/neutral) from context.

        Args:
            text: Full text
            value: Extracted value

        Returns:
            Preference type
        """
        text_lower = text.lower()
        value_lower = value.lower()

        # Keywords indicating likes
        like_keywords = ["love", "like", "enjoy", "prefer", "favorite", "fan of"]
        # Keywords indicating dislikes
        dislike_keywords = ["hate", "dislike", "don't like", "avoid", "can't stand", "not a fan"]

        # Check surrounding context
        for keyword in like_keywords:
            if keyword in text_lower:
                return "like"

        for keyword in dislike_keywords:
            if keyword in text_lower:
                return "dislike"

        # Default to neutral
        return "neutral"

    async def _find_similar_preference(
        self,
        user_id: uuid.UUID,
        pref_data: dict[str, Any],
    ) -> UserPreference | None:
        """Find similar existing preference.

        Args:
            user_id: User ID
            pref_data: Preference data to match

        Returns:
            Similar preference if found, None otherwise
        """
        existing = await self.preference_repo.get_user_preferences(
            user_id,
            category=pref_data["category"],
        )

        for pref in existing:
            if pref.value.lower() == pref_data["value"].lower():
                return pref

        return None

    async def _check_and_create_conflicts(
        self,
        user_id: uuid.UUID,
        new_preference: UserPreference,
    ) -> None:
        """Check for preference conflicts and create conflict records.

        Args:
            user_id: User ID
            new_preference: Newly created preference
        """
        # Get existing preferences
        existing = await self.preference_repo.get_user_preferences(user_id)

        # Known conflict rules
        conflict_rules = {
            # Category conflicts
            ("cuisine", "cuisine"): "Similar cuisine preferences",
            # Atmosphere conflicts
            ("atmosphere", "atmosphere"): "Conflicting atmosphere preferences",
        }

        for existing_pref in existing:
            # Skip if same type
            if existing_pref.preference_type == new_preference.preference_type:
                continue

            # Check conflict rules
            rule_key = (new_preference.category, existing_pref.category)
            if rule_key in conflict_rules:
                await self._create_conflict(
                    user_id,
                    new_preference.id,
                    existing_pref.id,
                    "indirect",
                    conflict_rules[rule_key],
                )

            # Direct opposition (same category, different type)
            if (new_preference.category == existing_pref.category and
                new_preference.preference_type != existing_pref.preference_type):
                await self._create_conflict(
                    user_id,
                    new_preference.id,
                    existing_pref.id,
                    "direct",
                    f"Opposing {new_preference.category} preferences",
                )

    async def _create_conflict(
        self,
        user_id: uuid.UUID,
        pref_id_1: uuid.UUID,
        pref_id_2: uuid.UUID,
        conflict_type: str,
        description: str,
    ) -> None:
        """Create a preference conflict record.

        Args:
            user_id: User ID
            pref_id_1: First preference ID
            pref_id_2: Second preference ID
            conflict_type: Type of conflict
            description: Conflict description
        """
        # Check severity based on confidence scores
        pref1 = await self.preference_repo.get_by_id(pref_id_1)
        pref2 = await self.preference_repo.get_by_id(pref_id_2)

        if not pref1 or not pref2:
            return

        avg_confidence = (pref1.confidence_score + pref2.confidence_score) / 2

        if avg_confidence >= 0.8:
            severity = "high"
        elif avg_confidence >= 0.5:
            severity = "medium"
        else:
            severity = "low"

        # Check if conflict already exists
        existing_conflicts = await self.conflict_repo.get_user_conflicts(user_id)
        for conflict in existing_conflicts:
            if ((conflict.preference_id_1 == pref_id_1 and conflict.preference_id_2 == pref_id_2) or
                (conflict.preference_id_1 == pref_id_2 and conflict.preference_id_2 == pref_id_1)):
                return  # Conflict already exists

        # Create new conflict
        from src.models.preference import PreferenceConflict

        conflict = PreferenceConflict(
            user_id=user_id,
            preference_id_1=pref_id_1,
            preference_id_2=pref_id_2,
            conflict_type=conflict_type,
            severity=severity,
            description=description,
        )
        self.session.add(conflict)

        logger.info(f"Created {severity} severity conflict for user {user_id}: {description}")

    async def cleanup_expired_preferences(
        self,
        user_id: uuid.UUID,
    ) -> int:
        """Clean up expired preferences for a user.

        Args:
            user_id: User ID

        Returns:
            Number of preferences cleaned up
        """
        return await self.preference_repo.cleanup_expired_preferences(user_id)

    async def get_conflicts(
        self,
        user_id: uuid.UUID,
        unresolved_only: bool = False,
    ) -> list[Any]:
        """Get preference conflicts for a user.

        Args:
            user_id: User ID
            unresolved_only: Only return unresolved conflicts

        Returns:
            List of conflicts
        """
        conflicts = await self.conflict_repo.get_user_conflicts(
            user_id,
            unresolved_only=unresolved_only,
        )

        # Convert to response format
        return [
            {
                "id": str(c.id),
                "user_id": str(c.user_id),
                "preference_id_1": str(c.preference_id_1),
                "preference_id_2": str(c.preference_id_2),
                "conflict_type": c.conflict_type,
                "severity": c.severity,
                "description": c.description,
                "resolved": c.resolved,
                "resolution": c.resolution,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in conflicts
        ]
