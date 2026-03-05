"""Main FastAPI application for Phoenix AI Travel Companion."""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from src.config.logging import logger, setup_logging
from src.config.settings import settings
from src.core.middleware import RequestContextASGIMiddleware, setup_cors
from src.database import close_database, init_database
from src.api.v1 import auth, chat, preferences, routes, voice, workflows


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Args:
        app: The FastAPI application

    Yields:
        None
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")

    # Setup logging
    setup_logging()

    # Initialize database
    try:
        await init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down application")
    await close_database()
    logger.info("Database connections closed")


# Create FastAPI application
fastapi_app = FastAPI(
    title=settings.app_name,
    description="AI-powered travel companion with voice interaction and personalized recommendations",
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)


# Custom exception handlers
# Import exceptions here to register handlers for specific types
from src.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PhoenixException,
    get_http_exception,
)


@fastapi_app.exception_handler(PhoenixException)
async def phoenix_exception_handler(request: Request, exc: PhoenixException) -> JSONResponse:
    """Handle PhoenixException and return appropriate HTTP responses.

    Args:
        request: The incoming request
        exc: The Phoenix exception

    Returns:
        JSON response with error details
    """
    http_exc = get_http_exception(exc)
    status = http_exc.status_code
    detail = http_exc.detail

    # Handle both dict and string detail formats
    if isinstance(detail, dict):
        return JSONResponse(status_code=status, content=detail)
    else:
        return JSONResponse(
            status_code=status,
            content={"detail": detail},
        )


@fastapi_app.exception_handler(AuthenticationError)
async def authentication_exception_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
    """Handle AuthenticationError specifically.

    Args:
        request: The incoming request
        exc: The authentication exception

    Returns:
        JSON response with 401 status
    """
    http_exc = get_http_exception(exc)
    return JSONResponse(status_code=http_exc.status_code, content={"detail": exc.message})


@fastapi_app.exception_handler(ConflictError)
async def conflict_exception_handler(request: Request, exc: ConflictError) -> JSONResponse:
    """Handle ConflictError specifically.

    Args:
        request: The incoming request
        exc: The conflict exception

    Returns:
        JSON response with 409 status
    """
    http_exc = get_http_exception(exc)
    return JSONResponse(status_code=http_exc.status_code, content={"detail": exc.message})


@fastapi_app.exception_handler(NotFoundError)
async def not_found_exception_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    """Handle NotFoundError specifically.

    Args:
        request: The incoming request
        exc: The not found exception

    Returns:
        JSON response with 404 status
    """
    http_exc = get_http_exception(exc)
    return JSONResponse(status_code=http_exc.status_code, content={"detail": exc.message})


# Health check endpoint
@fastapi_app.get("/health", tags=["Health"])
async def health_check() -> dict[str, Any]:
    """Health check endpoint.

    Returns:
        Health status
    """
    from src.database import check_database_health

    db_healthy = await check_database_health()

    return {
        "status": "healthy" if db_healthy else "degraded",
        "version": settings.app_version,
        "database": "connected" if db_healthy else "disconnected",
        "environment": settings.environment,
    }


# Root endpoint
@fastapi_app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """Root endpoint.

    Returns:
        Welcome message
    """
    return {
        "message": "Welcome to Phoenix AI Travel Companion",
        "version": settings.app_version,
        "docs": "/docs" if settings.debug else "Documentation disabled in production",
    }


def _frontend_app_url(path: str = "/app", query: str = "") -> str:
    """Build frontend URL for local development redirects."""
    base = "http://localhost:8080"
    url = f"{base}{path}"
    if query:
        url = f"{url}?{query}"
    return url


@fastapi_app.get("/app", tags=["Root"])
async def frontend_app_redirect(request: Request) -> RedirectResponse:
    """Redirect /app on backend port to frontend dev server."""
    return RedirectResponse(url=_frontend_app_url("/app", request.url.query), status_code=307)


@fastapi_app.get("/app/{subpath:path}", tags=["Root"])
async def frontend_app_subpath_redirect(subpath: str, request: Request) -> RedirectResponse:
    """Redirect /app/* on backend port to frontend dev server."""
    return RedirectResponse(
        url=_frontend_app_url(f"/app/{subpath}", request.url.query),
        status_code=307,
    )


# Include API routers
fastapi_app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
fastapi_app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
fastapi_app.include_router(preferences.router, prefix="/api/v1/preferences", tags=["Preferences"])
fastapi_app.include_router(routes.router, prefix="/api/v1/routes", tags=["Routes"])
fastapi_app.include_router(voice.router, prefix="/api/v1/voice", tags=["Voice"])
fastapi_app.include_router(workflows.router, prefix="/api/v1/workflows", tags=["Workflows"])


# Setup CORS (must be done before wrapping with ASGI middleware)
setup_cors(fastapi_app)


# Wrap app with ASGI middleware (avoids BaseHTTPMiddleware event loop issues)
# We keep the original FastAPI app for testing, and export the wrapped app for serving
# The middleware wrapper needs to expose the FastAPI app's interface for testing
class AppWrapper:
    """Wrapper that exposes the ASGI app while keeping FastAPI app accessible."""

    def __init__(self, inner_fastapi_app: FastAPI) -> None:
        """Initialize the wrapper.

        Args:
            inner_fastapi_app: The original FastAPI app
        """
        self._fastapi_app = inner_fastapi_app
        # Only use RequestContextASGIMiddleware, rely on FastAPI's exception handler
        self._asgi_app = RequestContextASGIMiddleware(inner_fastapi_app)

    # Expose FastAPI app attributes
    @property
    def dependency_overrides(self):
        """Get dependency overrides from FastAPI app."""
        return self._fastapi_app.dependency_overrides

    @dependency_overrides.setter
    def dependency_overrides(self, value):
        """Set dependency overrides on FastAPI app."""
        self._fastapi_app.dependency_overrides = value

    def clear_dependency_overrides(self):
        """Clear dependency overrides."""
        self._fastapi_app.dependency_overrides.clear()

    # Expose other FastAPI app attributes as needed
    @property
    def routes(self):
        """Get routes from FastAPI app."""
        return self._fastapi_app.routes

    @property
    def title(self):
        """Get app title."""
        return self._fastapi_app.title

    # Make this callable as an ASGI app
    async def __call__(self, scope, receive, send):
        """Call the ASGI app."""
        await self._asgi_app(scope, receive, send)


# Wrap the app with middleware and export as 'app'
app = AppWrapper(fastapi_app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
