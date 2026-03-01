"""API dependencies and utilities for Phoenix AI Travel Companion."""

from src.api.dependencies import (
    AdminUser,
    ClientIP,
    CurrentUser,
    DBSession,
    OptionalCurrentUser,
    TokenPayload,
    UserAgent,
    VerifiedUser,
    get_client_ip,
    get_current_user,
    get_db_session,
    get_optional_current_user,
    get_optional_token,
    get_required_token,
    get_user_agent,
    require_admin_user,
    require_verified_user,
)

__all__ = [
    # Dependencies
    "get_db_session",
    "get_optional_token",
    "get_required_token",
    "get_current_user",
    "get_optional_current_user",
    "require_verified_user",
    "require_admin_user",
    "get_client_ip",
    "get_user_agent",
    # Type aliases
    "DBSession",
    "CurrentUser",
    "OptionalCurrentUser",
    "TokenPayload",
    "VerifiedUser",
    "AdminUser",
    "ClientIP",
    "UserAgent",
]
