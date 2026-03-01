"""Core security and middleware for Phoenix AI Travel Companion."""

from src.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DatabaseError,
    ExternalServiceError,
    NotFoundError,
    PhoenixException,
    RateLimitError,
    ValidationError,
    get_http_exception,
)
from src.core.middleware import (
    ErrorHandlingMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
    setup_cors,
)
from src.core.security import (
    OAuthProvider,
    OAuthUserInfo,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    get_token_expiry,
    is_token_expired,
    verify_apple_token,
    verify_google_token,
    verify_password,
    verify_token,
)

__all__ = [
    # Security
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "decode_token",
    "get_token_expiry",
    "is_token_expired",
    "OAuthProvider",
    "OAuthUserInfo",
    "verify_google_token",
    "verify_apple_token",
    # Exceptions
    "PhoenixException",
    "AuthenticationError",
    "AuthorizationError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "RateLimitError",
    "ExternalServiceError",
    "DatabaseError",
    "get_http_exception",
    # Middleware
    "RequestContextMiddleware",
    "ErrorHandlingMiddleware",
    "RateLimitMiddleware",
    "setup_cors",
]
