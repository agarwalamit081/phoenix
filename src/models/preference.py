"""Preference model for storing user travel preferences."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import BaseModel

if TYPE_CHECKING:
    from src.models.user import User


class UserPreference(BaseModel):
    """User preference model for storing structured travel preferences."""

    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    preference_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # 'like', 'dislike', 'neutral'
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )  # 'cuisine', 'activity', 'art_style', 'transport', etc.
    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )  # Natural language description of the preference
    embedding: Mapped[bytes | None] = mapped_column(
        Vector(1536),
        nullable=True,
    )  # OpenAI embedding for semantic search
    confidence_score: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )  # Confidence in preference extraction (0.0 to 1.0)
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # 'explicit', 'inferred', 'behavioral'
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )  # Optional expiration for temporary preferences
    context: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # Additional context about the preference

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="preferences",
    )

    def is_expired(self) -> bool:
        """Check if the preference has expired.

        Returns:
            bool: True if preference is expired
        """
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    def is_strong_preference(self) -> bool:
        """Check if this is a strong preference (high confidence).

        Returns:
            bool: True if confidence score is above 0.7
        """
        return self.confidence_score >= 0.7

    def to_dict(self) -> dict:
        """Convert preference to dictionary.

        Returns:
            dict: Dictionary representation of the preference
        """
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "preference_type": self.preference_type,
            "category": self.category,
            "value": self.value,
            "confidence_score": self.confidence_score,
            "source": self.source,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "context": self.context,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PreferenceConflict(BaseModel):
    """Record of detected conflicts between preferences."""

    __tablename__ = "preference_conflicts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    preference_id_1: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_preferences.id", ondelete="CASCADE"),
        nullable=False,
    )
    preference_id_2: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_preferences.id", ondelete="CASCADE"),
        nullable=False,
    )
    conflict_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # 'direct', 'indirect', 'contextual'
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # 'low', 'medium', 'high'
    description: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        """Convert conflict to dictionary.

        Returns:
            dict: Dictionary representation of the conflict
        """
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "preference_id_1": str(self.preference_id_1),
            "preference_id_2": str(self.preference_id_2),
            "conflict_type": self.conflict_type,
            "severity": self.severity,
            "description": self.description,
            "resolved": self.resolved,
            "resolution": self.resolution,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Alias for backward compatibility
Preference = UserPreference
