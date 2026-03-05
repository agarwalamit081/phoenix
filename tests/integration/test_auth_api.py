"""Integration tests for authentication API."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


class TestAuthAPI:
    """Tests for authentication API endpoints."""

    def test_register_success(
        self,
        async_client,
    ) -> None:
        """Test successful user registration."""
        response = async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePass123",
                "display_name": "New User",
                "preferred_language": "en",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email(
        self,
        async_client,
    ) -> None:
        """Test registration with duplicate email."""
        # First register a user
        response = async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@example.com",
                "password": "SecurePass123",
                "display_name": "First User",
            },
        )
        assert response.status_code == 201

        # Try to register again with same email
        response = async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@example.com",
                "password": "DifferentPass123",
                "display_name": "Duplicate User",
            },
        )

        assert response.status_code == 409  # Conflict

    def test_register_weak_password(
        self,
        async_client,
    ) -> None:
        """Test registration with weak password."""
        response = async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "weak",  # Missing uppercase, digit
                "display_name": "Test User",
            },
        )

        assert response.status_code == 422  # Validation Error

    def test_login_success(
        self,
        async_client,
    ) -> None:
        """Test successful login."""
        # First register a user
        response = async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "loginuser@example.com",
                "password": "CorrectPassword123",
                "display_name": "Login User",
            },
        )
        assert response.status_code == 201

        # Now login with the correct password
        response = async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "loginuser@example.com",
                "password": "CorrectPassword123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_wrong_password(
        self,
        async_client,
    ) -> None:
        """Test login with wrong password."""
        # First register a user with a known password
        response = async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrongpass@example.com",
                "password": "CorrectPassword123",
                "display_name": "Test User",
            },
        )
        assert response.status_code == 201

        # Try to login with wrong password
        response = async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "wrongpass@example.com",
                "password": "WrongPassword123",
            },
        )

        assert response.status_code == 401  # Unauthorized

    def test_login_nonexistent_user(
        self,
        async_client,
    ) -> None:
        """Test login with non-existent user."""
        response = async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "Anypassword123",
            },
        )

        assert response.status_code == 401  # Unauthorized

    def test_refresh_token(
        self,
        async_client,
    ) -> None:
        """Test token refresh."""
        # First register a user
        response = async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "refreshuser@example.com",
                "password": "RefreshPassword123",
                "display_name": "Refresh User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        refresh_token = data["refresh_token"]

        # Now use the refresh token to get new tokens
        response = async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_invalid_token(
        self,
        async_client,
    ) -> None:
        """Test refresh with invalid token."""
        response = async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )

        assert response.status_code == 401  # Unauthorized

    def test_get_profile(
        self,
        async_client,
    ) -> None:
        """Test getting user profile."""
        # First register a user
        response = async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "profileuser@example.com",
                "password": "ProfilePassword123",
                "display_name": "Profile User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        access_token = data["access_token"]

        # Now get the profile
        response = async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "profileuser@example.com"
        assert data["display_name"] == "Profile User"

    def test_get_profile_unauthorized(
        self,
        async_client,
    ) -> None:
        """Test getting profile without authentication."""
        response = async_client.get("/api/v1/auth/me")

        assert response.status_code == 401  # Unauthorized

    def test_logout(
        self,
        async_client,
    ) -> None:
        """Test logout."""
        # First register a user
        response = async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "logoutuser@example.com",
                "password": "LogoutPassword123",
                "display_name": "Logout User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        refresh_token = data["refresh_token"]

        response = async_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_change_password(
        self,
        async_client,
    ) -> None:
        """Test changing password."""
        # First register a user
        response = async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "changepass@example.com",
                "password": "OldPassword123",
                "display_name": "Change Pass User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        access_token = data["access_token"]

        response = async_client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "current_password": "OldPassword123",
                "new_password": "NewSecurePass123",
            },
        )

        # Should succeed with correct password
        assert response.status_code == 200

    def test_verify_token_endpoint(
        self,
        async_client,
    ) -> None:
        """Test token verification endpoint."""
        # First register a user
        response = async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "verifyuser@example.com",
                "password": "VerifyPassword123",
                "display_name": "Verify User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        access_token = data["access_token"]

        response = async_client.get(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert "user_id" in data
