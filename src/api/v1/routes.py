"""Routes API endpoints (Phase 1 stub, Phase 3 full implementation)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DBSession
from src.schemas.route import (
    Location,
    POIBrief,
    RouteGenerateRequest,
    RouteListResponse,
    RouteModifyRequest,
    RouteResponse,
)

router = APIRouter()


@router.post("/generate", response_model=RouteResponse, status_code=201)
async def generate_route(
    data: RouteGenerateRequest,
    user: CurrentUser,
    session: DBSession,
) -> RouteResponse:
    """Generate a personalized travel route.

    This is a stub implementation for Phase 1. Full implementation will be in Phase 3.

    Args:
        data: Route generation request
        user: Current user
        session: Database session

    Returns:
        Generated route

    Note:
        Full implementation including POI matching, optimization, and RAG
        will be available in Phase 3.
    """
    from src.core.exceptions import NotImplementedError

    # Return placeholder route
    return RouteResponse(
        id=uuid.uuid4(),
        title=f"Route from {data.start_location.city or 'start'} to {data.end_location.city if data.end_location else 'end'}",
        description="This is a placeholder route. Full route planning will be implemented in Phase 3.",
        status="draft",
        stops=[],
        total_distance_km=0.0,
        total_duration_minutes=0,
        estimated_start_time=data.start_time,
        estimated_end_time=data.end_time,
        satisfaction_score=0.0,
        created_at=timestamp(),
    )


@router.get("/", response_model=RouteListResponse)
async def list_routes(
    user: CurrentUser,
    session: DBSession,
    status: str | None = Query(None, description="Filter by status"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Pagination limit"),
) -> RouteListResponse:
    """List user's routes.

    This is a stub implementation for Phase 1.

    Args:
        user: Current user
        session: Database session
        status: Optional status filter
        offset: Pagination offset
        limit: Pagination limit

    Returns:
        List of routes
    """
    # Return empty list for now
    return RouteListResponse(
        routes=[],
        total=0,
        page=offset // limit + 1,
        page_size=limit,
    )


@router.get("/{route_id}", response_model=RouteResponse)
async def get_route(
    route_id: uuid.UUID,
    user: CurrentUser,
    session: DBSession,
) -> RouteResponse:
    """Get route details.

    This is a stub implementation for Phase 1.

    Args:
        route_id: Route ID
        user: Current user
        session: Database session

    Returns:
        Route details

    Raises:
        NotFoundError: If route not found
    """
    from src.core.exceptions import NotFoundError

    # For now, raise not found
    raise NotFoundError("Route", str(route_id))


@router.patch("/{route_id}", response_model=RouteResponse)
async def modify_route(
    route_id: uuid.UUID,
    data: RouteModifyRequest,
    user: CurrentUser,
    session: DBSession,
) -> RouteResponse:
    """Modify an existing route.

    This is a stub implementation for Phase 1.

    Args:
        route_id: Route ID
        data: Modification request
        user: Current user
        session: Database session

    Returns:
        Modified route

    Raises:
        NotFoundError: If route not found
    """
    from src.core.exceptions import NotFoundError

    raise NotFoundError("Route", str(route_id))


@router.delete("/{route_id}")
async def delete_route(
    route_id: uuid.UUID,
    user: CurrentUser,
    session: DBSession,
) -> dict[str, str]:
    """Delete a route.

    This is a stub implementation for Phase 1.

    Args:
        route_id: Route ID
        user: Current user
        session: Database session

    Returns:
        Deletion confirmation

    Raises:
        NotFoundError: If route not found
    """
    from src.core.exceptions import NotFoundError

    raise NotFoundError("Route", str(route_id))


@router.post("/{route_id}/optimize", response_model=RouteResponse)
async def optimize_route(
    route_id: uuid.UUID,
    user: CurrentUser,
    session: DBSession,
) -> RouteResponse:
    """Re-optimize an existing route.

    This is a stub implementation for Phase 1.

    Args:
        route_id: Route ID
        user: Current user
        session: Database session

    Returns:
        Optimized route

    Raises:
        NotFoundError: If route not found
    """
    from src.core.exceptions import NotFoundError

    raise NotFoundError("Route", str(route_id))


def timestamp() -> Any:
    """Get current timestamp.

    Returns:
        Current datetime
    """
    from datetime import datetime

    return datetime.now()
