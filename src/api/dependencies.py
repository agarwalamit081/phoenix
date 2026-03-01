"""FastAPI dependencies for dependency injection."""

from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.core.exceptions import AuthenticationError, AuthorizationError
from src.core.security import TokenPayload, verify_token
from src.database import get_session
from src.database.repositories.user import UserRepository
from src.models.user import User

# HTTP Bearer token scheme
http_bearer = HTTPBearer(auto_error=False)


async def get_db_session() -> AsyncSession:
    """Get database session dependency.

    Yields:
        AsyncSession: Database session
    """
    async for session in get_session():
        yield session


async def get_optional_token(
    authorization: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)],
) -> TokenPayload | None:
    """Get optional token from Authorization header.

    Args:
        authorization: Optional authorization credentials

    Returns:
        TokenPayload if valid token provided, None otherwise
    """
    if authorization is None:
        return None

    token = authorization.credentials
    payload = verify_token(token, token_type="access")

    if payload is None:
        raise AuthenticationError("Invalid or expired token")

    return payload


async def get_required_token(
    authorization: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)],
) -> TokenPayload:
    """Get required token from Authorization header.

    Args:
        authorization: Authorization credentials

    Returns:
        TokenPayload

    Raises:
        AuthenticationError: If no valid token provided
    """
    if authorization is None:
        raise AuthenticationError("Not authenticated")

    token = authorization.credentials
    payload = verify_token(token, token_type="access")

    if payload is None:
        raise AuthenticationError("Invalid or expired token")

    return payload


async def get_current_user(
    token: Annotated[TokenPayload, Depends(get_required_token)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Get the current authenticated user.

    Args:
        token: JWT token payload
        session: Database session

    Returns:
        The current user

    Raises:
        AuthenticationError: If user not found
    """
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(token.sub)

    if user is None:
        raise AuthenticationError("User not found")

    if not user.is_active:
        raise AuthenticationError("User account is inactive")

    # Update last active timestamp
    await user_repo.update_last_active(user.id)

    return user


async def get_optional_current_user(
    token: Annotated[TokenPayload | None, Depends(get_optional_token)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User | None:
    """Get the current user if authenticated.

    Args:
        token: Optional JWT token payload
        session: Database session

    Returns:
        The current user if authenticated, None otherwise
    """
    if token is None:
        return None

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(token.sub)

    if user is None or not user.is_active:
        return None

    return user


def require_verified_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Require user to be verified.

    Args:
        user: The current user

    Returns:
        The verified user

    Raises:
        AuthorizationError: If user is not verified
    """
    if not user.is_verified:
        raise AuthorizationError("Email verification required")

    return user


def require_admin_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Require user to be an admin.

    Args:
        user: The current user

    Returns:
        The admin user

    Raises:
        AuthorizationError: If user is not an admin

    Note:
        This is a placeholder for future admin functionality.
        Implement admin role checking in User model.
    """
    if not getattr(user, "is_admin", False):
        raise AuthorizationError("Admin privileges required")

    return user


def get_client_ip(
    x_forwarded_for: Annotated[str | None, Header(alias="X-Forwarded-For")] = None,
    x_real_ip: Annotated[str | None, Header(alias="X-Real-IP")] = None,
) -> str:
    """Get the client's IP address from headers.

    Args:
        x_forwarded_for: X-Forwarded-For header value
        x_real_ip: X-Real-IP header value

    Returns:
        The client IP address
    """
    if x_forwarded_for:
        # X-Forwarded-For can contain multiple IPs, first one is the client
        return x_forwarded_for.split(",")[0].strip()
    elif x_real_ip:
        return x_real_ip
    else:
        return "unknown"


def get_user_agent(
    user_agent: Annotated[str | None, Header(alias="User-Agent")] = None,
) -> str | None:
    """Get the user agent from headers.

    Args:
        user_agent: User-Agent header value

    Returns:
        The user agent string or None
    """
    return user_agent


# Type aliases for common dependencies
DBSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalCurrentUser = Annotated[User | None, Depends(get_optional_current_user)]
VerifiedUser = Annotated[User, Depends(require_verified_user)]
AdminUser = Annotated[User, Depends(require_admin_user)]
TokenPayload = Annotated[TokenPayload, Depends(get_required_token)]
ClientIP = Annotated[str, Depends(get_client_ip)]
UserAgent = Annotated[str | None, Depends(get_user_agent)]
