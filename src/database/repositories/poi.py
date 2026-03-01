"""Point of Interest repository for database operations."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.logging import logger
from src.database.repositories import BaseRepository
from src.models.poi import PointOfInterest, POISearchIndex


class POIRepository(BaseRepository[PointOfInterest]):
    """Repository for PointOfInterest model operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the POI repository.

        Args:
            session: The database session
        """
        super().__init__(session, PointOfInterest)

    async def get_by_external_id(self, external_id: str) -> PointOfInterest | None:
        """Get a POI by external ID.

        Args:
            external_id: The external ID (e.g., Google Places ID)

        Returns:
            The POI if found, None otherwise
        """
        stmt = select(PointOfInterest).where(
            PointOfInterest.external_id == external_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_nearby(
        self,
        latitude: Decimal,
        longitude: Decimal,
        radius_km: float = 5.0,
        categories: list[str] | None = None,
        limit: int = 20,
    ) -> list[PointOfInterest]:
        """Get POIs near a location.

        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_km: Search radius in kilometers
            categories: Optional category filter
            limit: Maximum number of results

        Returns:
            List of nearby POIs
        """
        from sqlalchemy import cast

        # Calculate bounding box for rough filtering
        lat_delta = Decimal(str(radius_km / 111.0))
        lon_delta = Decimal(str(radius_km / (111.0 * float(latitude.cos()))))

        min_lat = latitude - lat_delta
        max_lat = latitude + lat_delta
        min_lon = longitude - lon_delta
        max_lon = longitude + lon_delta

        stmt = select(PointOfInterest).where(
            and_(
                PointOfInterest.latitude >= min_lat,
                PointOfInterest.latitude <= max_lat,
                PointOfInterest.longitude >= min_lon,
                PointOfInterest.longitude <= max_lon,
                PointOfInterest.is_active == True,
            ),
        )

        if categories:
            stmt = stmt.where(PointOfInterest.categories.overlap(categories))

        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        pois = list(result.scalars().all())

        # Filter by exact distance
        nearby_pois = []
        for poi in pois:
            distance = self._calculate_distance(
                latitude, longitude, poi.latitude, poi.longitude
            )
            if distance <= radius_km:
                nearby_pois.append(poi)

        return nearby_pois[:limit]

    def _calculate_distance(
        self,
        lat1: Decimal,
        lon1: Decimal,
        lat2: Decimal,
        lon2: Decimal,
    ) -> float:
        """Calculate distance between two points using Haversine formula.

        Args:
            lat1: First point latitude
            lon1: First point longitude
            lat2: Second point latitude
            lon2: Second point longitude

        Returns:
            Distance in kilometers
        """
        from math import asin, cos, radians, sin, sqrt

        lat1_rad = radians(float(lat1))
        lat2_rad = radians(float(lat2))
        lon1_rad = radians(float(lon1))
        lon2_rad = radians(float(lon2))

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        r = 6371  # Earth's radius in km

        return c * r

    async def get_by_city(
        self,
        city: str,
        country: str | None = None,
        categories: list[str] | None = None,
        limit: int = 50,
    ) -> list[PointOfInterest]:
        """Get POIs in a city.

        Args:
            city: The city name
            country: Optional country filter
            categories: Optional category filter
            limit: Maximum number of results

        Returns:
            List of POIs in the city
        """
        stmt = select(PointOfInterest).where(
            PointOfInterest.city.ilike(f"%{city}%"),
            PointOfInterest.is_active == True,
        )

        if country:
            stmt = stmt.where(PointOfInterest.country.ilike(f"%{country}%"))

        if categories:
            stmt = stmt.where(PointOfInterest.categories.overlap(categories))

        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_categories(
        self,
        categories: list[str],
        limit: int = 50,
        min_rating: float | None = None,
    ) -> list[PointOfInterest]:
        """Get POIs by categories.

        Args:
            categories: List of categories to filter by
            limit: Maximum number of results
            min_rating: Optional minimum rating filter

        Returns:
            List of matching POIs
        """
        stmt = select(PointOfInterest).where(
            PointOfInterest.categories.overlap(categories),
            PointOfInterest.is_active == True,
        )

        if min_rating is not None:
            stmt = stmt.where(PointOfInterest.rating >= Decimal(str(min_rating)))

        stmt = stmt.order_by(PointOfInterest.rating.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_trending(
        self,
        city: str | None = None,
        limit: int = 20,
    ) -> list[PointOfInterest]:
        """Get trending POIs based on social signals.

        Args:
            city: Optional city filter
            limit: Maximum number of results

        Returns:
            List of trending POIs
        """
        stmt = select(PointOfInterest).where(
            PointOfInterest.is_active == True,
        )

        if city:
            stmt = stmt.where(PointOfInterest.city.ilike(f"%{city}%"))

        # Order by trending score in social signals
        stmt = stmt.limit(limit * 2)  # Get more, then filter
        result = await self.session.execute(stmt)
        pois = list(result.scalars().all())

        # Filter and sort by trending
        trending = [p for p in pois if p.is_trending()]
        trending.sort(key=lambda p: p.get_trending_score(), reverse=True)
        return trending[:limit]

    async def search_by_name(
        self,
        query: str,
        limit: int = 20,
    ) -> list[PointOfInterest]:
        """Search POIs by name.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching POIs
        """
        stmt = select(PointOfInterest).where(
            PointOfInterest.name.ilike(f"%{query}%"),
            PointOfInterest.is_active == True,
        ).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_or_create_by_external_id(
        self,
        external_id: str,
        defaults: dict[str, Any],
    ) -> PointOfInterest:
        """Get an existing POI by external ID or create a new one.

        Args:
            external_id: The external ID
            defaults: Default values for creation

        Returns:
            The existing or newly created POI
        """
        existing = await self.get_by_external_id(external_id)
        if existing:
            return existing

        defaults["external_id"] = external_id
        return await self.create(defaults)

    async def bulk_upsert(
        self,
        pois: list[dict[str, Any]],
    ) -> list[PointOfInterest]:
        """Bulk upsert POIs.

        Args:
            pois: List of POI dictionaries

        Returns:
            List of created or updated POIs
        """
        result = []
        for poi_data in pois:
            external_id = poi_data.get("external_id")
            if external_id:
                existing = await self.get_by_external_id(external_id)
                if existing:
                    for key, value in poi_data.items():
                        if value is not None and hasattr(existing, key):
                            setattr(existing, key, value)
                    result.append(existing)
                    continue
            result.append(await self.create(poi_data))
        return result

    async def cleanup_inactive(self) -> int:
        """Delete inactive POIs.

        Returns:
            Number of POIs deleted
        """
        stmt = select(PointOfInterest).where(PointOfInterest.is_active == False)
        result = await self.session.execute(stmt)
        pois = result.scalars().all()
        count = len(pois)
        for poi in pois:
            await self.session.delete(poi)
        logger.info(f"Cleaned up {count} inactive POIs")
        return count
