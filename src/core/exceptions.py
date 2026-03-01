"""Custom exceptions for Phoenix AI Travel Companion."""

from typing import Any

from fastapi import HTTPException, status


class PhoenixException(Exception):
    """Base exception for Phoenix application."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            code: Machine-readable error code
            details: Additional error details
        """
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(PhoenixException):
    """Authentication failed exception."""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the authentication error.

        Args:
            message: Error message
            details: Additional details
        """
        super().__init__(
            message=message,
            code="AUTHENTICATION_FAILED",
            details=details,
        )


# Alias for backward compatibility
InvalidCredentialsError = AuthenticationError
UnauthorizedError = AuthenticationError


class AuthorizationError(PhoenixException):
    """Authorization failed exception."""

    def __init__(
        self,
        message: str = "Insufficient permissions",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the authorization error.

        Args:
            message: Error message
            details: Additional details
        """
        super().__init__(
            message=message,
            code="AUTHORIZATION_FAILED",
            details=details,
        )


class ValidationError(PhoenixException):
    """Validation error exception."""

    def __init__(
        self,
        message: str = "Validation failed",
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the validation error.

        Args:
            message: Error message
            field: Field that failed validation
            details: Additional details
        """
        if field:
            details = details or {}
            details["field"] = field

        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=details,
        )


class NotFoundError(PhoenixException):
    """Resource not found exception."""

    def __init__(
        self,
        resource: str,
        identifier: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the not found error.

        Args:
            resource: Type of resource (e.g., "User", "Itinerary")
            identifier: Resource identifier
            details: Additional details
        """
        message = f"{resource} not found"
        if identifier:
            message += f": {identifier}"

        details = details or {}
        if identifier:
            details["identifier"] = identifier

        super().__init__(
            message=message,
            code="NOT_FOUND",
            details=details | {"resource": resource},
        )


class ConflictError(PhoenixException):
    """Resource conflict exception."""

    def __init__(
        self,
        message: str = "Resource conflict",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the conflict error.

        Args:
            message: Error message
            details: Additional details
        """
        super().__init__(
            message=message,
            code="CONFLICT",
            details=details,
        )


class RateLimitError(PhoenixException):
    """Rate limit exceeded exception."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the rate limit error.

        Args:
            message: Error message
            retry_after: Seconds until retry is allowed
            details: Additional details
        """
        details = details or {}
        if retry_after is not None:
            details["retry_after"] = retry_after

        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            details=details,
        )


class ExternalServiceError(PhoenixException):
    """External service error exception."""

    def __init__(
        self,
        service: str,
        message: str = "External service error",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the external service error.

        Args:
            service: Name of the external service
            message: Error message
            details: Additional details
        """
        details = details or {}
        details["service"] = service

        super().__init__(
            message=message,
            code="EXTERNAL_SERVICE_ERROR",
            details=details,
        )


class DatabaseError(PhoenixException):
    """Database error exception."""

    def __init__(
        self,
        message: str = "Database error",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the database error.

        Args:
            message: Error message
            details: Additional details
        """
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            details=details,
        )


# HTTP exception helpers
def get_http_exception(exc: PhoenixException) -> HTTPException:
    """Convert a PhoenixException to HTTPException.

    Args:
        exc: The PhoenixException

    Returns:
        HTTPException with appropriate status code
    """
    status_codes: dict[str, int] = {
        "AUTHENTICATION_FAILED": status.HTTP_401_UNAUTHORIZED,
        "AUTHORIZATION_FAILED": status.HTTP_403_FORBIDDEN,
        "VALIDATION_ERROR": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "CONFLICT": status.HTTP_409_CONFLICT,
        "RATE_LIMIT_EXCEEDED": status.HTTP_429_TOO_MANY_REQUESTS,
        "EXTERNAL_SERVICE_ERROR": status.HTTP_502_BAD_GATEWAY,
        "DATABASE_ERROR": status.HTTP_500_INTERNAL_SERVER_ERROR,
    }

    status_code = status_codes.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    return HTTPException(
        status_code=status_code,
        detail={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        },
    )
