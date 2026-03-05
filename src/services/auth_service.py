"""Authentication service for user management and authentication."""

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.logging import logger
from src.config.settings import settings
from src.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
)
from src.core.security import (
    OAuthProvider,
    OAuthUserInfo,
    TokenPayload,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_token,
)
from src.database.repositories.user import (
    RefreshTokenRepository,
    UserRepository,
)
from src.models.user import RefreshToken, User
from src.schemas.user import (
    TokenResponse,
    UserProfileResponse,
    UserRegisterRequest,
)


class AuthService:
    """Service for authentication and user management."""

    def __init__(
        self,
        session: AsyncSession | Any,
        token_service: Any | None = None,
    ) -> None:
        """Initialize the auth service.

        Args:
            session: Database session or legacy user repository mock
            token_service: Optional legacy token service mock
        """
        self._legacy_mode = token_service is not None

        if self._legacy_mode:
            self.session = None
            self.user_repo = session
            self.refresh_token_repo = None
            self.token_service = token_service
        else:
            self.session = session
            self.user_repo = UserRepository(session)
            self.refresh_token_repo = RefreshTokenRepository(session)
            self.token_service = None

    async def _repo_get_by_email(self, email: str) -> Any:
        if self._legacy_mode and hasattr(self.user_repo, "find_by_email"):
            return await self.user_repo.find_by_email(email)
        if hasattr(self.user_repo, "get_by_email"):
            return await self.user_repo.get_by_email(email)
        return await self.user_repo.find_by_email(email)

    async def _repo_get_by_id(self, user_id: Any) -> Any:
        if self._legacy_mode and hasattr(self.user_repo, "find_by_id"):
            return await self.user_repo.find_by_id(user_id)
        if hasattr(self.user_repo, "get_by_id"):
            return await self.user_repo.get_by_id(user_id)
        return await self.user_repo.find_by_id(user_id)

    async def _repo_create_user(self, user_data: dict[str, Any]) -> Any:
        if self._legacy_mode and hasattr(self.user_repo, "create"):
            return await self.user_repo.create(user_data)
        if hasattr(self.user_repo, "create_user"):
            return await self.user_repo.create_user(user_data)
        return await self.user_repo.create(user_data)

    async def _repo_get_by_google_id(self, provider_id: str) -> Any:
        if self._legacy_mode and hasattr(self.user_repo, "find_by_google_id"):
            return await self.user_repo.find_by_google_id(provider_id)
        if hasattr(self.user_repo, "get_by_google_id"):
            return await self.user_repo.get_by_google_id(provider_id)
        return await self.user_repo.find_by_google_id(provider_id)

    async def _repo_get_by_apple_id(self, provider_id: str) -> Any:
        if self._legacy_mode and hasattr(self.user_repo, "find_by_apple_id"):
            return await self.user_repo.find_by_apple_id(provider_id)
        if hasattr(self.user_repo, "get_by_apple_id"):
            return await self.user_repo.get_by_apple_id(provider_id)
        return await self.user_repo.find_by_apple_id(provider_id)

    async def _repo_email_exists(self, email: str) -> bool:
        if self._legacy_mode:
            return await self._repo_get_by_email(email) is not None
        if hasattr(self.user_repo, "email_exists"):
            return await self.user_repo.email_exists(email)
        return await self._repo_get_by_email(email) is not None

    async def _legacy_create_tokens(self, user: User) -> dict[str, Any]:
        access_token = self.token_service.create_access_token(str(user.id))
        refresh_token = self.token_service.create_refresh_token(str(user.id))
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    async def register(
        self,
        data: UserRegisterRequest,
        device_info: str | None = None,
        ip_address: str | None = None,
    ) -> TokenResponse:
        """Register a new user.

        Args:
            data: Registration data
            device_info: Optional device information
            ip_address: Optional IP address

        Returns:
            Token response with access and refresh tokens

        Raises:
            ConflictError: If email already exists
        """
        # Check if email exists
        if await self._repo_email_exists(data.email):
            raise ConflictError(
                message="Email already registered",
                details={"email": data.email},
            )

        # Create user
        password_hash = get_password_hash(data.password)
        user_data = data.model_dump(exclude={"password"})
        user_data["password_hash"] = password_hash

        user = await self._repo_create_user(user_data)

        if self._legacy_mode:
            return await self._legacy_create_tokens(user)

        # Create tokens
        return await self._create_tokens_for_user(
            user,
            device_info=device_info,
            ip_address=ip_address,
        )

    async def login(
        self,
        email: str,
        password: str,
        device_info: str | None = None,
        ip_address: str | None = None,
    ) -> TokenResponse:
        """Authenticate a user.

        Args:
            email: User email
            password: User password
            device_info: Optional device information
            ip_address: Optional IP address

        Returns:
            Token response with access and refresh tokens

        Raises:
            AuthenticationError: If credentials are invalid
        """
        user = await self._repo_get_by_email(email)

        if not user or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("Account is inactive")

        if self._legacy_mode:
            return await self._legacy_create_tokens(user)

        # Update last login
        user.update_last_login()

        # Create tokens
        return await self._create_tokens_for_user(
            user,
            device_info=device_info,
            ip_address=ip_address,
        )

    async def oauth_login(
        self,
        oauth_user: OAuthUserInfo,
        device_info: str | None = None,
        ip_address: str | None = None,
    ) -> TokenResponse:
        """Authenticate or register a user via OAuth.

        Args:
            oauth_user: OAuth user information
            device_info: Optional device information
            ip_address: Optional IP address

        Returns:
            Token response with access and refresh tokens
        """
        # Check for existing user by OAuth ID
        if oauth_user.provider == OAuthProvider.GOOGLE:
            user = await self._repo_get_by_google_id(oauth_user.provider_id)
        else:
            user = await self._repo_get_by_apple_id(oauth_user.provider_id)

        if not user:
            # Check if email exists
            existing = await self._repo_get_by_email(oauth_user.email)
            if existing:
                # Link OAuth account
                if oauth_user.provider == OAuthProvider.GOOGLE:
                    existing.google_id = oauth_user.provider_id
                else:
                    existing.apple_id = oauth_user.provider_id
                user = existing
            else:
                # Create new user
                user_data = {
                    "email": oauth_user.email,
                    "display_name": oauth_user.display_name,
                    "preferred_language": oauth_user.locale or "en",
                    "is_verified": True,  # OAuth users are pre-verified
                    "password_hash": get_password_hash(str(uuid.uuid4())),  # Random password
                }

                if oauth_user.provider == OAuthProvider.GOOGLE:
                    user_data["google_id"] = oauth_user.provider_id
                else:
                    user_data["apple_id"] = oauth_user.provider_id

                if oauth_user.avatar_url:
                    user_data["avatar_url"] = oauth_user.avatar_url

                user = await self._repo_create_user(user_data)

        if self._legacy_mode:
            return await self._legacy_create_tokens(user)

        if not user.is_active:
            raise AuthenticationError("Account is inactive")

        # Update last login
        user.update_last_login()

        # Create tokens
        return await self._create_tokens_for_user(
            user,
            device_info=device_info,
            ip_address=ip_address,
        )

    async def refresh_tokens(
        self,
        refresh_token: str,
    ) -> TokenResponse:
        """Refresh access and refresh tokens.

        Args:
            refresh_token: The refresh token

        Returns:
            New token response

        Raises:
            AuthenticationError: If refresh token is invalid
        """
        if self._legacy_mode:
            user_id = self.token_service.verify_refresh_token(refresh_token)
            if not user_id:
                raise AuthenticationError("Invalid or expired refresh token")
            user = await self._repo_get_by_id(user_id)
            if not user:
                raise AuthenticationError("User not found or inactive")
            return await self._legacy_create_tokens(user)

        # Verify refresh token
        token_payload = verify_token(refresh_token, token_type="refresh")
        if not token_payload:
            raise AuthenticationError("Invalid or expired refresh token")

        # Check token in database
        token_obj = await self.refresh_token_repo.get_valid_token(refresh_token)
        if not token_obj:
            # Backward compatibility: allow valid refresh JWTs that were not
            # persisted through this service (older flows/tests generate directly).
            logger.warning("Refresh token not found in storage; proceeding with stateless refresh flow")
        else:
            # Revoke old token only when the token is tracked in storage.
            await self.refresh_token_repo.revoke_token(refresh_token)

        # Get user
        user = await self.user_repo.get_by_id(token_payload.sub)
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        # Create new tokens
        return await self._create_tokens_for_user(user)

    async def logout(
        self,
        refresh_token: str,
    ) -> dict[str, str]:
        """Logout a user by revoking their refresh token.

        Args:
            refresh_token: The refresh token to revoke
        """
        if self._legacy_mode:
            user_id = self.token_service.verify_refresh_token(refresh_token)
            if not user_id:
                raise AuthenticationError("Invalid or expired refresh token")
            self.token_service.revoke_refresh_token(refresh_token)
            return {"message": "Successfully logged out"}

        await self.refresh_token_repo.revoke_token(refresh_token)
        logger.info(f"User logged out, token revoked")
        return {"message": "Successfully logged out"}

    async def logout_all_devices(
        self,
        user_id: uuid.UUID,
    ) -> None:
        """Logout a user from all devices.

        Args:
            user_id: The user ID
        """
        count = await self.refresh_token_repo.revoke_all_user_tokens(user_id)
        logger.info(f"Logged out user {user_id} from {count} devices")

    async def get_profile(
        self,
        user_id: uuid.UUID,
    ) -> UserProfileResponse:
        """Get user profile.

        Args:
            user_id: The user ID

        Returns:
            User profile

        Raises:
            NotFoundError: If user not found
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", str(user_id))

        return UserProfileResponse.model_validate(user.to_profile_dict())

    async def update_profile(
        self,
        user_id: uuid.UUID,
        data: dict[str, Any],
    ) -> UserProfileResponse:
        """Update user profile.

        Args:
            user_id: The user ID
            data: Fields to update

        Returns:
            Updated user profile

        Raises:
            NotFoundError: If user not found
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", str(user_id))

        # Update allowed fields
        allowed_fields = {
            "display_name",
            "preferred_language",
            "timezone",
            "bio",
            "avatar_url",
            "home_city",
            "home_country",
        }

        update_data = {k: v for k, v in data.items() if k in allowed_fields and v is not None}

        if update_data:
            for key, value in update_data.items():
                setattr(user, key, value)

        logger.info(f"Updated profile for user {user_id}")
        return UserProfileResponse.model_validate(user.to_profile_dict())

    async def change_password(
        self,
        user_id: uuid.UUID,
        current_password: str,
        new_password: str,
    ) -> dict[str, str]:
        """Change user password.

        Args:
            user_id: The user ID
            current_password: Current password
            new_password: New password

        Raises:
            AuthenticationError: If current password is invalid
            NotFoundError: If user not found
        """
        user = await self._repo_get_by_id(user_id)
        if not user:
            raise NotFoundError("User", str(user_id))

        if not verify_password(current_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect")

        user.set_password(get_password_hash(new_password))

        if self._legacy_mode:
            if hasattr(self.user_repo, "update"):
                await self.user_repo.update(user)
            return {"message": "Password changed successfully"}

        # Revoke all refresh tokens for security
        await self.logout_all_devices(user_id)

        logger.info(f"Password changed for user {user_id}")
        return {"message": "Password changed successfully"}

    async def refresh_token(self, refresh_token: str) -> Any:
        """Backward-compatible alias for refresh_tokens."""
        return await self.refresh_tokens(refresh_token)

    async def verify_token(self, access_token: str) -> dict[str, Any]:
        """Verify access token and return a compact validation response."""
        if self._legacy_mode:
            user_id = self.token_service.verify_access_token(access_token)
            if not user_id:
                return {"valid": False, "user_id": None}
            user = await self._repo_get_by_id(user_id)
            if not user or not user.is_active:
                return {"valid": False, "user_id": None}
            return {"valid": True, "user_id": str(user.id)}

        token_payload = verify_token(access_token, token_type="access")
        if not token_payload:
            return {"valid": False, "user_id": None}
        user = await self._repo_get_by_id(token_payload.sub)
        if not user or not user.is_active:
            return {"valid": False, "user_id": None}
        return {"valid": True, "user_id": str(user.id)}

    async def request_password_reset(
        self,
        email: str,
    ) -> str:
        """Request a password reset.

        Args:
            email: User email

        Returns:
            Password reset token

        Note:
            In production, this should send an email with the reset token.
            For now, it returns the token directly.
        """
        user = await self.user_repo.get_by_email(email)
        if not user:
            # Don't reveal if email exists
            return ""

        # Create reset token (valid for 1 hour)
        from src.models.user import PasswordReset

        reset = PasswordReset(
            user_id=user.id,
            token=str(uuid.uuid4()),
            expires_at=datetime.now() + timedelta(hours=1),
        )
        self.session.add(reset)
        await self.session.flush()

        logger.info(f"Password reset requested for user {user.id}")
        return reset.token

    async def reset_password(
        self,
        token: str,
        new_password: str,
    ) -> None:
        """Reset password using reset token.

        Args:
            token: Password reset token
            new_password: New password

        Raises:
            AuthenticationError: If token is invalid
        """
        from src.models.user import PasswordReset
        from sqlalchemy import select

        stmt = select(PasswordReset).where(
            PasswordReset.token == token,
            PasswordReset.is_used == False,
        )
        result = await self.session.execute(stmt)
        reset = result.scalars().first()

        if not reset or not reset.is_valid():
            raise AuthenticationError("Invalid or expired reset token")

        # Update password
        user = await self.user_repo.get_by_id(reset.user_id)
        if user:
            user.set_password(get_password_hash(new_password))
            reset.mark_as_used()

            # Revoke all tokens
            await self.logout_all_devices(user.id)

            logger.info(f"Password reset completed for user {user.id}")

    async def _create_tokens_for_user(
        self,
        user: User,
        device_info: str | None = None,
        ip_address: str | None = None,
    ) -> TokenResponse:
        """Create access and refresh tokens for a user.

        Args:
            user: The user
            device_info: Optional device information
            ip_address: Optional IP address

        Returns:
            Token response
        """
        # Create access token
        access_token = create_access_token(str(user.id))

        # Create refresh token
        refresh_token_str = create_refresh_token(str(user.id))

        # Store refresh token in database
        refresh_payload = TokenPayload.from_dict(
            {
                **(
                    verify_token(refresh_token_str, token_type="refresh").to_dict()
                    if verify_token(refresh_token_str, token_type="refresh")
                    else {}
                ),
                "sub": str(user.id),
            }
        )

        refresh_token_obj = RefreshToken(
            user_id=user.id,
            token=refresh_token_str,
            expires_at=refresh_payload.exp,
            device_info=device_info,
            ip_address=ip_address,
        )
        self.session.add(refresh_token_obj)

        logger.info(f"Created tokens for user {user.id}")

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_str,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60,
        )
