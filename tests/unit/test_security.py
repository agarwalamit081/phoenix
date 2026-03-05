"""Unit tests for security functions."""

import uuid
from datetime import datetime, timedelta

import pytest
from jose import jwt
from passlib.context import CryptContext

from src.config.settings import settings
from src.core.security import (
    OAuthProvider,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    is_token_expired,
    verify_password,
    verify_token,
)


class TestPasswordHashing:
    """Tests for password hashing and verification."""

    def test_hash_password(self) -> None:
        """Test password hashing."""
        password = "SecurePassword123"
        hashed = get_password_hash(password)

        assert hashed != password
        assert len(hashed) == 60  # bcrypt hash length
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_verify_correct_password(self) -> None:
        """Test verifying correct password."""
        password = "SecurePassword123"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_verify_incorrect_password(self) -> None:
        """Test verifying incorrect password."""
        password = "SecurePassword123"
        wrong_password = "WrongPassword123"
        hashed = get_password_hash(password)

        assert verify_password(wrong_password, hashed) is False

    def test_hash_different_passwords_different_hashes(self) -> None:
        """Test that different passwords produce different hashes."""
        password1 = "Password123"
        password2 = "Password456"

        hash1 = get_password_hash(password1)
        hash2 = get_password_hash(password2)

        assert hash1 != hash2

    def test_hash_same_password_same_hash(self) -> None:
        """Test that same password produces consistent hash."""
        password = "Password123"

        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        # Note: bcrypt includes salt, so hashes will be different
        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestTokenGeneration:
    """Tests for JWT token generation and verification."""

    def test_create_access_token(self) -> None:
        """Test access token creation."""
        user_id = uuid.uuid4()
        token = create_access_token(str(user_id))

        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_valid_token(self) -> None:
        """Test verifying a valid token."""
        user_id = uuid.uuid4()
        token = create_access_token(str(user_id))

        payload = verify_token(token)
        assert payload is not None
        assert payload.sub == str(user_id)
        assert payload.type == "access"

    def test_verify_invalid_token(self) -> None:
        """Test verifying an invalid token."""
        invalid_token = "invalid.token.here"
        payload = verify_token(invalid_token)
        assert payload is None

    def test_access_token_expiration(self) -> None:
        """Test that access token expires correctly."""
        user_id = uuid.uuid4()
        token = create_access_token(str(user_id), expires_delta=timedelta(seconds=1))

        # Token should be valid immediately
        payload = verify_token(token)
        assert payload is not None

        # Wait for expiration
        import time

        time.sleep(2)

        # Token should now be expired
        assert is_token_expired(token) is True

    def test_refresh_token_longer_expiration(self) -> None:
        """Test that refresh token has longer expiration."""
        user_id = uuid.uuid4()

        access_token = create_access_token(str(user_id))
        refresh_token = create_refresh_token(str(user_id))

        access_payload = verify_token(access_token)
        refresh_payload = verify_token(refresh_token)

        assert access_payload is not None
        assert refresh_payload is not None

        # Refresh token should expire later than access token
        access_expires = access_payload.exp
        refresh_expires = refresh_payload.exp

        assert refresh_expires > access_expires

    def test_token_type_differentiation(self) -> None:
        """Test that access and refresh tokens have different types."""
        user_id = uuid.uuid4()

        access_token = create_access_token(str(user_id))
        refresh_token = create_refresh_token(str(user_id))

        access_payload = verify_token(access_token)
        refresh_payload = verify_token(refresh_token)

        assert access_payload.type == "access"
        assert refresh_payload.type == "refresh"

    def test_verify_token_by_type(self) -> None:
        """Test verifying token by type."""
        user_id = uuid.uuid4()

        access_token = create_access_token(str(user_id))
        refresh_token = create_refresh_token(str(user_id))

        # Access token should verify as access
        access_payload = verify_token(access_token, token_type="access")
        assert access_payload is not None
        assert access_payload.type == "access"

        # Access token should NOT verify as refresh
        refresh_payload = verify_token(access_token, token_type="refresh")
        assert refresh_payload is None


class TestTokenExpiration:
    """Tests for token expiration checking."""

    def test_is_token_expired_valid(self) -> None:
        """Test checking non-expired token."""
        user_id = uuid.uuid4()
        token = create_access_token(str(user_id))

        assert is_token_expired(token) is False

    def test_is_token_expired_invalid(self) -> None:
        """Test checking expired token."""
        # Create a token that's already expired
        user_id = uuid.uuid4()
        token = create_access_token(
            str(user_id),
            expires_delta=timedelta(seconds=-1),
        )

        assert is_token_expired(token) is True

    def test_get_token_expiry(self) -> None:
        """Test getting token expiry time."""
        from src.core.security import get_token_expiry

        user_id = uuid.uuid4()
        token = create_access_token(str(user_id))

        expiry = get_token_expiry(token)
        assert expiry is not None
        assert expiry > datetime.now()

    def test_get_token_expiry_invalid(self) -> None:
        """Test getting expiry for invalid token."""
        from src.core.security import get_token_expiry

        invalid_token = "invalid.token"
        expiry = get_token_expiry(invalid_token)
        assert expiry is None


class TestOAuth:
    """Tests for OAuth functionality."""

    def test_oauth_provider_constants(self) -> None:
        """Test OAuth provider constants."""
        assert OAuthProvider.GOOGLE == "google"
        assert OAuthProvider.APPLE == "apple"

    def test_oauth_user_info(self) -> None:
        """Test OAuth user info creation."""
        from src.core.security import OAuthUserInfo

        user_info = OAuthUserInfo(
            provider=OAuthProvider.GOOGLE,
            provider_id="google-12345",
            email="user@example.com",
            display_name="Test User",
            avatar_url="https://example.com/avatar.jpg",
            locale="en",
        )

        assert user_info.provider == "google"
        assert user_info.email == "user@example.com"
        assert user_info.display_name == "Test User"

    def test_oauth_user_info_to_dict(self) -> None:
        """Test converting OAuth user info to dict."""
        from src.core.security import OAuthUserInfo

        user_info = OAuthUserInfo(
            provider=OAuthProvider.GOOGLE,
            provider_id="google-12345",
            email="user@example.com",
        )

        data = user_info.to_dict()
        assert data["provider"] == "google"
        assert data["email"] == "user@example.com"
        assert data["provider_id"] == "google-12345"
