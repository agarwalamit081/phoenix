"""Pytest configuration and fixtures for testing."""

import asyncio
import uuid
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

from src.config.settings import settings
from src.database import Base, get_session
from src.models.user import User


# Test database URL
TEST_DATABASE_URL = settings.test_database_url


# Event loop for tests - use function scope to avoid conflicts
@pytest.fixture
def event_loop_policy():
    """Use the default event loop policy for tests."""
    return asyncio.get_event_loop_policy()


# Async engine
@pytest_asyncio.fixture(scope="function")
async def test_engine() -> AsyncGenerator[Any, None]:
    """Create test database engine.

    Yields:
        Async engine
    """
    from sqlalchemy.pool import NullPool

    # Use NullPool to avoid connection pooling issues with multiple event loops
    # Each request gets a fresh connection instead of reusing pooled connections
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
        poolclass=NullPool,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


# Test session factory
@pytest_asyncio.fixture(scope="function")
async def test_session_maker(test_engine: Any) -> AsyncGenerator[Any, None]:
    """Create test session maker.

    Args:
        test_engine: Test engine

    Yields:
        Session maker
    """
    async_session_maker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    yield async_session_maker


# Test session
@pytest_asyncio.fixture
async def test_session(test_session_maker: Any) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session.

    Args:
        test_session_maker: Session maker

    Yields:
        Database session

    Note:
        This fixture commits changes instead of rolling them back.
        This allows data to persist between requests within the same test,
        which is necessary for multi-request tests (e.g., register then login).
        The cleanup_database fixture handles cleaning up between tests.
    """
    async with test_session_maker() as session:
        yield session
        # Commit changes so they persist for subsequent requests in the same test
        await session.commit()


# Database cleanup - use pytest hooks for session-level cleanup
@pytest.fixture(scope="session", autouse=True)
def cleanup_database_sync() -> Generator[None, None, None]:
    """Clean up database once at the start and end of the test session.

    This uses synchronous SQLAlchemy to avoid async fixture scope issues.

    Yields:
        None
    """
    from sqlalchemy import create_engine, text

    # Convert async URL to sync URL
    sync_url = TEST_DATABASE_URL.replace("+asyncpg", "").replace("asyncpg", "postgresql+psycopg2")

    # Create a synchronous engine for cleanup
    cleanup_engine = create_engine(
        sync_url,
        echo=False,
    )

    print("DEBUG: Initial database cleanup")
    with cleanup_engine.begin() as conn:
        # Try to delete data if tables exist, ignore errors if they don't
        try:
            conn.execute(text("DELETE FROM refresh_tokens"))
        except Exception:
            pass
        try:
            conn.execute(text("DELETE FROM user_preferences"))
        except Exception:
            pass
        try:
            conn.execute(text("DELETE FROM itinerary_items"))
        except Exception:
            pass
        try:
            conn.execute(text("DELETE FROM itineraries"))
        except Exception:
            pass
        try:
            conn.execute(text("DELETE FROM users"))
        except Exception:
            pass
    print("DEBUG: Initial cleanup done")

    yield

    # Final cleanup at the end of the test session
    print("DEBUG: Final database cleanup")
    with cleanup_engine.begin() as conn:
        try:
            conn.execute(text("DELETE FROM refresh_tokens"))
        except Exception:
            pass
        try:
            conn.execute(text("DELETE FROM user_preferences"))
        except Exception:
            pass
        try:
            conn.execute(text("DELETE FROM itinerary_items"))
        except Exception:
            pass
        try:
            conn.execute(text("DELETE FROM itineraries"))
        except Exception:
            pass
        try:
            conn.execute(text("DELETE FROM users"))
        except Exception:
            pass
    print("DEBUG: Final cleanup done")

    cleanup_engine.dispose()


# Cleanup after each test function
@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup_after_test() -> AsyncGenerator[None, None]:
    """Clean up database after each test function.

    This ensures data doesn't leak between tests.

    Yields:
        None
    """
    from sqlalchemy.pool import NullPool

    # Create a temporary engine just for cleanup
    cleanup_engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
        poolclass=NullPool,
    )

    yield

    # Clean up after the test - wrap in try/except in case tables don't exist
    try:
        async with cleanup_engine.begin() as conn:
            # Delete in correct order due to foreign key constraints
            try:
                await conn.execute(text("DELETE FROM refresh_tokens"))
            except Exception:
                pass
            try:
                await conn.execute(text("DELETE FROM user_preferences"))
            except Exception:
                pass
            try:
                await conn.execute(text("DELETE FROM itinerary_items"))
            except Exception:
                pass
            try:
                await conn.execute(text("DELETE FROM itineraries"))
            except Exception:
                pass
            try:
                await conn.execute(text("DELETE FROM users"))
            except Exception:
                pass
    except Exception:
        pass

    await cleanup_engine.dispose()


# Mock user
@pytest.fixture
def mock_user() -> User:
    """Create a mock user.

    Returns:
        Mock user object
    """
    return User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash="hashed_password",
        display_name="Test User",
        preferred_language="en",
        is_active=True,
        is_verified=True,
    )


# Mock user in database
@pytest_asyncio.fixture
async def test_user(test_session: AsyncSession) -> AsyncGenerator[User, None]:
    """Create a test user in the database.

    Args:
        test_session: Test session

    Yields:
        Created user
    """
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        display_name="Test User",
        preferred_language="en",
        is_active=True,
        is_verified=True,
    )
    test_session.add(user)
    await test_session.flush()

    yield user


# Mock settings
@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings.

    Returns:
        Mock settings object
    """
    mock = MagicMock(spec=settings)
    mock.openai_api_key = "test-api-key"
    mock.database_url = TEST_DATABASE_URL
    mock.secret_key = "test-secret-key"
    mock.access_token_expire_minutes = 15
    mock.refresh_token_expire_days = 7
    mock.algorithm = "HS256"
    mock.environment = "testing"
    mock.debug = True

    return mock


