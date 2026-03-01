"""Redis-based session storage for LangGraph checkpoints and user sessions."""

import json
import uuid
from typing import Any, AsyncGenerator

from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool

from src.config.logging import logger
from src.config.settings import settings

# Redis connection pool
_pool: ConnectionPool | None = None


def get_redis_pool() -> ConnectionPool:
    """Get or create Redis connection pool.

    Returns:
        Redis connection pool
    """
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=settings.redis_pool_size,
        )
    return _pool


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Get Redis client from pool.

    Yields:
        Redis client
    """
    pool = get_redis_pool()
    async with Redis(connection_pool=pool) as redis:
        yield redis


# Session storage keys
SESSION_PREFIX = "session:"
CHECKPOINT_PREFIX = "checkpoint:"
USER_STATE_PREFIX = "user_state:"
SESSION_TTL = 3600  # 1 hour
CHECKPOINT_TTL = 86400  # 24 hours


async def save_session(session_id: str, state: dict[str, Any], ttl: int | None = None) -> None:
    """Save session state to Redis.

    Args:
        session_id: Session identifier
        state: Session state dictionary
        ttl: Time to live in seconds (defaults to SESSION_TTL)
    """
    key = f"{SESSION_PREFIX}{session_id}"
    ttl = ttl or SESSION_TTL

    try:
        async with Redis(connection_pool=get_redis_pool()) as redis:
            await redis.setex(key, ttl, json.dumps(state))
            logger.debug(f"Saved session {session_id} to Redis")
    except Exception as e:
        logger.error(f"Failed to save session {session_id}: {e}")
        raise


async def load_session(session_id: str) -> dict[str, Any] | None:
    """Load session state from Redis.

    Args:
        session_id: Session identifier

    Returns:
        Session state dictionary or None if not found
    """
    key = f"{SESSION_PREFIX}{session_id}"

    try:
        async with Redis(connection_pool=get_redis_pool()) as redis:
            data = await redis.get(key)
            if data:
                return json.loads(data)
            return None
    except Exception as e:
        logger.error(f"Failed to load session {session_id}: {e}")
        return None


async def delete_session(session_id: str) -> None:
    """Delete session from Redis.

    Args:
        session_id: Session identifier
    """
    session_key = f"{SESSION_PREFIX}{session_id}"
    checkpoint_pattern = f"{CHECKPOINT_PREFIX}{session_id}:*"

    try:
        async with Redis(connection_pool=get_redis_pool()) as redis:
            # Delete session data
            await redis.delete(session_key)

            # Delete associated checkpoints
            keys = await redis.keys(checkpoint_pattern)
            if keys:
                await redis.delete(*keys)

            logger.debug(f"Deleted session {session_id} from Redis")
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")


async def save_checkpoint(
    thread_id: str,
    checkpoint_id: str,
    state: dict[str, Any],
    ttl: int | None = None
) -> None:
    """Save LangGraph checkpoint to Redis.

    Args:
        thread_id: Thread identifier
        checkpoint_id: Checkpoint identifier
        state: Checkpoint state dictionary
        ttl: Time to live in seconds (defaults to CHECKPOINT_TTL)
    """
    key = f"{CHECKPOINT_PREFIX}{thread_id}:{checkpoint_id}"
    ttl = ttl or CHECKPOINT_TTL
    timestamp = str(uuid.uuid4())

    try:
        async with Redis(connection_pool=get_redis_pool()) as redis:
            await redis.hset(
                key,
                mapping={
                    "state": json.dumps(state),
                    "timestamp": timestamp,
                }
            )
            await redis.expire(key, ttl)
            logger.debug(f"Saved checkpoint {checkpoint_id} for thread {thread_id}")
    except Exception as e:
        logger.error(f"Failed to save checkpoint {checkpoint_id}: {e}")
        raise


async def load_checkpoint(thread_id: str, checkpoint_id: str) -> dict[str, Any] | None:
    """Load LangGraph checkpoint from Redis.

    Args:
        thread_id: Thread identifier
        checkpoint_id: Checkpoint identifier

    Returns:
        Checkpoint state dictionary or None if not found
    """
    key = f"{CHECKPOINT_PREFIX}{thread_id}:{checkpoint_id}"

    try:
        async with Redis(connection_pool=get_redis_pool()) as redis:
            data = await redis.hget(key, "state")
            if data:
                return json.loads(data)
            return None
    except Exception as e:
        logger.error(f"Failed to load checkpoint {checkpoint_id}: {e}")
        return None


async def list_checkpoints(thread_id: str) -> list[str]:
    """List all checkpoints for a thread.

    Args:
        thread_id: Thread identifier

    Returns:
        List of checkpoint IDs
    """
    pattern = f"{CHECKPOINT_PREFIX}{thread_id}:*"

    try:
        async with Redis(connection_pool=get_redis_pool()) as redis:
            keys = await redis.keys(pattern)
            # Extract checkpoint IDs from keys
            return [key.split(":")[-1] for key in keys]
    except Exception as e:
        logger.error(f"Failed to list checkpoints for thread {thread_id}: {e}")
        return []


async def save_user_state(user_id: uuid.UUID, state: dict[str, Any], ttl: int = SESSION_TTL) -> None:
    """Save user state to Redis.

    Args:
        user_id: User ID
        state: User state dictionary
        ttl: Time to live in seconds
    """
    key = f"{USER_STATE_PREFIX}{str(user_id)}"

    try:
        async with Redis(connection_pool=get_redis_pool()) as redis:
            await redis.setex(key, ttl, json.dumps(state))
            logger.debug(f"Saved user state for {user_id}")
    except Exception as e:
        logger.error(f"Failed to save user state for {user_id}: {e}")
        raise


async def load_user_state(user_id: uuid.UUID) -> dict[str, Any] | None:
    """Load user state from Redis.

    Args:
        user_id: User ID

    Returns:
        User state dictionary or None if not found
    """
    key = f"{USER_STATE_PREFIX}{str(user_id)}"

    try:
        async with Redis(connection_pool=get_redis_pool()) as redis:
            data = await redis.get(key)
            if data:
                return json.loads(data)
            return None
    except Exception as e:
        logger.error(f"Failed to load user state for {user_id}: {e}")
        return None


async def clear_all_sessions() -> int:
    """Clear all sessions from Redis (for testing/admin).

    Returns:
        Number of sessions deleted
    """
    patterns = [
        f"{SESSION_PREFIX}*",
        f"{CHECKPOINT_PREFIX}*",
        f"{USER_STATE_PREFIX}*",
    ]

    try:
        async with Redis(connection_pool=get_redis_pool()) as redis:
            total_deleted = 0
            for pattern in patterns:
                keys = await redis.keys(pattern)
                if keys:
                    total_deleted += await redis.delete(*keys)
            logger.info(f"Cleared {total_deleted} session-related keys from Redis")
            return total_deleted
    except Exception as e:
        logger.error(f"Failed to clear sessions: {e}")
        return 0
