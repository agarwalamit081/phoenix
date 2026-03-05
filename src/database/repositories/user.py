"""User repository for database operations."""

import uuid
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.logging import logger
from src.database.repositories import BaseRepository
from src.models.user import RefreshToken, User


class UserRepository(BaseRepository[User]):
    """Repository for User model operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the user repository.

        Args:
            session: The database session
        """
        super().__init__(session, User)

    async def get_by_email(self, email: str) -> User | None:
        """Get a user by email address.

        Args:
            email: The user's email address

        Returns:
            The user if found, None otherwise
        """
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_google_id(self, google_id: str) -> User | None:
        """Get a user by Google OAuth ID.

        Args:
            google_id: The Google OAuth ID

        Returns:
            The user if found, None otherwise
        """
        stmt = select(User).where(User.google_id == google_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_apple_id(self, apple_id: str) -> User | None:
        """Get a user by Apple OAuth ID.

        Args:
            apple_id: The Apple OAuth ID

        Returns:
            The user if found, None otherwise
        """
        stmt = select(User).where(User.apple_id == apple_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_oauth(self, google_id: str | None = None, apple_id: str | None = None) -> User | None:
        """Get a user by OAuth provider ID.

        Args:
            google_id: Optional Google OAuth ID
            apple_id: Optional Apple OAuth ID

        Returns:
            The user if found, None otherwise
        """
        conditions = []
        if google_id:
            conditions.append(User.google_id == google_id)
        if apple_id:
            conditions.append(User.apple_id == apple_id)

        if not conditions:
            return None

        stmt = select(User).where(or_(*conditions))
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def email_exists(self, email: str) -> bool:
        """Check if an email address is already registered.

        Args:
            email: The email address to check

        Returns:
            True if email exists, False otherwise
        """
        return await self.get_by_email(email) is not None

    async def create_user(self, data: dict[str, Any]) -> User:
        """Create a new user.

        Args:
            data: Dictionary with user field values

        Returns:
            The created user
        """
        user = await self.create(data)
        logger.info(f"Created new user: {user.email}")
        return user

    async def update_last_active(self, user_id: uuid.UUID) -> None:
        """Update the user's last active timestamp.

        Args:
            user_id: The user ID
        """
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        user = result.scalars().first()
        if user:
            user.update_last_active()

    async def get_active_users(
        self,
        offset: int = 0,
        limit: int = 100,
    ) -> list[User]:
        """Get all active users.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of active users
        """
        stmt = (
            select(User)
            .where(User.is_active == True)
            .offset(offset)
            .limit(limit)
            .order_by(User.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search_users(
        self,
        query: str,
        offset: int = 0,
        limit: int = 20,
    ) -> list[User]:
        """Search users by email or display name.

        Args:
            query: Search query string
            offset: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of matching users
        """
        search_pattern = f"%{query}%"
        stmt = (
            select(User)
            .where(
                or_(
                    User.email.ilike(search_pattern),
                    User.display_name.ilike(search_pattern),
                )
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    """Repository for RefreshToken model operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the refresh token repository.

        Args:
            session: The database session
        """
        super().__init__(session, RefreshToken)

    async def get_by_token(self, token: str) -> RefreshToken | None:
        """Get a refresh token by token string.

        Args:
            token: The token string

        Returns:
            The refresh token if found, None otherwise
        """
        stmt = select(RefreshToken).where(RefreshToken.token == token)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_valid_token(self, token: str) -> RefreshToken | None:
        """Get a valid (non-expired, non-revoked) refresh token.

        Args:
            token: The token string

        Returns:
            The valid refresh token if found, None otherwise
        """
        stmt = select(RefreshToken).where(
            RefreshToken.token == token,
            RefreshToken.is_revoked == False,
        )
        result = await self.session.execute(stmt)
        token_obj = result.scalars().first()
        if token_obj and token_obj.is_valid():
            return token_obj
        return None

    async def revoke_all_user_tokens(self, user_id: uuid.UUID) -> int:
        """Revoke all refresh tokens for a user.

        Args:
            user_id: The user ID

        Returns:
            Number of tokens revoked
        """
        stmt = (
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False,
            )
        )
        result = await self.session.execute(stmt)
        tokens = result.scalars().all()
        count = 0
        for token in tokens:
            token.revoke()
            count += 1
        logger.info(f"Revoked {count} tokens for user {user_id}")
        return count

    async def revoke_token(self, token: str) -> bool:
        """Revoke a specific refresh token.

        Args:
            token: The token string to revoke

        Returns:
            True if revoked, False if not found
        """
        token_obj = await self.get_by_token(token)
        if token_obj:
            token_obj.revoke()
            return True
        return False

    async def cleanup_expired_tokens(self) -> int:
        """Delete expired refresh tokens from the database.

        Returns:
            Number of tokens deleted
        """
        from datetime import datetime, timezone

        stmt = select(RefreshToken).where(
            RefreshToken.is_revoked == True,
            RefreshToken.expires_at < datetime.now(timezone.utc),
        )
        result = await self.session.execute(stmt)
        tokens = result.scalars().all()
        count = len(tokens)
        for token in tokens:
            await self.session.delete(token)
        logger.info(f"Cleaned up {count} expired tokens")
        return count