# Mock LLM service
@pytest.fixture
def mock_llm_service() -> AsyncMock:
    """Create mock LLM service.

    Returns:
        Mock LLM service
    """
    mock = AsyncMock()
    mock.chat_completion.return_value = {
        "content": "Test response",
        "model": "gpt-4o-mini",
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        },
        "finish_reason": "stop",
    }
    mock.generate_embeddings.return_value = [[0.1] * 1536]
    mock.extract_entities.return_value = []
    mock.classify_intent.return_value = {
        "intent": "general_question",
        "confidence": 0.8,
        "reasoning": "Test reasoning",
    }

    return mock


# Mock embedding service
@pytest.fixture
def mock_embedding_service() -> AsyncMock:
    """Create mock embedding service.

    Returns:
        Mock embedding service
    """
    mock = AsyncMock()
    mock.generate_embedding.return_value = [0.1] * 1536
    mock.generate_embeddings.return_value = [[0.1] * 1536]
    mock.compute_similarity.return_value = 0.85
    mock.find_similar.return_value = []

    return mock


# Test client - use synchronous TestClient to avoid event loop issues
@pytest.fixture(scope="function")
def test_client(test_session_maker: Any):
    """Create test client for FastAPI app.

    Args:
        test_session_maker: Test session maker factory

    Returns:
        Test client
    """
    from fastapi.testclient import TestClient
    from src.main import fastapi_app
    from src.database import get_session

    # Override database dependency to create a fresh session for each request
    # This prevents event loop issues and state pollution between requests
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            else:
                # Commit in testing mode so each request's changes are visible
                await session.commit()
            finally:
                await session.close()

    fastapi_app.dependency_overrides[get_session] = override_get_session

    # Use TestClient - it handles async internally without event loop conflicts
    client = TestClient(fastapi_app)

    yield client

    fastapi_app.dependency_overrides.clear()


