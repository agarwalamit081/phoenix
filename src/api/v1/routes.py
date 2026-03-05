"""Routes API endpoints (Phase 1 stub, Phase 3 full implementation)."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DBSession, OptionalCurrentUser
from src.database.repositories.poi import POIRepository
from src.schemas.route import (
    POIBrief,
    RouteGenerateRequest,
    RouteListResponse,
    RouteModifyRequest,
    RouteStop,
    RouteResponse,
)

router = APIRouter()


@router.post("/generate", response_model=RouteResponse, status_code=201)
async def generate_route(
    data: RouteGenerateRequest,
    user: OptionalCurrentUser,
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
    def haversine_km(lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal) -> float:
        """Calculate distance between two coordinates in KM."""
        lat1_rad = radians(float(lat1))
        lat2_rad = radians(float(lat2))
        lon1_rad = radians(float(lon1))
        lon2_rad = radians(float(lon2))

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
        return 6371.0 * 2 * asin(sqrt(a))

    repo = POIRepository(session)
    city = data.start_location.city
    country = data.start_location.country
    preferred_categories = data.preferred_categories or None

    pois = []
    if city:
        pois = await repo.get_by_city(
            city=city,
            country=country,
            categories=preferred_categories,
            limit=12,
        )

    if len(pois) < 3:
        trending = await repo.get_trending(city=city, limit=12)
        seen_ids = {poi.id for poi in pois}
        for poi in trending:
            if poi.id not in seen_ids:
                pois.append(poi)
                seen_ids.add(poi.id)
            if len(pois) >= 8:
                break

    selected_pois = pois[:5]
    if not selected_pois:
        base_lat = data.start_location.latitude
        base_lng = data.start_location.longitude
        synthetic_stops: list[RouteStop] = []
        for index in range(3):
            offset = Decimal("0.004") * Decimal(index + 1)
            poi_lat = base_lat + offset
            poi_lng = base_lng + offset
            synthetic_stops.append(
                RouteStop(
                    sequence_order=index + 1,
                    poi=POIBrief(
                        id=uuid.uuid4(),
                        name=f"Local Highlight {index + 1}",
                        categories=["sightseeing"],
                        latitude=poi_lat,
                        longitude=poi_lng,
                        rating=4.2,
                        price_level=1,
                        estimated_duration_minutes=45,
                    ),
                    estimated_arrival_time=None,
                    estimated_departure_time=None,
                    estimated_duration_minutes=45,
                    distance_from_previous_km=0.0 if index == 0 else float(0.6 * index),
                    travel_time_minutes=0 if index == 0 else int((0.6 * index / 4.5) * 60),
                    transport_mode=data.transport_mode,
                ),
            )

        return RouteResponse(
            id=uuid.uuid4(),
            title=f"{data.start_location.city or 'Nearby'} quick route",
            description="Generated fallback route based on your current location.",
            status="generated",
            stops=synthetic_stops,
            total_distance_km=float(sum(stop.distance_from_previous_km or 0 for stop in synthetic_stops)),
            total_duration_minutes=int(sum((stop.travel_time_minutes or 0) + (stop.estimated_duration_minutes or 0) for stop in synthetic_stops)),
            estimated_start_time=data.start_time or datetime.now(),
            estimated_end_time=(data.start_time or datetime.now()) + timedelta(
                minutes=int(sum((stop.travel_time_minutes or 0) + (stop.estimated_duration_minutes or 0) for stop in synthetic_stops)),
            ),
            satisfaction_score=0.72,
            optimization_version=1,
            created_at=timestamp(),
        )

    route_stops: list[RouteStop] = []
    total_distance = 0.0
    total_duration = 0
    prev_lat = data.start_location.latitude
    prev_lng = data.start_location.longitude

    for index, poi in enumerate(selected_pois):
        distance_km = haversine_km(prev_lat, prev_lng, poi.latitude, poi.longitude)
        travel_minutes = int((distance_km / 4.5) * 60) if index > 0 else 0
        visit_minutes = 45
        total_distance += distance_km
        total_duration += travel_minutes + visit_minutes
        prev_lat = poi.latitude
        prev_lng = poi.longitude

        route_stops.append(
            RouteStop(
                sequence_order=index + 1,
                poi=POIBrief(
                    id=poi.id,
                    name=poi.name,
                    categories=poi.categories,
                    latitude=poi.latitude,
                    longitude=poi.longitude,
                    rating=float(poi.rating) if poi.rating is not None else None,
                    price_level=poi.price_level,
                    estimated_duration_minutes=visit_minutes,
                ),
                estimated_arrival_time=None,
                estimated_departure_time=None,
                estimated_duration_minutes=visit_minutes,
                distance_from_previous_km=round(distance_km, 2),
                travel_time_minutes=travel_minutes,
                transport_mode=data.transport_mode,
            ),
        )

    start_time = data.start_time or datetime.now()
    return RouteResponse(
        id=uuid.uuid4(),
        title=f"{city or 'City'} walking route",
        description="Generated from nearby points of interest and your route settings.",
        status="generated",
        stops=route_stops,
        total_distance_km=round(total_distance, 2),
        total_duration_minutes=total_duration,
        estimated_start_time=start_time,
        estimated_end_time=start_time + timedelta(minutes=total_duration),
        satisfaction_score=0.78,
        optimization_version=1,
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
