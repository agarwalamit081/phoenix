"""Middleware for FastAPI application."""

import time
import uuid
from typing import Any, Callable

from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from src.config.logging import logger
from src.config.settings import settings
from src.core.exceptions import RateLimitError


# ============================================================================
# Pure ASGI Middleware (No Event Loop Issues)
# ============================================================================


class RequestContextASGIMiddleware:
    """ASGI middleware to add request ID and timing information.

    This pure ASGI middleware avoids the event loop issues of BaseHTTPMiddleware.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialize the middleware.

        Args:
            app: The ASGI application
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process the request and add context.

        Args:
            scope: ASGI scope
            receive: ASGI receive callable
            send: ASGI send callable
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Store request ID in scope for access in routes
        scope["request_id"] = request_id

        # Log request start
        start_time = time.time()
        method = scope["method"]
        path = scope["path"]

        logger.bind(request_id=request_id).info(
            f"Request started: {method} {path}"
        )

        # Wrap send to intercept and modify response
        status_code = None

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                # Add custom headers
                headers = message.get("headers", [])
                headers.append((b"X-Request-ID", request_id.encode()))

                # Calculate duration and add process time header
                duration = time.time() - start_time
                headers.append((b"X-Process-Time", str(duration).encode()))

                message["headers"] = headers
            elif message["type"] == "http.response.body":
                # Log completion
                duration = time.time() - start_time
                if status_code:
                    logger.bind(request_id=request_id).info(
                        f"Request completed: {method} {path} "
                        f"- Status {status_code} - {duration:.3f}s"
                    )

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            # Calculate duration for failed requests
            duration = time.time() - start_time

            # Log error - escape curly braces in exception message
            exc_str = str(e).replace("{", "{{").replace("}", "}}")
            logger.bind(request_id=request_id).error(
                f"Request failed: {method} {path} "
                f"- {type(e).__name__}: {exc_str} - {duration:.3f}s"
            )
            # Re-raise for ErrorHandlingASGIMiddleware to handle
            raise


class ErrorHandlingASGIMiddleware:
    """ASGI middleware for global error handling.

    This pure ASGI middleware avoids the event loop issues of BaseHTTPMiddleware.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialize the middleware.

        Args:
            app: The ASGI application
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process the request and handle errors.

        Args:
            scope: ASGI scope
            receive: ASGI receive callable
            send: ASGI send callable
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Create a wrapper for the send callable to track if a response was sent
        response_sent = False

        async def send_wrapper(message: dict) -> None:
            nonlocal response_sent
            if message["type"] == "http.response.start":
                response_sent = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            # Import here to avoid circular dependencies
            from src.core.exceptions import get_http_exception, PhoenixException
            from fastapi import HTTPException
            from src.config.settings import settings

            # Don't handle HTTPException - let it propagate
            if isinstance(e, HTTPException):
                if not response_sent:
                    # Send HTTPException response directly using ASGI messages
                    await send({
                        "type": "http.response.start",
                        "status": e.status_code,
                        "headers": [[b"content-type", b"application/json"]],
                    })
                    await send({
                        "type": "http.response.body",
                        "body": f'{{"detail":"{e.detail}"}}'.encode(),
                    })
                # If response was sent, can't do anything
                return

            if not response_sent:
                # Only send error response if no response was sent yet
                if isinstance(e, PhoenixException):
                    # Convert Phoenix exceptions to HTTP exceptions
                    http_exc = get_http_exception(e)
                    # Send the error response directly using ASGI messages
                    import json
                    await send({
                        "type": "http.response.start",
                        "status": http_exc.status_code,
                        "headers": [[b"content-type", b"application/json"]],
                    })
                    await send({
                        "type": "http.response.body",
                        "body": json.dumps({"detail": http_exc.detail}).encode(),
                    })
                else:
                    # For other exceptions, return 500 error
                    # Escape curly braces in exception message to avoid format string errors
                    exc_str = str(e).replace("{", "{{").replace("}", "}}")
                    logger.error(f"Unhandled exception: {exc_str}", exc_info=True)

                    import json
                    await send({
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [[b"content-type", b"application/json"]],
                    })
                    await send({
                        "type": "http.response.body",
                        "body": json.dumps({
                            "code": "INTERNAL_SERVER_ERROR",
                            "message": "An unexpected error occurred",
                            "details": {"traceback": str(e)} if settings.debug else None,
                        }).encode(),
                    })
            # If response was already sent, can't send another response
            # RequestContextASGIMiddleware already logged it


# ============================================================================
# Backward Compatible BaseHTTPMiddleware Wrappers (for production)
# These can still be used outside of testing contexts
# ============================================================================


