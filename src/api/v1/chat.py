"""Chat API endpoints."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DBSession
from src.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ConversationHistory,
    ConversationListResponse,
)
from src.services.chat_service import ChatService

router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def send_message(
    data: ChatRequest,
    user: CurrentUser,
    session: DBSession,
) -> ChatResponse:
    """Send a chat message and get a response.

    Args:
        data: Chat request data
        user: Current user
        session: Database session

    Returns:
        Chat response from the AI
    """
    chat_service = ChatService(session)
    return await chat_service.send_message(
        user_id=user.id,
        message=data.message,
        conversation_id=data.conversation_id,
        language=data.language or user.preferred_language,
        include_preferences=data.include_preferences,
    )


@router.post("/stream", response_model=ChatResponse)
async def stream_message(
    data: ChatRequest,
    user: CurrentUser,
    session: DBSession,
) -> ChatResponse:
    """Backward-compatible streaming endpoint using standard response fallback."""
    chat_service = ChatService(session)
    return await chat_service.send_message(
        user_id=user.id,
        message=data.message,
        conversation_id=data.conversation_id,
        language=data.language or user.preferred_language,
        include_preferences=data.include_preferences,
    )


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    user: CurrentUser,
    session: DBSession,
    offset: int = 0,
    limit: int = 20,
) -> ConversationListResponse:
    """List user's conversations.

    Args:
        user: Current user
        session: Database session
        offset: Pagination offset
        limit: Pagination limit

    Returns:
        List of conversations
    """
    chat_service = ChatService(session)
    # This would typically query a conversations table
    # For now, return empty list as conversations are in-memory
    return ConversationListResponse(
        conversations=[],
        total=0,
        page=offset // limit + 1,
        page_size=limit,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationHistory)
async def get_conversation(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    session: DBSession,
) -> ConversationHistory:
    """Get conversation history.

    Args:
        conversation_id: Conversation ID
        user: Current user
        session: Database session

    Returns:
        Conversation history
    """
    chat_service = ChatService(session)
    return await chat_service.get_conversation_history(conversation_id)


@router.get("/history", response_model=ConversationHistory)
async def get_latest_history(
    user: CurrentUser,
    session: DBSession,
    offset: int = 0,
    limit: int = 20,
) -> ConversationHistory:
    """Backward-compatible history endpoint returning user's latest conversation."""
    chat_service = ChatService(session)
    return await chat_service.get_user_history(
        user_id=user.id,
        offset=offset,
        limit=limit,
    )


@router.get("/history/{conversation_id}", response_model=ConversationHistory)
async def get_history_by_id(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    session: DBSession,
) -> ConversationHistory:
    """Backward-compatible conversation history by ID endpoint."""
    chat_service = ChatService(session)
    return await chat_service.get_conversation_history(conversation_id)


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    session: DBSession,
) -> dict[str, str]:
    """Delete a conversation.

    Args:
        conversation_id: Conversation ID
        user: Current user
        session: Database session

    Returns:
        Deletion confirmation
    """
    chat_service = ChatService(session)
    await chat_service.delete_conversation(conversation_id)
    return {"message": "Conversation deleted"}


@router.delete("/history/{conversation_id}", status_code=204)
async def delete_history_conversation(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    session: DBSession,
) -> Response:
    """Backward-compatible conversation delete endpoint."""
    chat_service = ChatService(session)
    await chat_service.delete_conversation(conversation_id)
    return Response(status_code=204)
