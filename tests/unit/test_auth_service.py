"""Unit tests for authentication service."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.exceptions import (
    ConflictError,
    InvalidCredentialsError,
    UnauthorizedError,
)
from src.core.security import get_password_hash
from src.models.user import User
from src.services.auth_service import AuthService
from src.schemas.user import UserRegisterRequest


@pytest.mark.asyncio
class TestAuthService:
    """Tests for AuthService."""

    async def test_register_success(self) -> None:
        """Test successful user registration."""
        mock_repo = AsyncMock()
        mock_repo.find_by_email.return_value = None
        mock_repo.create.return_value = User(
            id=uuid.uuid4(),
            email="test@example.com",
            password_hash=get_password_hash("Password123"),
            display_name="Test User",
            preferred_language="en",
            is_active=True,
            is_verified=False,
            created_at=datetime.now(timezone.utc),
        )

        mock_token_service = MagicMock()
        mock_token_service.create_access_token.return_value = "access-token"
        mock_token_service.create_refresh_token.return_value = "refresh-token"

        auth_service = AuthService(mock_repo, mock_token_service)

        request = UserRegisterRequest(
            email="test@example.com",
            password="Password123",
            display_name="Test User",
            preferred_language="en",
        )

        result = await auth_service.register(request)

        assert result["access_token"] == "access-token"
        assert result["refresh_token"] == "refresh-token"
        mock_repo.create.assert_called_once()

    async def test_register_duplicate_email(self) -> None:
        """Test registration with duplicate email."""
        existing_user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            password_hash="hash",
            display_name="Existing User",
        )
        mock_repo = AsyncMock()
        mock_repo.find_by_email.return_value = existing_user

        mock_token_service = MagicMock()

        auth_service = AuthService(mock_repo, mock_token_service)

        request = UserRegisterRequest(
            email="test@example.com",
            password="Password123",
            display_name="Test User",
        )

        with pytest.raises(ConflictError):
            await auth_service.register(request)

    async def test_login_success(self) -> None:
        """Test successful login."""
        password = "Password123"
        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            password_hash=get_password_hash(password),
            display_name="Test User",
            is_active=True,
        )

        mock_repo = AsyncMock()
        mock_repo.find_by_email.return_value = user

        mock_token_service = MagicMock()
        mock_token_service.create_access_token.return_value = "access-token"
        mock_token_service.create_refresh_token.return_value = "refresh-token"

        auth_service = AuthService(mock_repo, mock_token_service)

        result = await auth_service.login("test@example.com", password)

        assert result["access_token"] == "access-token"
        assert result["refresh_token"] == "refresh-token"

    async def test_login_wrong_password(self) -> None:
        """Test login with wrong password."""
        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            password_hash=get_password_hash("Password123"),
            display_name="Test User",
            is_active=True,
        )

        mock_repo = AsyncMock()
        mock_repo.find_by_email.return_value = user

        mock_token_service = MagicMock()

        auth_service = AuthService(mock_repo, mock_token_service)

        with pytest.raises(InvalidCredentialsError):
            await auth_service.login("test@example.com", "WrongPassword")

    async def test_login_nonexistent_user(self) -> None:
        """Test login with non-existent user."""
        mock_repo = AsyncMock()
        mock_repo.find_by_email.return_value = None

        mock_token_service = MagicMock()

        auth_service = AuthService(mock_repo, mock_token_service)

        with pytest.raises(InvalidCredentialsError):
            await auth_service.login("nonexistent@example.com", "Password123")

    async def test_login_inactive_user(self) -> None:
        """Test login with inactive user."""
        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            password_hash=get_password_hash("Password123"),
            display_name="Test User",
            is_active=False,
        )

        mock_repo = AsyncMock()
        mock_repo.find_by_email.return_value = user

        mock_token_service = MagicMock()

        auth_service = AuthService(mock_repo, mock_token_service)

        with pytest.raises(InvalidCredentialsError):
            await auth_service.login("test@example.com", "Password123")

    async def test_refresh_token_success(self) -> None:
        """Test successful token refresh."""
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="test@example.com",
            password_hash="hash",
            display_name="Test User",
            is_active=True,
        )

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = user

        mock_token_service = MagicMock()
        mock_token_service.verify_refresh_token.return_value = str(user_id)
        mock_token_service.create_access_token.return_value = "new-access"
        mock_token_service.create_refresh_token.return_value = "new-refresh"

        auth_service = AuthService(mock_repo, mock_token_service)

        result = await auth_service.refresh_token("valid-refresh-token")

        assert result["access_token"] == "new-access"
        assert result["refresh_token"] == "new-refresh"

    async def test_refresh_invalid_token(self) -> None:
        """Test refresh with invalid token."""
        mock_repo = AsyncMock()
        mock_token_service = MagicMock()
        mock_token_service.verify_refresh_token.return_value = None

        auth_service = AuthService(mock_repo, mock_token_service)

        with pytest.raises(UnauthorizedError):
            await auth_service.refresh_token("invalid-token")

    async def test_verify_token_success(self) -> None:
        """Test successful token verification."""
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="test@example.com",
            password_hash="hash",
            display_name="Test User",
            is_active=True,
        )

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = user

        mock_token_service = MagicMock()
        mock_token_service.verify_access_token.return_value = str(user_id)

        auth_service = AuthService(mock_repo, mock_token_service)

        result = await auth_service.verify_token("valid-access-token")

        assert result["valid"] is True
        assert result["user_id"] == str(user_id)

    async def test_verify_token_invalid(self) -> None:
        """Test verification with invalid token."""
        mock_repo = AsyncMock()
        mock_token_service = MagicMock()
        mock_token_service.verify_access_token.return_value = None

        auth_service = AuthService(mock_repo, mock_token_service)

        result = await auth_service.verify_token("invalid-token")

        assert result["valid"] is False
        assert result["user_id"] is None

    async def test_logout_success(self) -> None:
        """Test successful logout."""
        user_id = uuid.uuid4()

        mock_repo = AsyncMock()
        mock_token_service = MagicMock()
        mock_token_service.verify_refresh_token.return_value = str(user_id)
        mock_token_service.revoke_refresh_token.return_value = None

        auth_service = AuthService(mock_repo, mock_token_service)

        result = await auth_service.logout("valid-refresh-token")

        assert result["message"] == "Successfully logged out"

    async def test_change_password_success(self) -> None:
        """Test successful password change."""
        password = "OldPassword123"
        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            password_hash=get_password_hash(password),
            display_name="Test User",
            is_active=True,
        )

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = user

        mock_token_service = MagicMock()

        auth_service = AuthService(mock_repo, mock_token_service)

        result = await auth_service.change_password(
            str(user.id), password, "NewPassword123"
        )

        assert result["message"] == "Password changed successfully"
        mock_repo.update.assert_called_once()

    async def test_change_password_wrong_current(self) -> None:
        """Test password change with wrong current password."""
        user = User(
            id=uuid.uuid4(),
            email="test@example.com",
            password_hash=get_password_hash("OldPassword123"),
            display_name="Test User",
            is_active=True,
        )

        mock_repo = AsyncMock()
        mock_repo.find_by_id.return_value = user

        mock_token_service = MagicMock()

        auth_service = AuthService(mock_repo, mock_token_service)

        with pytest.raises(InvalidCredentialsError):
            await auth_service.change_password(
                str(user.id), "WrongPassword", "NewPassword123"
            )

    async def test_oauth_login_new_user(self) -> None:
        """Test OAuth login for new user."""
        mock_repo = AsyncMock()
        mock_repo.find_by_google_id.return_value = None
        mock_repo.find_by_email.return_value = None
        mock_repo.create.return_value = User(
            id=uuid.uuid4(),
            email="oauth@example.com",
            password_hash="",
            display_name="OAuth User",
            google_id="google-12345",
            is_active=True,
            is_verified=True,
        )

        mock_token_service = MagicMock()
        mock_token_service.create_access_token.return_value = "access-token"
        mock_token_service.create_refresh_token.return_value = "refresh-token"

        auth_service = AuthService(mock_repo, mock_token_service)

        oauth_info = MagicMock()
        oauth_info.provider = "google"
        oauth_info.provider_id = "google-12345"
        oauth_info.email = "oauth@example.com"
        oauth_info.display_name = "OAuth User"

        result = await auth_service.oauth_login(oauth_info)

        assert result["access_token"] == "access-token"
        mock_repo.create.assert_called_once()

    async def test_oauth_login_existing_user(self) -> None:
        """Test OAuth login for existing user."""
        user = User(
            id=uuid.uuid4(),
            email="oauth@example.com",
            password_hash="",
            display_name="OAuth User",
            google_id="google-12345",
            is_active=True,
            is_verified=True,
        )

        mock_repo = AsyncMock()
        mock_repo.find_by_google_id.return_value = user

        mock_token_service = MagicMock()
        mock_token_service.create_access_token.return_value = "access-token"
        mock_token_service.create_refresh_token.return_value = "refresh-token"

        auth_service = AuthService(mock_repo, mock_token_service)

        oauth_info = MagicMock()
        oauth_info.provider = "google"
        oauth_info.provider_id = "google-12345"

        result = await auth_service.oauth_login(oauth_info)

        assert result["access_token"] == "access-token"
        mock_repo.create.assert_not_called()