class RequestContextMiddleware(BaseHTTPMiddleware):
    """BaseHTTPMiddleware wrapper for request context (deprecated for testing).

    Note: This middleware has known compatibility issues with pytest-asyncio.
    Use RequestContextASGIMiddleware instead in test environments.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add context.

        Args:
            request: The incoming request
            call_next: The next middleware/route handler

        Returns:
            The response from the next handler
        """
        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Add request ID to request state
        request.state.request_id = request_id

        # Log request start
        start_time = time.time()

        # Process request
        logger.bind(request_id=request_id).info(
            f"Request started: {request.method} {request.url.path}"
        )

        try:
            response = await call_next(request)

            # Calculate duration
            duration = time.time() - start_time

            # Add custom headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(duration)

            # Log completion
            logger.bind(request_id=request_id).info(
                f"Request completed: {request.method} {request.url.path} "
                f"- Status {response.status_code} - {duration:.3f}s"
            )

            return response

        except Exception as e:
            # Calculate duration for failed requests
            duration = time.time() - start_time

            # Log error - escape curly braces in exception message
            exc_str = str(e).replace("{", "{{").replace("}", "}}")
            logger.bind(request_id=request_id).error(
                f"Request failed: {request.method} {request.url.path} "
                f"- {type(e).__name__}: {exc_str} - {duration:.3f}s"
            )
            raise


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """BaseHTTPMiddleware wrapper for error handling (deprecated for testing).

    Note: This middleware has known compatibility issues with pytest-asyncio.
    Use ErrorHandlingASGIMiddleware instead in test environments.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and handle errors.

        Args:
            request: The incoming request
            call_next: The next middleware/route handler

        Returns:
            The response from the next handler

        Raises:
            Exception: Re-raises unhandled exceptions
        """
        try:
            return await call_next(request)
        except Exception as e:
            # Import here to avoid circular dependencies
            from src.core.exceptions import get_http_exception, PhoenixException

            if isinstance(e, PhoenixException):
                # Convert Phoenix exceptions to HTTP exceptions
                http_exc = get_http_exception(e)
                raise http_exc
            else:
                # Re-raise other exceptions
                raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests."""

    def __init__(
        self,
        app: ASGIApp,
        redis_client: Any | None = None,
    ) -> None:
        """Initialize the rate limit middleware.

        Args:
            app: The ASGI application
            redis_client: Optional Redis client for distributed rate limiting
        """
        super().__init__(app)
        self.redis_client = redis_client
        self.enabled = settings.rate_limit_enabled
        self.requests = settings.rate_limit_requests
        self.period = settings.rate_limit_period
        self.prefix = settings.rate_limit_redis_prefix

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and enforce rate limits.

        Args:
            request: The incoming request
            call_next: The next middleware/route handler

        Returns:
            The response from the next handler

        Raises:
            RateLimitError: If rate limit is exceeded
        """
        if not self.enabled:
            return await call_next(request)

        # Get client identifier (IP address or user ID if authenticated)
        client_id = self._get_client_id(request)

        # Check rate limit
        if not await self._check_rate_limit(client_id):
            logger.warning(f"Rate limit exceeded for client: {client_id}")
            raise RateLimitError(
                message="Rate limit exceeded",
                retry_after=self.period,
            )

        return await call_next(request)

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting.

        Args:
            request: The incoming request

        Returns:
            Client identifier string
        """
        # Try to get user ID from authenticated request
        if hasattr(request.state, "user") and request.state.user:
            return f"user:{request.state.user.id}"

        # Fall back to IP address
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return f"ip:{forwarded_for.split(',')[0].strip()}"

        return f"ip:{request.client.host if request.client else 'unknown'}"

    async def _check_rate_limit(self, client_id: str) -> bool:
        """Check if client has exceeded rate limit.

        Args:
            client_id: The client identifier

        Returns:
            True if under limit, False if exceeded
        """
        if self.redis_client:
            return await self._check_redis_rate_limit(client_id)
        else:
            return await self._check_memory_rate_limit(client_id)

    async def _check_redis_rate_limit(self, client_id: str) -> bool:
        """Check rate limit using Redis.

        Args:
            client_id: The client identifier

        Returns:
            True if under limit, False if exceeded
        """
        try:
            key = f"{self.prefix}:{client_id}"
            current = await self.redis_client.incr(key)

            if current == 1:
                # Set expiration on first request
                await self.redis_client.expire(key, self.period)

            return current <= self.requests
        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            return True  # Allow request if Redis fails

    async def _check_memory_rate_limit(self, client_id: str) -> bool:
        """Check rate limit using in-memory storage.

        Note: This is not recommended for production as it doesn't
        work across multiple worker processes.

        Args:
            client_id: The client identifier

        Returns:
            True if under limit, False if exceeded
        """
        # Simple in-memory rate limiting (not production-ready)
        if not hasattr(self, "_rate_limit_store"):
            self._rate_limit_store = {}

        now = time.time()
        key = f"{client_id}:{int(now // self.period)}"

        if key not in self._rate_limit_store:
            self._rate_limit_store[key] = 0

        self._rate_limit_store[key] += 1
        return self._rate_limit_store[key] <= self.requests


def setup_cors(app: ASGIApp) -> None:
    """Set up CORS middleware for the application.

    Args:
        app: The ASGI application
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )
