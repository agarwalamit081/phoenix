"""Pydantic schemas for chat-related operations."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Chat message schema."""

    role: str = Field(..., pattern="^(user|assistant|system)$", description="Message role")
    content: str = Field(..., description="Message content")
    timestamp: datetime | None = Field(None, description="Message timestamp")
    metadata: dict[str, Any] | None = Field(None, description="Optional message metadata")


class ChatRequest(BaseModel):
    """Request schema for sending a chat message."""

    message: str = Field(..., min_length=1, max_length=5000, description="User message")
    conversation_id: uuid.UUID | None = Field(None, description="Conversation ID for context")
    language: str | None = Field(None, pattern="^[a-z]{2}$", description="Message language")
    include_preferences: bool = Field(
        True,
        description="Whether to include user preferences in context"
    )


class ChatResponse(BaseModel):
    """Response schema for chat responses."""

    message_id: uuid.UUID = Field(..., description="Unique message ID")
    role: str = Field("assistant", description="Message role")
    content: str = Field(..., description="Response content")
    timestamp: datetime = Field(..., description="Response timestamp")
    preferences_detected: list[dict[str, Any]] | None = Field(
        None, description="Preferences detected from conversation"
    )
    suggested_actions: list[str] | None = Field(
        None, description="Suggested follow-up actions"
    )


class ConversationHistory(BaseModel):
    """Schema for conversation history."""

    conversation_id: uuid.UUID = Field(..., description="Conversation ID")
    messages: list[ChatMessage] = Field(..., description="List of messages")
    created_at: datetime = Field(..., description="Conversation creation time")
    updated_at: datetime = Field(..., description="Last update time")


class ConversationListResponse(BaseModel):
    """Response schema for listing conversations."""

    conversations: list[ConversationHistory] = Field(..., description="List of conversations")
    total: int = Field(..., description="Total number of conversations")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of conversations per page")


class StreamingChunk(BaseModel):
    """Schema for streaming response chunk."""

    delta: str | None = Field(None, description="Content delta")
    finish_reason: str | None = Field(None, description="Reason for finishing")
    message_id: uuid.UUID = Field(..., description="Message ID")


class PreferenceExtraction(BaseModel):
    """Schema for extracted preferences from chat."""

    category: str = Field(..., description="Preference category")
    value: str = Field(..., description="Preference value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    preference_type: str = Field(
        ...,
        pattern="^(like|dislike|neutral)$",
        description="Type of preference"
    )