# Async test client - use TestClient with proper dependency override support
@pytest_asyncio.fixture(scope="function")
async def async_client(test_session_maker: Any) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create async test client for FastAPI app.

    Uses TestClient which properly supports dependency overrides.
    With NullPool and proper session management, we can avoid event loop issues.

    Args:
        test_session_maker: Test session maker factory

    Yields:
        Async test client (httpx.AsyncClient wrapped for TestClient compatibility)
    """
    from fastapi.testclient import TestClient
    from src.main import fastapi_app
    from src.database import get_session, reset_engine

    # Reset the global engine so it gets recreated with NullPool
    reset_engine()

    # Override database dependency to create a fresh session for each request
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            else:
                # Commit in testing mode so each request's changes are visible
                # This is critical for multi-request tests (e.g., register then login)
                await session.commit()
            finally:
                await session.close()

    fastapi_app.dependency_overrides[get_session] = override_get_session

    # Use TestClient which properly handles dependency overrides
    class AsyncTestClient:
        """Async wrapper around TestClient for compatibility with async tests."""

        def __init__(self, test_client: TestClient):
            self.client = test_client

        def post(self, url: str, **kwargs):
            return self.client.post(url, **kwargs)

        def get(self, url: str, **kwargs):
            return self.client.get(url, **kwargs)

        def put(self, url: str, **kwargs):
            return self.client.put(url, **kwargs)

        def patch(self, url: str, **kwargs):
            return self.client.patch(url, **kwargs)

        def delete(self, url: str, **kwargs):
            return self.client.delete(url, **kwargs)

    client = TestClient(fastapi_app)
    async_client = AsyncTestClient(client)

    yield async_client

    fastapi_app.dependency_overrides.clear()


# Mock authentication token
@pytest.fixture
def mock_auth_token(mock_user: User) -> str:
    """Create a mock JWT token.

    Args:
        mock_user: Mock user

    Returns:
        Mock JWT token
    """
    from jose import jwt
    from datetime import datetime, timedelta, timezone

    payload = {
        "sub": str(mock_user.id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
        "type": "access",
    }

    return jwt.encode(payload, "test-secret-key", algorithm="HS256")


# Override database dependency
@pytest_asyncio.fixture
async def override_db_session(test_session: AsyncSession) -> AsyncGenerator[None, None]:
    """Override database session dependency for testing.

    Args:
        test_session: Test session

    Yields:
        None

    Note:
        This fixture commits changes instead of rolling them back.
        This allows data to persist between requests within the same test.
    """
    from src.main import fastapi_app

    async def get_test_session() -> AsyncGenerator[AsyncSession, None]:
        yield test_session
        # Commit so changes persist for subsequent operations
        await test_session.commit()

    fastapi_app.dependency_overrides[get_session] = get_test_session

    yield

    fastapi_app.dependency_overrides.clear()


# Mock external services
@pytest.fixture
def mock_openai_client() -> AsyncMock:
    """Create mock OpenAI client.

    Returns:
        Mock OpenAI client
    """
    mock = AsyncMock()

    # Mock chat completion
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Test response"
    mock_response.choices[0].finish_reason = "stop"
    mock_response.model = "gpt-4o-mini"
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 20
    mock_response.usage.total_tokens = 30

    mock.chat.completions.create.return_value = mock_response

    # Mock embeddings
    mock_embedding_response = MagicMock()
    mock_embedding_response.data = [MagicMock(embedding=[0.1] * 1536)]
    mock.embeddings.create.return_value = mock_embedding_response

    return mock


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create mock Redis client.

    Returns:
        Mock Redis client
    """
    mock = AsyncMock()
    mock.incr.return_value = 1
    mock.expire.return_value = True
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = 1

    return mock


@pytest.fixture
def mock_neo4j() -> AsyncMock:
    """Create mock Neo4j client.

    Returns:
        Mock Neo4j client
    """
    mock = AsyncMock()
    mock.run.return_value = MagicMock()
    mock.close.return_value = None

    return mock


# Mock LiveKit
@pytest.fixture
def mock_livekit() -> AsyncMock:
    """Create mock LiveKit service.

    Returns:
        Mock LiveKit service
    """
    mock = AsyncMock()
    mock.create_room.return_value = MagicMock(sid="test-room-sid")
    mock.list_rooms.return_value = []

    return mock


# Patch external services
@pytest.fixture(autouse=True)
def patch_external_services(
    mock_openai_client: AsyncMock,
    mock_redis: AsyncMock,
    mock_neo4j: AsyncMock,
    mock_livekit: AsyncMock,
) -> Generator[None, None, None]:
    """Patch all external services with mocks.

    Args:
        mock_openai_client: Mock OpenAI client
        mock_redis: Mock Redis client
        mock_neo4j: Mock Neo4j client
        mock_livekit: Mock LiveKit service

    Yields:
        None
    """
    with patch("openai.AsyncOpenAI", return_value=mock_openai_client), \
         patch("redis.asyncio.Redis", return_value=mock_redis):
        yield


# Skip external API tests if no API keys
@pytest.fixture(scope="session")
def skip_external_tests() -> bool:
    """Determine if external API tests should be skipped.

    Returns:
        True if API keys are not configured
    """
    return not bool(settings.openai_api_key and settings.openai_api_key != "")


# Performance testing marker
@pytest.fixture
def benchmark_threshold() -> dict[str, float]:
    """Performance threshold values for benchmarks.

    Returns:
        Dictionary of thresholds
    """
    return {
        "api_response_time_ms": 200.0,
        "database_query_time_ms": 50.0,
        "llm_generation_time_ms": 2000.0,
        "embedding_generation_time_ms": 500.0,
    }
