"""POI importer for importing places from Google Places API."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

import httpx

from src.config.settings import settings
from src.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


class GooglePlacesImporter:
    """Import POIs from Google Places API."""

    def __init__(
        self,
        api_key: str | None = None,
    ) -> None:
        """Initialize Google Places importer.

        Args:
            api_key: Google Places API key (defaults to settings)
        """
        self.api_key = api_key or settings.google_maps_api_key
        self.base_url = "https://places.googleapis.com/v1"

        if not self.api_key:
            logger.warning("Google Places API key not configured")

        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client.

        Returns:
            Async HTTP client
        """
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search_places(
        self,
        query: str,
        location: dict[str, float] | None = None,
        radius: int = 5000,
        language: str = "en",
    ) -> list[dict[str, Any]]:
        """Search for places using Google Places API.

        Args:
            query: Search query
            location: Center location {lat, lng}
            radius: Search radius in meters
            language: Language code

        Returns:
            List of place data
        """
        if not self.api_key:
            raise ExternalServiceError(
                service="Google Places",
                message="API key not configured",
            )

        client = await self._get_client()

        # Build request
        url = f"{self.base_url}/places:searchText"

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": ",".join([
                "places.id",
                "places.name",
                "places.displayName",
                "places.formattedAddress",
                "places.location",
                "places.types",
                "places.rating",
                "places.userRatingCount",
                "places.photos",
                "places.currentOpeningHours",
                "places.priceLevel",
                "places.editorialSummary",
            ]),
        }

        body = {
            "textQuery": query,
            "languageCode": language,
        }

        if location:
            body["locationRestriction"] = {
                "circle": {
                    "center": {
                        "latitude": location["lat"],
                        "longitude": location["lng"],
                    },
                    "radius": radius,
                },
            }

        try:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()

            data = response.json()
            places = data.get("places", [])

            logger.info(f"Found {len(places)} places for query: {query}")

            return places

        except httpx.HTTPStatusError as e:
            logger.error(f"Google Places API error: {e.response.status_code} - {e.response.text}")
            raise ExternalServiceError(
                service="Google Places",
                message=f"API request failed: {e.response.status_code}",
            )

        except Exception as e:
            logger.error(f"Failed to search places: {e}")
            raise

    async def get_place_details(
        self,
        place_id: str,
        language: str = "en",
    ) -> dict[str, Any] | None:
        """Get detailed information about a place.

        Args:
            place_id: Google Place ID
            language: Language code

        Returns:
            Place details or None
        """
        if not self.api_key:
            return None

        client = await self._get_client()

        url = f"{self.base_url}/places/{place_id}"

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": ",".join([
                "id",
                "name",
                "displayName",
                "formattedAddress",
                "location",
                "types",
                "rating",
                "userRatingCount",
                "photos",
                "currentOpeningHours",
                "priceLevel",
                "editorialSummary",
                "reviews",
            ]),
        }

        params = {"languageCode": language}

        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.error(f"Failed to get place details for {place_id}: {e}")
            return None

    async def search_nearby(
        self,
        location: dict[str, float],
        radius: int = 1000,
        type_filter: str | None = None,
        keyword: str | None = None,
        language: str = "en",
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Search for places near a location.

        Args:
            location: Center location {lat, lng}
            radius: Search radius in meters
            type_filter: Place type filter
            keyword: Search keyword
            language: Language code

        Yields:
            Place data
        """
        if not self.api_key:
            return

        # Build search query
        query_parts = []
        if type_filter:
            query_parts.append(type_filter)
        if keyword:
            query_parts.append(keyword)

        query = " ".join(query_parts) if query_parts else "points of interest"

        places = await self.search_places(
            query=query,
            location=location,
            radius=radius,
            language=language,
        )

        for place in places:
            yield place

    async def import_places(
        self,
        query: str,
        location: dict[str, float] | None = None,
        radius: int = 5000,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Import places from Google Places.

        Args:
            query: Search query
            location: Center location
            radius: Search radius
            limit: Maximum places to import

        Returns:
            List of imported place data
        """
        places = await self.search_places(query, location, radius)

        # Enrich with additional details
        enriched_places = []

        for i, place in enumerate(places[:limit]):
            place_id = place.get("id")

            if place_id:
                details = await self.get_place_details(place_id)

                if details:
                    place.update(details)

            # Normalize place data
            normalized = self._normalize_place(place)
            enriched_places.append(normalized)

            logger.info(f"Imported {i+1}/{min(len(places), limit)}: {normalized.get('name')}")

        return enriched_places

    def _normalize_place(self, place: dict[str, Any]) -> dict[str, Any]:
        """Normalize place data to standard format.

        Args:
            place: Raw place data from Google Places

        Returns:
            Normalized place data
        """
        loc = place.get("location", {})

        # Extract primary type from types list
        types = place.get("types", [])
        primary_type = types[0] if types else "establishment"

        # Get photo reference if available
        photo_ref = None
        if place.get("photos"):
            photos = place["photos"]
            if photos and len(photos) > 0:
                photo_ref = photos[0].get("name")

        return {
            "external_id": place.get("id"),
            "name": place.get("displayName", {}).get("text") or place.get("name"),
            "description": place.get("editorialSummary", {}).get("text"),
            "category": self._map_type_to_category(primary_type),
            "latitude": loc.get("latitude"),
            "longitude": loc.get("longitude"),
            "address": place.get("formattedAddress"),
            "rating": place.get("rating"),
            "review_count": place.get("userRatingCount"),
            "price_level": place.get("priceLevel"),
            "types": types,
            "photo_reference": photo_ref,
            "opening_hours": place.get("currentOpeningHours"),
            "source": "google_places",
            "imported_at": datetime.now(timezone.utc).isoformat(),
        }

    def _map_type_to_category(self, place_type: str) -> str:
        """Map Google Place type to internal category.

        Args:
            place_type: Google Place type

        Returns:
            Internal category
        """
        type_mapping = {
            "restaurant": "restaurant",
            "food": "restaurant",
            "cafe": "cafe",
            "bakery": "cafe",
            "bar": "bar",
            "night_club": "nightlife",
            "museum": "museum",
            "art_gallery": "museum",
            "tourist_attraction": "attraction",
            "park": "park",
            "natural_feature": "nature",
            "lodging": "accommodation",
            "hotel": "accommodation",
            "shopping_mall": "shopping",
            "store": "shopping",
            "transit_station": "transport",
            "subway_station": "transport",
            "airport": "transport",
        }

        # Try exact match first
        if place_type in type_mapping:
            return type_mapping[place_type]

        # Try partial match
        place_type_lower = place_type.lower()
        for key, value in type_mapping.items():
            if key in place_type_lower or place_type_lower in key:
                return value

        return "other"

    async def get_photo_url(
        self,
        photo_reference: str,
        max_width: int = 400,
    ) -> str | None:
        """Get URL for a place photo.

        Args:
            photo_reference: Photo reference from place data
            max_width: Maximum width in pixels

        Returns:
            Photo URL or None
        """
        if not self.api_key or not photo_reference:
            return None

        return (
            f"https://places.googleapis.com/v1/"
            f"{photo_reference}/media"
            f"?maxWidthPx={max_width}"
            f"&key={self.api_key}"
        )


class POIImportBatch:
    """Batch processor for POI imports."""

    def __init__(
        self,
        importer: GooglePlacesImporter | None = None,
    ) -> None:
        """Initialize batch processor.

        Args:
            importer: POI importer instance
        """
        self.importer = importer or GooglePlacesImporter()
        self._imported_count = 0
        self._failed_count = 0

    async def import_by_categories(
        self,
        location: dict[str, float],
        categories: list[str],
        radius: int = 5000,
        limit_per_category: int = 20,
    ) -> dict[str, list[dict[str, Any]]]:
        """Import places by category.

        Args:
            location: Center location
            categories: List of categories to import
            radius: Search radius
            limit_per_category: Max places per category

        Returns:
            Dictionary of imported places by category
        """
        results = {}

        for category in categories:
            try:
                places = await self.importer.import_places(
                    query=category,
                    location=location,
                    radius=radius,
                    limit=limit_per_category,
                )

                results[category] = places
                self._imported_count += len(places)

                logger.info(f"Imported {len(places)} {category} places")

            except Exception as e:
                logger.error(f"Failed to import {category}: {e}")
                self._failed_count += 1
                results[category] = []

        return results

    async def import_by_queries(
        self,
        queries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Import places by custom queries.

        Args:
            queries: List of query dictionaries with keys:
                - query: Search query
                - location: Optional location
                - radius: Optional radius
                - limit: Optional limit

        Returns:
            List of all imported places
        """
        all_places = []

        for query_config in queries:
            try:
                places = await self.importer.import_places(
                    query=query_config.get("query"),
                    location=query_config.get("location"),
                    radius=query_config.get("radius", 5000),
                    limit=query_config.get("limit", 20),
                )

                all_places.extend(places)
                self._imported_count += len(places)

            except Exception as e:
                logger.error(f"Failed to import '{query_config.get('query')}': {e}")
                self._failed_count += 1

        logger.info(f"Batch import complete: {self._imported_count} imported, {self._failed_count} failed")

        return all_places

    def get_stats(self) -> dict[str, int]:
        """Get import statistics.

        Returns:
            Import statistics
        """
        return {
            "imported": self._imported_count,
            "failed": self._failed_count,
        }

    async def cleanup(self) -> None:
        """Clean up resources."""
        await self.importer.close()


# Global instance
poi_importer = GooglePlacesImporter()
