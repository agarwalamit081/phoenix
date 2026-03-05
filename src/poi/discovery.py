"""POI discovery for searching and finding POIs."""

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterable, AsyncGenerator
from datetime import datetime, timezone
from typing import Any

from src.config.settings import settings
from src.core.exceptions import ValidationError
from src.poi.importer import GooglePlacesImporter, poi_importer
from src.poi.matcher import POIMatcher, poi_matcher

logger = logging.getLogger(__name__)


class POIDiscovery:
    """Discover and search POIs."""

    def __init__(
        self,
        importer: GooglePlacesImporter | None = None,
        matcher: POIMatcher | None = None,
    ) -> None:
        """Initialize POI discovery.

        Args:
            importer: Optional POI importer
            matcher: Optional POI matcher
        """
        self.importer = importer or poi_importer
        self.matcher = matcher or poi_matcher

    async def search_nearby(
        self,
        location: dict[str, float],
        query: str,
        radius: int = 1000,
        limit: int = 20,
        user_preferences: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for POIs near a location.

        Args:
            location: Center location {lat, lng}
            query: Search query
            radius: Search radius in meters
            limit: Maximum results
            user_preferences: Optional user preferences for ranking

        Returns:
            List of POIs
        """
        # Import from Google Places
        try:
            places = await self.importer.import_places(
                query=query,
                location=location,
                radius=radius,
                limit=limit,
            )
        except Exception as e:
            logger.error(f"Failed to import places: {e}")
            return []

        # Rank by preferences if provided
        if user_preferences and places:
            ranked = await self.matcher.rank_pois(places, user_preferences, limit=limit)

            # Get original POIs in ranked order
            poi_map = {p.get("external_id", p.get("id")): p for p in places}
            ranked_pois = []

            for r in ranked:
                poi_id = r["poi_id"]
                if poi_id in poi_map:
                    ranked_pois.append({
                        **poi_map[poi_id],
                        "match_score": r["score"],
                    })

            return ranked_pois

        return places

    async def discover_by_category(
        self,
        location: dict[str, float],
        categories: list[str],
        radius: int = 5000,
        limit_per_category: int = 10,
    ) -> dict[str, list[dict[str, Any]]]:
        """Discover POIs by category.

        Args:
            location: Center location
            categories: List of categories to search
            radius: Search radius
            limit_per_category: Max POIs per category

        Returns:
            POIs grouped by category
        """
        results = {}

        for category in categories:
            try:
                places = await self.search_nearby(
                    location=location,
                    query=category,
                    radius=radius,
                    limit=limit_per_category,
                )

                results[category] = places

                logger.info(f"Found {len(places)} {category} places")

            except Exception as e:
                logger.error(f"Failed to discover {category}: {e}")
                results[category] = []

        return results

    async def find_nearest(
        self,
        location: dict[str, float],
        category: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find nearest POIs to a location.

        Args:
            location: Center location
            category: Optional category filter
            limit: Maximum results

        Returns:
            List of nearest POIs with distances
        """
        query = category or "points of interest"

        places = await self.search_nearby(
            location=location,
            query=query,
            radius=1000,
            limit=50,
        )

        # Calculate distances
        for place in places:
            place["distance"] = self._calculate_distance(
                location,
                {
                    "lat": place.get("latitude"),
                    "lng": place.get("longitude"),
                },
            )

        # Sort by distance
        places.sort(key=lambda p: p["distance"])

        return places[:limit]

    async def search_by_name(
        self,
        name: str,
        location: dict[str, float] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for POIs by name.

        Args:
            name: POI name to search
            location: Optional center location

        Returns:
            List of matching POIs
        """
        places = await self.importer.import_places(
            query=name,
            location=location,
            radius=10000,
            limit=10,
        )

        return places

    async def discover_route(
        self,
        start_location: dict[str, float],
        end_location: dict[str, float],
        categories: list[str] | None = None,
        poi_count: int = 10,
    ) -> dict[str, Any]:
        """Discover POIs along a route.

        Args:
            start_location: Start location
            end_location: End location
            categories: Optional categories to filter
            poi_count: Number of POIs to find

        Returns:
            Route discovery results
        """
        # Calculate midpoint
        mid_lat = (start_location["lat"] + end_location["lat"]) / 2
        mid_lng = (start_location["lng"] + end_location["lng"]) / 2

        # Calculate approximate radius (half of route length + buffer)
        distance = self._calculate_distance(start_location, end_location)
        radius = max(int(distance * 1000 / 2 + 5000), 10000)  # At least 10km

        # Search for POIs
        query = " ".join(categories) if categories else "points of interest"

        places = await self.search_nearby(
            location={"lat": mid_lat, "lng": mid_lng},
            query=query,
            radius=radius,
            limit=poi_count * 2,
        )

        # Filter to places along the route
        route_pois = []
        for place in places[:poi_count * 3]:
            # Check if place is between start and end
            if self._is_between_locations(
                start_location,
                end_location,
                {"lat": place.get("latitude"), "lng": place.get("longitude")},
            ):
                route_pois.append(place)

            if len(route_pois) >= poi_count:
                break

        return {
            "start_location": start_location,
            "end_location": end_location,
            "distance_km": distance,
            "pois": route_pois[:poi_count],
        }

    async def explore_area(
        self,
        location: dict[str, float],
        preferences: list[dict[str, Any]] | None = None,
        radius: int = 2000,
    ) -> dict[str, Any]:
        """Explore an area and return categorized recommendations.

        Args:
            location: Center location
            preferences: Optional user preferences
            radius: Search radius

        Returns:
            Exploration results
        """
        # Search for various categories
        categories = ["restaurant", "attractions", "museums", "parks", "shopping"]

        all_pois = []
        by_category = {}

        for category in categories:
            places = await self.search_nearby(
                location=location,
                query=category,
                radius=radius,
                limit=10,
                user_preferences=preferences,
            )

            by_category[category] = places
            all_pois.extend(places)

        # Get overall top recommendations
        if preferences:
            top_pois = await self.matcher.rank_pois(all_pois, preferences, limit=20)
        else:
            top_pois = [{"poi_id": p.get("id"), "score": 1.0} for p in all_pois[:20]]

        return {
            "location": location,
            "radius": radius,
            "by_category": by_category,
            "top_recommendations": top_pois,
            "total_pois": len(all_pois),
        }

    def _calculate_distance(
        self,
        loc1: dict[str, float],
        loc2: dict[str, float],
    ) -> float:
        """Calculate distance between two locations (Haversine formula).

        Args:
            loc1: First location {lat, lng}
            loc2: Second location {lat, lng}

        Returns:
            Distance in kilometers
        """
        import math

        R = 6371  # Earth radius in km

        lat1 = math.radians(loc1["lat"])
        lat2 = math.radians(loc2["lat"])
        delta_lat = math.radians(loc2["lat"] - loc1["lat"])
        delta_lng = math.radians(loc2["lng"] - loc1["lng"])

        a = (
            math.sin(delta_lat / 2) ** 2 +
            math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2
        )

        c = 2 * math.asin(math.sqrt(a))

        return R * c

    def _is_between_locations(
        self,
        start: dict[str, float],
        end: dict[str, float],
        point: dict[str, float],
        tolerance: float = 0.2,
    ) -> bool:
        """Check if a point is between two locations.

        Args:
            start: Start location
            end: End location
            point: Point to check
            tolerance: Tolerance factor

        Returns:
            True if point is between start and end
        """
        # Calculate distances
        d_start_point = self._calculate_distance(start, point)
        d_point_end = self._calculate_distance(point, end)
        d_start_end = self._calculate_distance(start, end)

        # Check if sum of distances is approximately equal to total distance
        return (d_start_point + d_point_end) <= d_start_end * (1 + tolerance)

    async def stream_search_results(
        self,
        location: dict[str, float],
        query: str,
        radius: int = 1000,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream search results as they're found.

        Args:
            location: Center location
            query: Search query
            radius: Search radius

        Yields:
            POI data
        """
        try:
            async for place in self.importer.search_nearby(
                location=location,
                query=query,
                radius=radius,
            ):
                yield place

        except Exception as e:
            logger.error(f"Error in stream search: {e}")


class POIRepository:
    """In-memory repository for POI data."""

    def __init__(self) -> None:
        """Initialize POI repository."""
        self._pois: dict[str, dict[str, Any]] = {}
        self._by_category: dict[str, list[str]] = defaultdict(list)
        self._by_location: dict[str, list[str]] = defaultdict(list)

    def add_poi(self, poi: dict[str, Any]) -> None:
        """Add a POI to the repository.

        Args:
            poi: POI data
        """
        poi_id = poi.get("id") or poi.get("external_id")

        if not poi_id:
            return

        self._pois[poi_id] = poi

        # Index by category
        category = poi.get("category", "other")
        self._by_category[category].append(poi_id)

        # Index by location (geohash-like grid)
        if poi.get("latitude") and poi.get("longitude"):
            grid_key = self._get_grid_key(
                poi["latitude"],
                poi["longitude"],
            )
            self._by_location[grid_key].append(poi_id)

    def get_poi(self, poi_id: str) -> dict[str, Any] | None:
        """Get a POI by ID.

        Args:
            poi_id: POI ID

        Returns:
            POI data or None
        """
        return self._pois.get(poi_id)

    def get_by_category(self, category: str) -> list[dict[str, Any]]:
        """Get POIs by category.

        Args:
            category: Category name

        Returns:
            List of POIs
        """
        poi_ids = self._by_category.get(category, [])
        return [self._pois[pid] for pid in poi_ids if pid in self._pois]

    def get_nearby(
        self,
        lat: float,
        lng: float,
        radius_km: float = 1.0,
    ) -> list[dict[str, Any]]:
        """Get POIs near a location.

        Args:
            lat: Latitude
            lng: Longitude
            radius_km: Search radius in km

        Returns:
            List of nearby POIs
        """
        # Get nearby grid cells
        nearby_ids = set()

        grid_size = int(radius_km / 10) + 1  # Approximate grid cell size

        for lat_offset in range(-grid_size, grid_size + 1):
            for lng_offset in range(-grid_size, grid_size + 1):
                grid_key = self._get_grid_key(
                    lat + lat_offset * 0.1,
                    lng + lng_offset * 0.1,
                )
                nearby_ids.update(self._by_location.get(grid_key, []))

        # Filter by actual distance
        nearby_pois = []

        for poi_id in nearby_ids:
            poi = self._pois.get(poi_id)
            if poi:
                dist = self._calculate_distance(
                    {"lat": lat, "lng": lng},
                    {"lat": poi["latitude"], "lng": poi["longitude"]},
                )
                if dist <= radius_km:
                    poi["distance_km"] = dist
                    nearby_pois.append(poi)

        nearby_pois.sort(key=lambda p: p["distance_km"])

        return nearby_pois

    def _get_grid_key(self, lat: float, lng: float) -> str:
        """Get grid key for location indexing.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            Grid key
        """
        lat_grid = int(lat * 10)  # ~11km precision
        lng_grid = int(lng * 10)
        return f"{lat_grid}:{lng_grid}"

    def _calculate_distance(
        self,
        loc1: dict[str, float],
        loc2: dict[str, float],
    ) -> float:
        """Calculate distance between locations.

        Args:
            loc1: First location
            loc2: Second location

        Returns:
            Distance in km
        """
        import math

        R = 6371

        lat1 = math.radians(loc1["lat"])
        lat2 = math.radians(loc2["lat"])
        delta_lat = math.radians(loc2["lat"] - loc1["lat"])
        delta_lng = math.radians(loc2["lng"] - loc1["lng"])

        a = (
            math.sin(delta_lat / 2) ** 2 +
            math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2
        )

        c = 2 * math.asin(math.sqrt(a))

        return R * c

    def get_stats(self) -> dict[str, Any]:
        """Get repository statistics.

        Returns:
            Statistics
        """
        return {
            "total_pois": len(self._pois),
            "categories": len(self._by_category),
            "category_counts": {
                cat: len(ids) for cat, ids in self._by_category.items()
            },
        }


# Global instances
poi_discovery = POIDiscovery()
poi_repository = POIRepository()
