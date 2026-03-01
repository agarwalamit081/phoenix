"""POI service for managing Points of Interest."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError, ValidationError
from src.poi.discovery import POIDiscovery, poi_discovery, poi_repository
from src.poi.enricher import POIEnricher, poi_enricher
from src.poi.importer import GooglePlacesImporter, POIImportBatch, poi_importer
from src.poi.matcher import POIMatcher, poi_matcher
from src.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class POIService:
    """Service for managing POIs."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        """Initialize POI service.

        Args:
            session: Database session
        """
        self.session = session
        self.discovery = poi_discovery
        self.repository = poi_repository
        self.enricher = poi_enricher
        self.matcher = poi_matcher

    async def import_from_google_places(
        self,
        query: str,
        location: dict[str, float] | None = None,
        radius: int = 5000,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Import POIs from Google Places API.

        Args:
            query: Search query
            location: Optional center location
            radius: Search radius in meters
            limit: Maximum POIs to import

        Returns:
            List of imported POIs
        """
        importer = poi_importer

        try:
            places = await importer.import_places(
                query=query,
                location=location,
                radius=radius,
                limit=limit,
            )

            # Enrich with embeddings
            enriched = await self.enricher.enrich_batch(
                places,
                generate_embeddings=True,
                generate_summaries=True,
            )

            # Add to repository
            for poi in enriched:
                poi["id"] = str(uuid.uuid4())
                self.repository.add_poi(poi)

            logger.info(f"Imported {len(enriched)} POIs from Google Places")

            return enriched

        finally:
            await importer.close()

    async def batch_import(
        self,
        location: dict[str, float],
        categories: list[str],
        limit_per_category: int = 10,
    ) -> dict[str, list[dict[str, Any]]]:
        """Batch import POIs by category.

        Args:
            location: Center location
            categories: Categories to import
            limit_per_category: Max POIs per category

        Returns:
            Imported POIs by category
        """
        batch = POIImportBatch()

        try:
            results = await batch.import_by_categories(
                location=location,
                categories=categories,
                radius=5000,
                limit_per_category=limit_per_category,
            )

            # Enrich all imported POIs
            all_pois = []

            for category, pois in results.items():
                enriched = await self.enricher.enrich_batch(pois)
                results[category] = enriched
                all_pois.extend(enriched)

                # Add to repository
                for poi in enriched:
                    poi["id"] = str(uuid.uuid4())
                    self.repository.add_poi(poi)

            logger.info(f"Batch import complete: {batch.get_stats()}")

            return results

        finally:
            await batch.cleanup()

    async def search_pois(
        self,
        query: str,
        location: dict[str, float] | None = None,
        radius: int = 5000,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search for POIs.

        Args:
            query: Search query
            location: Optional center location
            radius: Search radius
            limit: Maximum results

        Returns:
            List of POIs
        """
        # First check repository
        repository_pois = list(self.repository._pois.values())

        # Simple text search on repository POIs
        matching = []
        query_lower = query.lower()

        for poi in repository_pois:
            if (
                query_lower in poi.get("name", "").lower() or
                query_lower in poi.get("category", "").lower() or
                query_lower in " ".join(poi.get("types", [])).lower()
            ):
                matching.append(poi)

        if len(matching) >= limit:
            return matching[:limit]

        # If not enough in repository, search Google Places
        try:
            google_pois = await self.discovery.search_nearby(
                location=location or {"lat": 0, "lng": 0},
                query=query,
                radius=radius,
                limit=limit,
            )

            # Add new POIs to repository
            for poi in google_pois:
                if not poi.get("id"):
                    poi["id"] = str(uuid.uuid4())
                self.repository.add_poi(poi)

            return google_pois

        except Exception as e:
            logger.error(f"Google Places search failed: {e}")

        return matching[:limit]

    async def get_poi(self, poi_id: str) -> dict[str, Any]:
        """Get a POI by ID.

        Args:
            poi_id: POI ID

        Returns:
            POI data

        Raises:
            NotFoundError: If POI not found
        """
        poi = self.repository.get_poi(poi_id)

        if not poi:
            raise NotFoundError("POI", poi_id)

        return poi

    async def get_nearby_pois(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 1.0,
        category: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get POIs near a location.

        Args:
            latitude: Latitude
            longitude: Longitude
            radius_km: Search radius in km
            category: Optional category filter
            limit: Maximum results

        Returns:
            List of nearby POIs
        """
        pois = self.repository.get_nearby(latitude, longitude, radius_km)

        # Filter by category if specified
        if category:
            pois = [p for p in pois if p.get("category") == category]

        return pois[:limit]

    async def recommend_pois(
        self,
        user_id: uuid.UUID,
        preferences: list[dict[str, Any]],
        location: dict[str, float] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get personalized POI recommendations.

        Args:
            user_id: User ID
            preferences: User preferences
            location: Optional location filter
            limit: Maximum recommendations

        Returns:
            List of recommended POIs
        """
        # Get all POIs
        all_pois = list(self.repository._pois.values())

        # Filter by location if specified
        if location:
            nearby_pois = self.repository.get_nearby(
                location["lat"],
                location["lng"],
                radius_km=50,
            )
        else:
            nearby_pois = all_pois

        # Rank by preferences
        ranked = await self.matcher.rank_pois(nearby_pois, preferences, limit=limit)

        # Get POIs in ranked order
        poi_map = {p.get("id"): p for p in all_pois}

        recommendations = []
        for r in ranked:
            poi_id = r["poi_id"]
            if poi_id in poi_map:
                recommendations.append({
                    **poi_map[poi_id],
                    "recommendation_score": r["score"],
                })

        return recommendations

    async def get_similar_pois(
        self,
        poi_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find POIs similar to a given POI.

        Args:
            poi_id: Reference POI ID
            limit: Maximum results

        Returns:
            List of similar POIs
        """
        poi = await self.get_poi(poi_id)

        all_pois = list(self.repository._pois.values())

        similar = await self.matcher.find_similar_pois(poi, all_pois, limit)

        # Get full POI data
        poi_map = {p.get("id"): p for p in all_pois}

        results = []
        for s in similar:
            poi_id = s["poi_id"]
            if poi_id in poi_map:
                results.append({
                    **poi_map[poi_id],
                    "similarity": s["similarity"],
                })

        return results

    async def get_poi_stats(self) -> dict[str, Any]:
        """Get POI statistics.

        Returns:
            POI statistics
        """
        return self.repository.get_stats()

    async def enrich_existing_pois(
        self,
        generate_embeddings: bool = True,
        generate_summaries: bool = True,
    ) -> dict[str, Any]:
        """Enrich existing POIs with embeddings and summaries.

        Args:
            generate_embeddings: Whether to generate embeddings
            generate_summaries: Whether to generate summaries

        Returns:
            Enrichment results
        """
        all_pois = list(self.repository._pois.values())

        enriched = await self.enricher.enrich_batch(
            all_pois,
            generate_embeddings=generate_embeddings,
            generate_summaries=generate_summaries,
        )

        # Update repository
        for poi in enriched:
            self.repository.add_poi(poi)

        return {
            "total": len(all_pois),
            "enriched": len(enriched),
            "with_embeddings": sum(1 for p in enriched if p.get("embedding")),
            "with_summaries": sum(1 for p in enriched if p.get("summary")),
        }

    async def delete_poi(self, poi_id: str) -> bool:
        """Delete a POI from repository.

        Args:
            poi_id: POI ID

        Returns:
            True if deleted
        """
        if poi_id in self.repository._pois:
            del self.repository._pois[poi_id]
            return True
        return False

    async def get_categories(self) -> list[str]:
        """Get all available POI categories.

        Returns:
            List of categories
        """
        return list(self.repository._by_category.keys())


# Global instance factory
def get_poi_service(session: AsyncSession) -> POIService:
    """Get POI service instance.

    Args:
        session: Database session

    Returns:
        POI service instance
    """
    return POIService(session)
