"""Map service for map operations."""

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.maps.client import GoogleMapsClient, get_google_maps_client
from src.maps.renderer import (
    MapRenderer,
    InteractiveMapRenderer,
    get_map_renderer,
    get_interactive_renderer,
)

logger = logging.getLogger(__name__)


class MapService:
    """Service for map operations."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        """Initialize map service.

        Args:
            session: Database session
        """
        self.session = session
        self.client = get_google_maps_client()
        self.renderer = get_map_renderer()
        self.interactive_renderer = get_interactive_renderer()

    async def geocode_address(
        self,
        address: str,
    ) -> dict[str, Any] | None:
        """Geocode an address to coordinates.

        Args:
            address: Address string

        Returns:
            Geocoding result
        """
        return await self.client.geocode(address)

    async def reverse_geocode(
        self,
        lat: float,
        lng: float,
    ) -> dict[str, Any] | None:
        """Reverse geocode coordinates to address.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            Address result
        """
        return await self.client.reverse_geocode(lat, lng)

    async def search_places(
        self,
        query: str,
        location: dict[str, float] | None = None,
        radius: int = 5000,
        type_: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for places.

        Args:
            query: Search query
            location: Optional center location
            radius: Search radius in meters
            type_: Optional place type

        Returns:
            List of places
        """
        return await self.client.search_places(query, location, radius, type_)

    async def get_place_details(
        self,
        place_id: str,
    ) -> dict[str, Any] | None:
        """Get detailed place information.

        Args:
            place_id: Place ID

        Returns:
            Place details
        """
        return await self.client.get_place_details(place_id)

    async def get_distance_matrix(
        self,
        origins: list[dict[str, float]],
        destinations: list[dict[str, float]],
        mode: str = "driving",
    ) -> dict[str, Any] | None:
        """Get distance matrix.

        Args:
            origins: Origin locations
            destinations: Destination locations
            mode: Travel mode

        Returns:
            Distance matrix
        """
        return await self.client.get_distance_matrix(origins, destinations, mode)

    async def get_directions(
        self,
        origin: dict[str, float],
        destination: dict[str, float],
        mode: str = "driving",
        waypoints: list[dict[str, float]] | None = None,
    ) -> dict[str, Any] | None:
        """Get directions.

        Args:
            origin: Origin
            destination: Destination
            mode: Travel mode
            waypoints: Optional waypoints

        Returns:
            Directions
        """
        return await self.client.get_directions(origin, destination, mode, waypoints)

    async def get_nearby_places(
        self,
        location: dict[str, float],
        radius: int = 1000,
        type_: str | None = None,
        keyword: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get nearby places.

        Args:
            location: Center location
            radius: Search radius
            type_: Optional place type
            keyword: Optional keyword

        Returns:
            List of places
        """
        return await self.client.get_nearby_search(location, radius, type_, keyword)

    async def autocomplete_place(
        self,
        input_text: str,
        location: dict[str, float] | None = None,
        radius: int = 100000,
    ) -> list[dict[str, Any]]:
        """Get place autocomplete suggestions.

        Args:
            input_text: Input text
            location: Optional location
            radius: Location bias radius

        Returns:
            List of predictions
        """
        return await self.client.autocomplete_place(input_text, location, radius)

    async def get_elevation(
        self,
        locations: list[dict[str, float]],
    ) -> list[float] | None:
        """Get elevation for locations.

        Args:
            locations: List of locations

        Returns:
            List of elevations
        """
        return await self.client.get_elevation(locations)

    async def render_poi_map(
        self,
        pois: list[dict[str, Any]],
        center: dict[str, float] | None = None,
        zoom: int = 13,
        width: int = 800,
        height: int = 600,
        interactive: bool = False,
    ) -> dict[str, Any]:
        """Render map with POIs.

        Args:
            pois: List of POIs
            center: Optional center
            zoom: Zoom level
            width: Map width
            height: Map height
            interactive: Whether to render interactive map

        Returns:
            Map render result
        """
        if interactive:
            return await self.interactive_renderer.render_interactive_map(
                pois=pois,
                width=f"{width}px",
                height=f"{height}px",
                center=center,
                zoom=zoom,
            )
        else:
            return await self.renderer.render_poi_map(
                pois=pois,
                center=center,
                zoom=zoom,
                width=width,
                height=height,
            )

    async def render_route_map(
        self,
        route: dict[str, Any],
        width: int = 800,
        height: int = 600,
        interactive: bool = False,
    ) -> dict[str, Any]:
        """Render map with route.

        Args:
            route: Route data
            width: Map width
            height: Map height
            interactive: Whether to render interactive map

        Returns:
            Map render result
        """
        if interactive:
            return await self.interactive_renderer.render_interactive_route_map(
                route=route,
                width=f"{width}px",
                height=f"{height}px",
            )
        else:
            return await self.renderer.render_route_map(
                route=route,
                width=width,
                height=height,
            )

    async def generate_geojson(
        self,
        pois: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate GeoJSON from POIs.

        Args:
            pois: List of POIs

        Returns:
            GeoJSON
        """
        return await self.renderer.generate_geojson(pois)

    async def generate_route_geojson(
        self,
        route: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate GeoJSON for route.

        Args:
            route: Route data

        Returns:
            GeoJSON
        """
        return await self.renderer.generate_route_geojson(route)

    async def batch_geocode(
        self,
        addresses: list[str],
    ) -> list[dict[str, Any] | None]:
        """Batch geocode addresses.

        Args:
            addresses: List of addresses

        Returns:
            List of geocoding results
        """
        tasks = [self.client.geocode(addr) for addr in addresses]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        geocoded = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to geocode {addresses[i]}: {result}")
                geocoded.append(None)
            else:
                geocoded.append(result)

        return geocoded

    async def calculate_route_stats(
        self,
        route: dict[str, Any],
    ) -> dict[str, Any]:
        """Calculate route statistics.

        Args:
            route: Route data

        Returns:
            Route statistics
        """
        pois = route.get("pois", [])

        if not pois:
            return {
                "total_pois": 0,
                "estimated_distance_km": 0,
                "estimated_duration_minutes": 0,
            }

        # Get distance matrix for consecutive POIs
        total_distance = 0
        total_duration = 0

        for i in range(len(pois) - 1):
            from_poi = pois[i]
            to_poi = pois[i + 1]

            origin = {
                "lat": from_poi.get("latitude", from_poi.get("lat", 0)),
                "lng": from_poi.get("longitude", from_poi.get("lng", 0)),
            }

            destination = {
                "lat": to_poi.get("latitude", to_poi.get("lat", 0)),
                "lng": to_poi.get("longitude", to_poi.get("lng", 0)),
            }

            directions = await self.client.get_directions(origin, destination)

            if directions:
                total_distance += directions.get("distance_km", 0)
                total_duration += directions.get("duration_min", 0)

        return {
            "total_pois": len(pois),
            "estimated_distance_km": round(total_distance, 2),
            "estimated_duration_minutes": round(total_duration),
            "estimated_duration_hours": round(total_duration / 60, 2),
        }

    async def close(self) -> None:
        """Close map client."""
        await self.client.close()


# Global instance factory
def get_map_service(session: AsyncSession) -> MapService:
    """Get map service instance.

    Args:
        session: Database session

    Returns:
        Map service instance
    """
    return MapService(session)
