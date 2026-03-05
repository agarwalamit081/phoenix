"""Map client for Google Maps integration via MCP."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from src.config.settings import settings

logger = logging.getLogger(__name__)


class GoogleMapsClient:
    """Client for Google Maps API using MCP integration."""

    def __init__(
        self,
        api_key: str | None = None,
    ) -> None:
        """Initialize Google Maps client.

        Args:
            api_key: Google Maps API key
        """
        self.api_key = api_key or settings.google_maps_api_key
        self.base_url = "https://maps.googleapis.com/maps/api"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def geocode(
        self,
        address: str,
    ) -> dict[str, Any] | None:
        """Geocode an address to coordinates.

        Args:
            address: Address string

        Returns:
            Geocoding result with lat, lng
        """
        if not self.api_key:
            logger.warning("Google Maps API key not configured")
            return None

        try:
            url = f"{self.base_url}/geocode/json"
            params = {
                "address": address,
                "key": self.api_key,
            }

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                location = result.get("geometry", {}).get("location", {})

                return {
                    "address": result.get("formatted_address"),
                    "lat": location.get("lat"),
                    "lng": location.get("lng"),
                    "place_id": result.get("place_id"),
                }

            return None

        except Exception as e:
            logger.error(f"Geocoding failed for {address}: {e}")
            return None

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
            Reverse geocoding result
        """
        if not self.api_key:
            return None

        try:
            url = f"{self.base_url}/geocode/json"
            params = {
                "latlng": f"{lat},{lng}",
                "key": self.api_key,
            }

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]

                return {
                    "address": result.get("formatted_address"),
                    "place_id": result.get("place_id"),
                    "types": result.get("types", []),
                }

            return None

        except Exception as e:
            logger.error(f"Reverse geocoding failed for {lat},{lng}: {e}")
            return None

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
        if not self.api_key:
            return []

        try:
            url = f"{self.base_url}/place/textsearch/json"
            params = {
                "query": query,
                "key": self.api_key,
            }

            if location:
                params["location"] = f"{location['lat']},{location['lng']}"
                params["radius"] = radius

            if type_:
                params["type"] = type_

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            places = []

            for result in data.get("results", []):
                place = {
                    "place_id": result.get("place_id"),
                    "name": result.get("name"),
                    "formatted_address": result.get("formatted_address"),
                    "types": result.get("types", []),
                    "rating": result.get("rating"),
                    "price_level": result.get("price_level"),
                }

                if result.get("geometry"):
                    location_data = result["geometry"].get("location", {})
                    place["lat"] = location_data.get("lat")
                    place["lng"] = location_data.get("lng")

                places.append(place)

            return places

        except Exception as e:
            logger.error(f"Place search failed: {e}")
            return []

    async def get_place_details(
        self,
        place_id: str,
    ) -> dict[str, Any] | None:
        """Get detailed information about a place.

        Args:
            place_id: Place ID

        Returns:
            Place details
        """
        if not self.api_key:
            return None

        try:
            url = f"{self.base_url}/place/details/json"
            params = {
                "place_id": place_id,
                "fields": "name,formatted_address,geometry,types,rating,price_level,opening_hours,photos,reviews",
                "key": self.api_key,
            }

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if data.get("status") == "OK":
                result = data.get("result", {})

                return {
                    "place_id": place_id,
                    "name": result.get("name"),
                    "formatted_address": result.get("formatted_address"),
                    "types": result.get("types", []),
                    "rating": result.get("rating"),
                    "price_level": result.get("price_level"),
                    "opening_hours": result.get("opening_hours"),
                    "photos": result.get("photos", []),
                    "reviews": result.get("reviews", []),
                }

            return None

        except Exception as e:
            logger.error(f"Failed to get place details for {place_id}: {e}")
            return None

    async def get_distance_matrix(
        self,
        origins: list[dict[str, float]],
        destinations: list[dict[str, float]],
        mode: str = "driving",
    ) -> dict[str, Any] | None:
        """Get distance matrix between locations.

        Args:
            origins: List of origin locations
            destinations: List of destination locations
            mode: Travel mode

        Returns:
            Distance matrix
        """
        if not self.api_key:
            return None

        try:
            url = f"{self.base_url}/distancematrix/json"
            params = {
                "origins": "|".join(f"{o['lat']},{o['lng']}" for o in origins),
                "destinations": "|".join(f"{d['lat']},{d['lng']}" for d in destinations),
                "mode": mode,
                "key": self.api_key,
            }

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if data.get("status") == "OK":
                rows = data.get("rows", [])
                matrix = []

                for row in rows:
                    elements = row.get("elements", [])
                    row_data = []

                    for element in elements:
                        if element.get("status") == "OK":
                            distance = element.get("distance", {}).get("value", 0)  # meters
                            duration = element.get("duration", {}).get("value", 0)  # seconds

                            row_data.append({
                                "distance_m": distance,
                                "distance_km": distance / 1000,
                                "duration_s": duration,
                                "duration_min": duration / 60,
                            })
                        else:
                            row_data.append(None)

                    matrix.append(row_data)

                return {
                    "origins": origins,
                    "destinations": destinations,
                    "matrix": matrix,
                    "mode": mode,
                }

            return None

        except Exception as e:
            logger.error(f"Distance matrix request failed: {e}")
            return None

    async def get_directions(
        self,
        origin: dict[str, float],
        destination: dict[str, float],
        mode: str = "driving",
        waypoints: list[dict[str, float]] | None = None,
    ) -> dict[str, Any] | None:
        """Get directions between locations.

        Args:
            origin: Origin location
            destination: Destination location
            mode: Travel mode
            waypoints: Optional waypoints

        Returns:
            Directions
        """
        if not self.api_key:
            return None

        try:
            url = f"{self.base_url}/directions/json"
            params = {
                "origin": f"{origin['lat']},{origin['lng']}",
                "destination": f"{destination['lat']},{destination['lng']}",
                "mode": mode,
                "key": self.api_key,
            }

            if waypoints:
                params["waypoints"] = "|".join(
                    f"{w['lat']},{w['lng']}" for w in waypoints
                )

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if data.get("status") == "OK":
                routes = data.get("routes", [])

                if routes:
                    route = routes[0]
                    leg = route.get("legs", [{}])[0]

                    return {
                        "distance_m": leg.get("distance", {}).get("value", 0),
                        "distance_km": leg.get("distance", {}).get("value", 0) / 1000,
                        "duration_s": leg.get("duration", {}).get("value", 0),
                        "duration_min": leg.get("duration", {}).get("value", 0) / 60,
                        "start_address": leg.get("start_address"),
                        "end_address": leg.get("end_address"),
                        "steps": leg.get("steps", []),
                        "overview_polyline": route.get("overview_polyline"),
                    }

            return None

        except Exception as e:
            logger.error(f"Directions request failed: {e}")
            return None

    async def get_nearby_search(
        self,
        location: dict[str, float],
        radius: int = 1000,
        type_: str | None = None,
        keyword: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search nearby places.

        Args:
            location: Center location
            radius: Search radius in meters
            type_: Optional place type
            keyword: Optional keyword

        Returns:
            List of nearby places
        """
        if not self.api_key:
            return []

        try:
            url = f"{self.base_url}/place/nearbysearch/json"
            params = {
                "location": f"{location['lat']},{location['lng']}",
                "radius": radius,
                "key": self.api_key,
            }

            if type_:
                params["type"] = type_

            if keyword:
                params["keyword"] = keyword

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            places = []

            for result in data.get("results", []):
                place = {
                    "place_id": result.get("place_id"),
                    "name": result.get("name"),
                    "types": result.get("types", []),
                    "rating": result.get("rating"),
                    "vicinity": result.get("vicinity"),
                }

                if result.get("geometry"):
                    location_data = result["geometry"].get("location", {})
                    place["lat"] = location_data.get("lat")
                    place["lng"] = location_data.get("lng")

                places.append(place)

            return places

        except Exception as e:
            logger.error(f"Nearby search failed: {e}")
            return []

    async def autocomplete_place(
        self,
        input_text: str,
        location: dict[str, float] | None = None,
        radius: int = 100000,
    ) -> list[dict[str, Any]]:
        """Get place autocomplete suggestions.

        Args:
            input_text: Input text
            location: Optional location for biasing
            radius: Radius for location bias

        Returns:
            List of predictions
        """
        if not self.api_key:
            return []

        try:
            url = f"{self.base_url}/place/autocomplete/json"
            params = {
                "input": input_text,
                "key": self.api_key,
            }

            if location:
                params["location"] = f"{location['lat']},{location['lng']}"
                params["radius"] = radius

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            predictions = []

            for prediction in data.get("predictions", []):
                predictions.append({
                    "place_id": prediction.get("place_id"),
                    "description": prediction.get("description"),
                    "types": prediction.get("types", []),
                })

            return predictions

        except Exception as e:
            logger.error(f"Place autocomplete failed: {e}")
            return []

    async def get_elevation(
        self,
        locations: list[dict[str, float]],
    ) -> list[float] | None:
        """Get elevation for locations.

        Args:
            locations: List of locations

        Returns:
            List of elevations in meters
        """
        if not self.api_key:
            return None

        try:
            url = f"{self.base_url}/elevation/json"
            params = {
                "locations": "|".join(f"{loc['lat']},{loc['lng']}" for loc in locations),
                "key": self.api_key,
            }

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if data.get("status") == "OK":
                return [
                    result.get("elevation", 0.0)
                    for result in data.get("results", [])
                ]

            return None

        except Exception as e:
            logger.error(f"Elevation request failed: {e}")
            return None

    async def get_static_map_url(
        self,
        center: dict[str, float],
        zoom: int = 13,
        size: str = "600x400",
        markers: list[dict[str, Any]] | None = None,
        path: list[dict[str, float]] | None = None,
    ) -> str:
        """Get static map URL.

        Args:
            center: Map center
            zoom: Zoom level
            size: Map size
            markers: Optional markers
            path: Optional path

        Returns:
            Static map URL
        """
        if not self.api_key:
            return ""

        base = f"{self.base_url}/staticmap"
        params = {
            "center": f"{center['lat']},{center['lng']}",
            "zoom": zoom,
            "size": size,
            "key": self.api_key,
        }

        # Add markers
        if markers:
            marker_strings = []
            for marker in markers:
                marker_params = []
                if marker.get("color"):
                    marker_params.append(f"color:{marker['color']}")
                if marker.get("label"):
                    marker_params.append(f"label:{marker['label']}")
                marker_params.append(f"{marker['lat']},{marker['lng']}")
                marker_strings.append("|".join(marker_params))

            params["markers"] = "|".join(marker_strings)

        # Add path
        if path:
            path_coords = "|".join(f"{p['lat']},{p['lng']}" for p in path)
            params["path"] = f"enc:{path_coords}"

        # Build URL
        param_string = "&".join(f"{k}={v}" for k, v in params.items())

        return f"{base}?{param_string}"


# Global instance
google_maps_client = GoogleMapsClient()


def get_google_maps_client() -> GoogleMapsClient:
    """Get Google Maps client instance.

    Returns:
        Google Maps client instance
    """
    return google_maps_client
