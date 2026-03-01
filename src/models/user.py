"""User model and related database models."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import BaseModel

if TYPE_CHECKING:
    from src.models.preference import UserPreference
    from src.models.itinerary import Itinerary


class User(BaseModel):
    """User model representing application users."""

    __tablename__ = "users"

    # Authentication fields
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # OAuth fields
    google_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    apple_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)

    # User preferences
    preferred_language: Mapped[str] = mapped_column(
        String(10), default="en", nullable=False
    )
    timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Account status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Activity tracking
    last_active_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Profile fields
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Location (optional, for context)
    home_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    home_country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    preferences: Mapped[list["UserPreference"]] = relationship(
        "UserPreference",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    itineraries: Mapped[list["Itinerary"]] = relationship(
        "Itinerary",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def update_last_active(self) -> None:
        """Update the last active timestamp."""
        self.last_active_at = datetime.now()

    def update_last_login(self) -> None:
        """Update the last login timestamp."""
        self.last_login_at = datetime.now()
        self.update_last_active()

    def set_password(self, password_hash: str) -> None:
        """Set the password hash.

        Args:
            password_hash: The hashed password to set
        """
        self.password_hash = password_hash

    @property
    def is_oauth_user(self) -> bool:
        """Check if user registered via OAuth.

        Returns:
            bool: True if user has OAuth provider ID
        """
        return self.google_id is not None or self.apple_id is not None

    def to_profile_dict(self) -> dict:
        """Convert to public profile dictionary (excludes sensitive data).

        Returns:
            dict: Public profile information
        """
        return {
            "id": str(self.id),
            "email": self.email,
            "display_name": self.display_name,
            "preferred_language": self.preferred_language,
            "timezone": self.timezone,
            "bio": self.bio,
            "avatar_url": self.avatar_url,
            "home_city": self.home_city,
            "home_country": self.home_country,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RefreshToken(BaseModel):
    """Refresh token model for JWT token management."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    device_info: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    def is_valid(self) -> bool:
        """Check if the refresh token is valid.

        Returns:
            bool: True if token is valid and not expired
        """
        if self.is_revoked:
            return False
        if datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    def revoke(self) -> None:
        """Revoke the refresh token."""
        self.is_revoked = True
        self.revoked_at = datetime.now(timezone.utc)


class PasswordReset(BaseModel):
    """Password reset token model."""

    __tablename__ = "password_resets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def is_valid(self) -> bool:
        """Check if the password reset token is valid.

        Returns:
            bool: True if token is valid and not expired
        """
        if self.is_used:
            return False
        if datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    def mark_as_used(self) -> None:
        """Mark the password reset token as used."""
        self.is_used = True
        self.used_at = datetime.now(timezone.utc)
