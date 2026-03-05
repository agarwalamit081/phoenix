"""Authentication API endpoints."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import (
    ClientIP,
    CurrentUser,
    DBSession,
    UserAgent,
)
from src.config.logging import logger
from src.schemas.user import (
    ErrorResponse,
    OAuthLoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    TokenRefreshRequest,
    TokenResponse,
    UserProfileResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserUpdateRequest,
)
from src.services.auth_service import AuthService

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    data: UserRegisterRequest,
    session: DBSession,
    request: Request,
    user_agent: UserAgent,
    client_ip: ClientIP,
) -> TokenResponse:
    """Register a new user account.

    Args:
        data: Registration data
        session: Database session
        request: HTTP request
        user_agent: User agent string
        client_ip: Client IP address

    Returns:
        Token response with access and refresh tokens
    """
    device_info = f"{user_agent or 'Unknown'} on {client_ip or 'Unknown'}"
    auth_service = AuthService(session)
    return await auth_service.register(
        data,
        device_info=device_info,
        ip_address=client_ip,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLoginRequest,
    session: DBSession,
    request: Request,
    user_agent: UserAgent,
    client_ip: ClientIP,
) -> TokenResponse:
    """Authenticate a user and return tokens.

    Args:
        data: Login data
        session: Database session
        request: HTTP request
        user_agent: User agent string
        client_ip: Client IP address

    Returns:
        Token response with access and refresh tokens
    """
    device_info = f"{user_agent or 'Unknown'} on {client_ip or 'Unknown'}"
    auth_service = AuthService(session)
    return await auth_service.login(
        data.email,
        data.password,
        device_info=device_info,
        ip_address=client_ip,
    )


@router.post("/oauth", response_model=TokenResponse)
async def oauth_login(
    data: OAuthLoginRequest,
    session: DBSession,
    request: Request,
    user_agent: UserAgent,
    client_ip: ClientIP,
) -> TokenResponse:
    """Authenticate via OAuth provider.

    Args:
        data: OAuth login data
        session: Database session
        request: HTTP request
        user_agent: User agent string
        client_ip: Client IP address

    Returns:
        Token response with access and refresh tokens
    """
    from src.core.security import (
        OAuthProvider,
        OAuthUserInfo,
        verify_apple_token,
        verify_google_token,
    )

    device_info = f"{user_agent or 'Unknown'} on {client_ip or 'Unknown'}"
    auth_service = AuthService(session)

    # Verify OAuth token based on provider
    if data.provider == "google":
        oauth_user = verify_google_token(data.token)
    elif data.provider == "apple":
        oauth_user = verify_apple_token(data.token)
    else:
        from src.core.exceptions import ValidationError

        raise ValidationError(
            message=f"Unsupported OAuth provider: {data.provider}",
            details={"provider": data.provider},
        )

    if oauth_user is None:
        from src.core.exceptions import AuthenticationError

        raise AuthenticationError("Invalid or expired OAuth token")

    return await auth_service.oauth_login(
        oauth_user,
        device_info=device_info,
        ip_address=client_ip,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    data: TokenRefreshRequest,
    session: DBSession,
) -> TokenResponse:
    """Refresh access token using refresh token.

    Args:
        data: Token refresh request
        session: Database session

    Returns:
        New token response with refreshed tokens
    """
    auth_service = AuthService(session)
    return await auth_service.refresh_tokens(data.refresh_token)


@router.post("/logout")
async def logout(
    data: TokenRefreshRequest,
    session: DBSession,
) -> dict[str, str]:
    """Logout a user by revoking their refresh token.

    Args:
        data: Token refresh request containing the refresh token to revoke
        session: Database session

    Returns:
        Logout confirmation
    """
    auth_service = AuthService(session)
    await auth_service.logout(data.refresh_token)
    return {"message": "Successfully logged out"}


@router.post("/logout-all")
async def logout_all_devices(
    user: CurrentUser,
    session: DBSession,
) -> dict[str, str]:
    """Logout a user from all devices.

    Args:
        user: Current user
        session: Database session

    Returns:
        Logout confirmation
    """
    auth_service = AuthService(session)
    await auth_service.logout_all_devices(user.id)
    return {"message": "Successfully logged out from all devices"}


@router.get("/me", response_model=UserProfileResponse)
async def get_profile(
    user: CurrentUser,
    session: DBSession,
) -> UserProfileResponse:
    """Get current user profile.

    Args:
        user: Current user
        session: Database session

    Returns:
        User profile
    """
    auth_service = AuthService(session)
    return await auth_service.get_profile(user.id)


@router.patch("/me", response_model=UserProfileResponse)
async def update_profile(
    data: UserUpdateRequest,
    user: CurrentUser,
    session: DBSession,
) -> UserProfileResponse:
    """Update current user profile.

    Args:
        data: Update data
        user: Current user
        session: Database session

    Returns:
        Updated user profile
    """
    auth_service = AuthService(session)
    update_data = data.model_dump(exclude_unset=True)
    return await auth_service.update_profile(user.id, update_data)


@router.post("/change-password")
async def change_password(
    data: PasswordChangeRequest,
    user: CurrentUser,
    session: DBSession,
) -> dict[str, str]:
    """Change user password.

    Args:
        data: Password change request
        user: Current user
        session: Database session

    Returns:
        Success message
    """
    auth_service = AuthService(session)
    await auth_service.change_password(
        user.id,
        data.current_password,
        data.new_password,
    )
    return {"message": "Password changed successfully"}


@router.post("/password-reset")
async def request_password_reset(
    data: PasswordResetRequest,
    session: DBSession,
) -> dict[str, Any]:
    """Request a password reset.

    Args:
        data: Password reset request
        session: Database session

    Returns:
        Password reset info

    Note:
        In production, this should send an email with the reset token.
    """
    auth_service = AuthService(session)
    token = await auth_service.request_password_reset(data.email)

    # In production, send email here
    # For now, return the token in development mode
    result = {"message": "If the email exists, a password reset token has been generated"}
    if token and settings.is_development:
        result["reset_token"] = token

    return result


@router.post("/password-reset/confirm")
async def reset_password(
    data: PasswordResetConfirmRequest,
    session: DBSession,
) -> dict[str, str]:
    """Reset password using reset token.

    Args:
        data: Password reset confirmation
        session: Database session

    Returns:
        Success message
    """
    auth_service = AuthService(session)
    await auth_service.reset_password(data.token, data.new_password)
    return {"message": "Password reset successfully"}


@router.get("/verify")
async def verify_token(
    user: CurrentUser,
) -> dict[str, Any]:
    """Verify that the current user's token is valid.

    Args:
        user: Current user

    Returns:
        Token validation result
    """
    return {
        "valid": True,
        "user_id": str(user.id),
        "email": user.email,
    }
