"""Async database connection management for PostgreSQL."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from src.config.logging import logger
from src.config.settings import settings

# Global engine and session maker
_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get the async database engine."""
    global _engine
    if _engine is None:
        # Use NullPool in testing to avoid event loop issues
        pool_class = NullPool if settings.environment == "testing" else None

        engine_params = {
            "url": settings.database_url,
            "echo": settings.debug,
        }

        # Only add pooling params if not using NullPool
        if pool_class is None:
            engine_params.update({
                "pool_size": settings.database_pool_size,
                "max_overflow": settings.database_max_overflow,
                "pool_timeout": settings.database_pool_timeout,
                "pool_recycle": settings.database_pool_recycle,
                "pool_pre_ping": True,
            })
        else:
            engine_params["poolclass"] = pool_class

        _engine = create_async_engine(**engine_params)

        if pool_class is None:
            logger.info(
                f"Database engine created: pool_size={settings.database_pool_size}, "
                f"max_overflow={settings.database_max_overflow}"
            )
        else:
            logger.info("Database engine created with NullPool (testing mode)")

    return _engine


def reset_engine() -> None:
    """Reset the global engine and session maker.

    This is primarily used in tests to ensure a fresh engine is created.
    """
    global _engine, _session_maker
    _engine = None
    _session_maker = None


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Get the async session maker."""
    global _session_maker
    if _session_maker is None:
        engine = get_engine()
        _session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        logger.info("Database session maker created")
    return _session_maker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session for use in dependency injection.

    Yields:
        AsyncSession: Database session
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            # Commit on success (when no exception occurred), unless in testing mode
            # In testing mode, we let the test fixture handle rollback
            if settings.environment != "testing":
                await session.commit()
        finally:
            await session.close()


async def init_database() -> None:
    """Initialize the database connection pool."""
    engine = get_engine()
    try:
        # Test connection
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database connection: {e}")
        raise


async def close_database() -> None:
    """Close the database connection pool."""
    global _engine, _session_maker
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_maker = None
        logger.info("Database connection closed")


@asynccontextmanager
async def get_test_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a test database session with NullPool.

    Yields:
        AsyncSession: Test database session
    """
    test_engine = create_async_engine(
        settings.test_database_url,
        echo=False,
        poolclass=NullPool,
    )
    test_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with test_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
            await test_engine.dispose()


async def check_database_health() -> bool:
    """Check if the database is healthy and accessible.

    Returns:
        bool: True if database is healthy, False otherwise
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


class DatabaseSessionManager:
    """Context manager for database sessions."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the session manager.

        Args:
            session: The database session to manage
        """
        self.session = session

    async def __aenter__(self) -> AsyncSession:
        """Enter the context manager.

        Returns:
            AsyncSession: The database session
        """
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context manager.

        Args:
            exc_type: Exception type
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        try:
            if exc_type is not None:
                await self.session.rollback()
            else:
                await self.session.commit()
        finally:
            await self.session.close()
