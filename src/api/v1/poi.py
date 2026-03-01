"""POI (Point of Interest) API endpoints."""

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import DBSession, OptionalCurrentUser
from src.database.repositories.poi import POIRepository
from src.schemas.route import POIBrief

router = APIRouter()


@router.get("/nearby", response_model=list[POIBrief])
async def get_nearby_pois(
    latitude: float = Query(..., ge=-90, le=90, description="Center latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Center longitude"),
    radius: float = Query(5.0, ge=0.1, le=50.0, description="Search radius in kilometers"),
    categories: list[str] | None = Query(None, description="Filter by categories"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    session: AsyncSession = Depends(DBSession),
    user: OptionalCurrentUser = None,
) -> list[POIBrief]:
    """Get POIs near a location.

    Args:
        latitude: Center latitude
        longitude: Center longitude
        radius: Search radius in kilometers
        categories: Optional category filter
        limit: Maximum number of results
        session: Database session
        user: Optional authenticated user

    Returns:
        List of nearby POIs
    """
    repo = POIRepository(session)
    pois = await repo.get_nearby(
        latitude=Decimal(str(latitude)),
        longitude=Decimal(str(longitude)),
        radius_km=radius,
        categories=categories,
        limit=limit,
    )

    return [
        POIBrief(
            id=poi.id,
            name=poi.name,
            categories=poi.categories,
            latitude=Decimal(str(float(poi.latitude))),
            longitude=Decimal(str(float(poi.longitude))),
            rating=float(poi.rating) if poi.rating else None,
            price_level=poi.price_level,
            estimated_duration_minutes=None,
        )
        for poi in pois
    ]


@router.get("/city/{city}", response_model=list[POIBrief])
async def get_pois_by_city(
    city: str,
    country: str | None = Query(None, description="Country filter"),
    categories: list[str] | None = Query(None, description="Filter by categories"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    session: AsyncSession = Depends(DBSession),
    user: OptionalCurrentUser = None,
) -> list[POIBrief]:
    """Get POIs in a city.

    Args:
        city: City name
        country: Optional country filter
        categories: Optional category filter
        limit: Maximum number of results
        session: Database session
        user: Optional authenticated user

    Returns:
        List of POIs in the city
    """
    repo = POIRepository(session)
    pois = await repo.get_by_city(
        city=city,
        country=country,
        categories=categories,
        limit=limit,
    )

    return [
        POIBrief(
            id=poi.id,
            name=poi.name,
            categories=poi.categories,
            latitude=Decimal(str(float(poi.latitude))),
            longitude=Decimal(str(float(poi.longitude))),
            rating=float(poi.rating) if poi.rating else None,
            price_level=poi.price_level,
            estimated_duration_minutes=None,
        )
        for poi in pois
    ]


@router.get("/trending", response_model=list[POIBrief])
async def get_trending_pois(
    city: str | None = Query(None, description="Filter by city"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    session: AsyncSession = Depends(DBSession),
    user: OptionalCurrentUser = None,
) -> list[POIBrief]:
    """Get trending POIs based on social signals.

    Args:
        city: Optional city filter
        limit: Maximum number of results
        session: Database session
        user: Optional authenticated user

    Returns:
        List of trending POIs
    """
    repo = POIRepository(session)
    pois = await repo.get_trending(city=city, limit=limit)

    return [
        POIBrief(
            id=poi.id,
            name=poi.name,
            categories=poi.categories,
            latitude=Decimal(str(float(poi.latitude))),
            longitude=Decimal(str(float(poi.longitude))),
            rating=float(poi.rating) if poi.rating else None,
            price_level=poi.price_level,
            estimated_duration_minutes=None,
        )
        for poi in pois
    ]


@router.get("/{poi_id}", response_model=dict[str, Any])
async def get_poi_details(
    poi_id: uuid.UUID,
    session: AsyncSession = Depends(DBSession),
    user: OptionalCurrentUser = None,
) -> dict[str, Any]:
    """Get detailed POI information.

    Args:
        poi_id: POI ID
        session: Database session
        user: Optional authenticated user

    Returns:
        Detailed POI information

    Raises:
        NotFoundError: If POI not found
    """
    from src.core.exceptions import NotFoundError

    repo = POIRepository(session)
    poi = await repo.get_by_id(poi_id)

    if not poi or not poi.is_active:
        raise NotFoundError("POI", str(poi_id))

    return poi.to_detail_dict()
