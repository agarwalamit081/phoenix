"""Pydantic schemas for preference-related operations."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PreferenceCreateRequest(BaseModel):
    """Request schema for creating a user preference."""

    category: str = Field(..., min_length=1, max_length=100, description="Preference category")
    value: str = Field(..., min_length=1, max_length=1000, description="Preference description")
    preference_type: str = Field(
        ...,
        pattern="^(like|dislike|neutral)$",
        description="Type of preference"
    )
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score")
    context: str | None = Field(None, description="Additional context")

    @field_validator("category")
    @classmethod
    def normalize_category(cls, v: str) -> str:
        """Normalize category to lowercase.

        Args:
            v: The category value

        Returns:
            Normalized category
        """
        return v.lower().strip()


class PreferenceUpdateRequest(BaseModel):
    """Request schema for updating a user preference."""

    value: str | None = Field(None, min_length=1, max_length=1000, description="Preference description")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Confidence score")
    preference_type: str | None = Field(
        None,
        pattern="^(like|dislike|neutral)$",
        description="Type of preference"
    )


class PreferenceResponse(BaseModel):
    """Response schema for user preference."""

    id: uuid.UUID = Field(..., description="Preference ID")
    user_id: uuid.UUID = Field(..., description="User ID")
    preference_type: str = Field(..., description="Type of preference")
    category: str = Field(..., description="Preference category")
    value: str = Field(..., description="Preference description")
    confidence_score: float = Field(..., description="Confidence score")
    source: str = Field(..., description="Preference source")
    expires_at: datetime | None = Field(None, description="Expiration time")
    context: str | None = Field(None, description="Additional context")
    created_at: datetime = Field(..., description="Creation time")

    model_config = {"from_attributes": True}


class PreferenceListResponse(BaseModel):
    """Response schema for listing preferences."""

    preferences: list[PreferenceResponse] = Field(..., description="List of preferences")
    total: int = Field(..., description="Total number of preferences")
    categories: list[str] = Field(..., description="Available categories")


class PreferenceConflictResponse(BaseModel):
    """Response schema for preference conflict."""

    id: uuid.UUID = Field(..., description="Conflict ID")
    user_id: uuid.UUID = Field(..., description="User ID")
    preference_id_1: uuid.UUID = Field(..., description="First preference ID")
    preference_id_2: uuid.UUID = Field(..., description="Second preference ID")
    conflict_type: str = Field(..., description="Type of conflict")
    severity: str = Field(..., description="Conflict severity")
    description: str = Field(..., description="Conflict description")
    resolved: bool = Field(..., description="Resolution status")
    resolution: str | None = Field(None, description="Resolution description")
    created_at: datetime = Field(..., description="Creation time")

    model_config = {"from_attributes": True}


class UserProfileSummary(BaseModel):
    """Summary of user preferences profile."""

    total_preferences: int = Field(..., description="Total number of preferences")
    strong_preferences: int = Field(..., description="Number of strong preferences")
    categories: dict[str, int] = Field(..., description="Preferences by category")
    top_interests: list[dict[str, Any]] = Field(..., description="Top interests")
    dislikes: list[str] = Field(..., description="Key dislikes")
    unresolved_conflicts: int = Field(..., description="Number of unresolved conflicts")


class PreferenceBulkCreateRequest(BaseModel):
    """Request schema for bulk creating preferences."""

    preferences: list[PreferenceCreateRequest] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of preferences to create"
    )


class PreferenceType(str, Enum):
    """Preference type enumeration."""

    LIKE = "like"
    DISLIKE = "dislike"
    NEUTRAL = "neutral"
