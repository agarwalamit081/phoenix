"""Unit tests for POI modules."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.poi.importer import GooglePlacesImporter
from src.poi.enricher import POIEnricher
from src.poi.matcher import POIMatcher
from src.poi.discovery import POIDiscovery, POIRepository


@pytest.fixture
def mock_poi():
    """Create a mock POI."""
    return {
        "id": "test_poi_1",
        "name": "Test Restaurant",
        "category": "restaurant",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "rating": 4.5,
        "description": "A great test restaurant",
        "types": ["restaurant", "food"],
    }


@pytest.fixture
def mock_preferences():
    """Create mock user preferences."""
    return [
        {
            "category": "category",
            "preference_type": "like",
            "value": "restaurant",
        },
        {
            "category": "rating",
            "preference_type": "like",
            "value": "4.0",
        },
    ]


class TestPOIRepository:
    """Test POI repository."""

    def test_add_poi(self, mock_poi):
        """Test adding a POI to repository."""
        repo = POIRepository()
        repo.add_poi(mock_poi)

        retrieved = repo.get_poi("test_poi_1")
        assert retrieved is not None
        assert retrieved["name"] == "Test Restaurant"

    def test_get_by_category(self, mock_poi):
        """Test getting POIs by category."""
        repo = POIRepository()
        repo.add_poi(mock_poi)

        restaurants = repo.get_by_category("restaurant")
        assert len(restaurants) == 1
        assert restaurants[0]["category"] == "restaurant"

    def test_get_nearby(self, mock_poi):
        """Test getting nearby POIs."""
        repo = POIRepository()
        repo.add_poi(mock_poi)

        nearby = repo.get_nearby(40.71, -74.00, radius_km=10)
        assert len(nearby) == 1
        assert "distance_km" in nearby[0]


class TestPOIMatcher:
    """Test POI matcher."""

    @pytest.mark.asyncio
    async def test_calculate_match_score(self, mock_poi, mock_preferences):
        """Test calculating match score."""
        matcher = POIMatcher()

        score = await matcher.calculate_match_score(mock_poi, mock_preferences)

        assert "score" in score
        assert "factors" in score
        assert 0 <= score["score"] <= 1

    @pytest.mark.asyncio
    async def test_rank_pois(self, mock_poi, mock_preferences):
        """Test ranking POIs."""
        matcher = POIMatcher()

        # Create multiple POIs
        pois = [
            mock_poi,
            {
                **mock_poi,
                "id": "test_poi_2",
                "name": "Test Museum",
                "category": "museum",
                "rating": 3.5,
            },
        ]

        ranked = await matcher.rank_pois(pois, mock_preferences)

        assert len(ranked) == 2
        # Restaurant should rank higher due to preference
        assert ranked[0]["poi_id"] == "test_poi_1"


class TestPOIEnricher:
    """Test POI enricher."""

    @pytest.mark.asyncio
    async def test_enrich_poi(self, mock_poi):
        """Test enriching a POI."""
        enricher = POIEnricher()

        # Mock embedding generation
        with patch.object(enricher.embedding_service, 'generate_embedding', return_value=[0.1] * 1536):
            enriched = await enricher.enrich_poi(
                mock_poi,
                generate_embedding=True,
                generate_summary=False,
            )

            assert "embedding" in enriched
            assert "enriched_at" in enriched

    @pytest.mark.asyncio
    async def test_enrich_batch(self, mock_poi):
        """Test batch enrichment."""
        enricher = POIEnricher()

        pois = [mock_poi] * 3

        with patch.object(enricher.embedding_service, 'generate_embedding', return_value=[0.1] * 1536):
            enriched = await enricher.enrich_batch(
                pois,
                generate_embeddings=True,
                generate_summaries=False,
            )

            assert len(enriched) == 3


class TestPOIDiscovery:
    """Test POI discovery."""

    @pytest.mark.asyncio
    async def test_search_nearby(self):
        """Test searching nearby POIs."""
        discovery = POIDiscovery()

        location = {"lat": 40.7128, "lng": -74.0060}

        # Mock the importer
        with patch.object(discovery.importer, 'import_places', return_value=[]):
            results = await discovery.search_nearby(
                location=location,
                query="restaurant",
                radius=1000,
            )

            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_discover_by_category(self):
        """Test discovering POIs by category."""
        discovery = POIDiscovery()

        location = {"lat": 40.7128, "lng": -74.0060}
        categories = ["restaurant", "museum"]

        # Mock the search_nearby method
        with patch.object(discovery, 'search_nearby', return_value=[]):
            results = await discovery.discover_by_category(
                location=location,
                categories=categories,
            )

            assert "restaurant" in results
            assert "museum" in results
