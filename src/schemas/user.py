"""Pydantic schemas for user-related operations."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    """Request schema for user registration."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=100, description="User password")
    display_name: str | None = Field(None, max_length=100, description="Display name")
    preferred_language: str = Field("en", pattern="^[a-z]{2}$", description="Preferred language code")
    timezone: str | None = Field(None, max_length=50, description="User timezone")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength.

        Args:
            v: The password value

        Returns:
            The validated password
        """
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLoginRequest(BaseModel):
    """Request schema for user login."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class OAuthLoginRequest(BaseModel):
    """Request schema for OAuth login."""

    provider: str = Field(..., pattern="^(google|apple)$", description="OAuth provider")
    token: str = Field(..., description="OAuth ID token")


class TokenResponse(BaseModel):
    """Response schema for token-based authentication."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")


class TokenRefreshRequest(BaseModel):
    """Request schema for token refresh."""

    refresh_token: str = Field(..., description="Refresh token")


class UserProfileResponse(BaseModel):
    """Response schema for user profile."""

    id: uuid.UUID = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    display_name: str | None = Field(None, description="Display name")
    preferred_language: str = Field(..., description="Preferred language")
    timezone: str | None = Field(None, description="User timezone")
    bio: str | None = Field(None, description="User biography")
    avatar_url: str | None = Field(None, description="Avatar URL")
    home_city: str | None = Field(None, description="Home city")
    home_country: str | None = Field(None, description="Home country")
    is_verified: bool = Field(..., description="Email verification status")
    created_at: datetime = Field(..., description="Account creation date")

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    """Request schema for updating user profile."""

    display_name: str | None = Field(None, max_length=100, description="Display name")
    preferred_language: str | None = Field(None, pattern="^[a-z]{2}$", description="Preferred language")
    timezone: str | None = Field(None, max_length=50, description="User timezone")
    bio: str | None = Field(None, max_length=1000, description="User biography")
    avatar_url: str | None = Field(None, max_length=500, description="Avatar URL")
    home_city: str | None = Field(None, max_length=100, description="Home city")
    home_country: str | None = Field(None, max_length=100, description="Home country")


class PasswordChangeRequest(BaseModel):
    """Request schema for changing password."""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=100, description="New password")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate new password strength.

        Args:
            v: The password value

        Returns:
            The validated password
        """
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class PasswordResetRequest(BaseModel):
    """Request schema for password reset."""

    email: EmailStr = Field(..., description="User email")


class PasswordResetConfirmRequest(BaseModel):
    """Request schema for confirming password reset."""

    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, max_length=100, description="New password")

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate new password strength.

        Args:
            v: The password value

        Returns:
            The validated password
        """
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class ErrorResponse(BaseModel):
    """Response schema for errors."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: dict[str, object] | None = Field(None, description="Additional error details")
