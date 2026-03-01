"""Unit tests for maps modules."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.maps.client import GoogleMapsClient
from src.maps.renderer import MapRenderer
from src.services.map_service import MapService


@pytest.fixture
def sample_locations():
    """Create sample locations."""
    return [
        {"lat": 40.7128, "lng": -74.0060},
        {"lat": 40.7580, "lng": -73.9855},
        {"lat": 40.7829, "lng": -73.9654},
    ]


@pytest.fixture
def sample_pois():
    """Create sample POIs."""
    return [
        {
            "id": "poi_1",
            "name": "Central Park",
            "category": "park",
            "latitude": 40.7829,
            "longitude": -73.9654,
            "rating": 4.8,
            "description": "A beautiful park",
        },
        {
            "id": "poi_2",
            "name": "Times Square",
            "category": "attraction",
            "latitude": 40.7580,
            "longitude": -73.9855,
            "rating": 4.5,
            "description": "Major commercial intersection",
        },
    ]


class TestGoogleMapsClient:
    """Test Google Maps client."""

    @pytest.mark.asyncio
    async def test_geocode(self):
        """Test geocoding."""
        client = GoogleMapsClient(api_key="test_key")

        mock_response = {
            "status": "OK",
            "results": [{
                "formatted_address": "New York, NY, USA",
                "geometry": {
                    "location": {"lat": 40.7128, "lng": -74.0060}
                },
                "place_id": "test_place",
            }]
        }

        with patch.object(client.client, 'get', return_value=MagicMock(
            raise_for_status=MagicMock(),
            json=lambda: mock_response
        )):
            result = await client.geocode("New York, NY")

            assert result is not None
            assert result["lat"] == 40.7128
            assert result["lng"] == -74.0060

    @pytest.mark.asyncio
    async def test_reverse_geocode(self):
        """Test reverse geocoding."""
        client = GoogleMapsClient(api_key="test_key")

        mock_response = {
            "status": "OK",
            "results": [{
                "formatted_address": "New York, NY, USA",
                "place_id": "test_place",
                "types": ["locality"],
            }]
        }

        with patch.object(client.client, 'get', return_value=MagicMock(
            raise_for_status=MagicMock(),
            json=lambda: mock_response
        )):
            result = await client.reverse_geocode(40.7128, -74.0060)

            assert result is not None
            assert result["address"] == "New York, NY, USA"

    @pytest.mark.asyncio
    async def test_search_places(self):
        """Test searching places."""
        client = GoogleMapsClient(api_key="test_key")

        mock_response = {
            "results": [{
                "place_id": "test_1",
                "name": "Test Restaurant",
                "geometry": {"location": {"lat": 40.7128, "lng": -74.0060}},
                "types": ["restaurant"],
                "rating": 4.5,
            }]
        }

        with patch.object(client.client, 'get', return_value=MagicMock(
            raise_for_status=MagicMock(),
            json=lambda: mock_response
        )):
            results = await client.search_places("restaurants")

            assert len(results) == 1
            assert results[0]["name"] == "Test Restaurant"

    @pytest.mark.asyncio
    async def test_get_distance_matrix(self, sample_locations):
        """Test getting distance matrix."""
        client = GoogleMapsClient(api_key="test_key")

        mock_response = {
            "status": "OK",
            "rows": [
                {
                    "elements": [
                        {
                            "status": "OK",
                            "distance": {"value": 1000},
                            "duration": {"value": 300},
                        },
                        {
                            "status": "OK",
                            "distance": {"value": 2000},
                            "duration": {"value": 600},
                        },
                    ]
                }
            ]
        }

        with patch.object(client.client, 'get', return_value=MagicMock(
            raise_for_status=MagicMock(),
            json=lambda: mock_response
        )):
            result = await client.get_distance_matrix(
                origins=sample_locations[:1],
                destinations=sample_locations[1:],
            )

            assert result is not None
            assert "matrix" in result
            assert len(result["matrix"]) == 1
            assert len(result["matrix"][0]) == 2

    @pytest.mark.asyncio
    async def test_get_directions(self, sample_locations):
        """Test getting directions."""
        client = GoogleMapsClient(api_key="test_key")

        mock_response = {
            "status": "OK",
            "routes": [{
                "legs": [{
                    "distance": {"value": 5000},
                    "duration": {"value": 1800},
                    "start_address": "Start",
                    "end_address": "End",
                    "steps": [],
                }]
            }],
            "overview_polyline": {"points": "encoded_path"},
        }

        with patch.object(client.client, 'get', return_value=MagicMock(
            raise_for_status=MagicMock(),
            json=lambda: mock_response
        )):
            result = await client.get_directions(
                origin=sample_locations[0],
                destination=sample_locations[1],
            )

            assert result is not None
            assert result["distance_m"] == 5000
            assert result["duration_min"] == 30

    @pytest.mark.asyncio
    async def test_get_static_map_url(self, sample_locations):
        """Test getting static map URL."""
        client = GoogleMapsClient(api_key="test_key")

        url = await client.get_static_map_url(
            center=sample_locations[0],
            zoom=13,
            size="600x400",
        )

        assert url is not None
        assert "maps.googleapis.com" in url
        assert "test_key" in url


class TestMapRenderer:
    """Test map renderer."""

    @pytest.mark.asyncio
    async def test_render_static_map(self, sample_pois):
        """Test rendering static map."""
        renderer = MapRenderer()

        result = await renderer.render_static_map(
            center={"lat": 40.7128, "lng": -74.0060},
            zoom=13,
            width=600,
            height=400,
        )

        assert "url" in result
        assert "center" in result
        assert result["zoom"] == 13

    @pytest.mark.asyncio
    async def test_render_poi_map(self, sample_pois):
        """Test rendering POI map."""
        renderer = MapRenderer()

        result = await renderer.render_poi_map(
            pois=sample_pois,
            zoom=13,
        )

        assert "url" in result
        assert result["markers_count"] == 2

    @pytest.mark.asyncio
    async def test_render_route_map(self, sample_pois):
        """Test rendering route map."""
        renderer = MapRenderer()

        route = {
            "pois": sample_pois,
        }

        result = await renderer.render_route_map(route)

        assert "url" in result
        assert result["has_path"] is True

    @pytest.mark.asyncio
    async def test_generate_geojson(self, sample_pois):
        """Test generating GeoJSON."""
        renderer = MapRenderer()

        geojson = await renderer.generate_geojson(sample_pois)

        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == 2
        assert geojson["features"][0]["geometry"]["type"] == "Point"

    @pytest.mark.asyncio
    async def test_generate_route_geojson(self, sample_pois):
        """Test generating route GeoJSON."""
        renderer = MapRenderer()

        route = {"pois": sample_pois}

        geojson = await renderer.generate_route_geojson(route)

        assert geojson["type"] == "FeatureCollection"
        assert any(f["geometry"]["type"] == "LineString" for f in geojson["features"])

    def test_calculate_center(self, sample_pois):
        """Test calculating center from POIs."""
        renderer = MapRenderer()

        center = renderer._calculate_center(sample_pois)

        assert "lat" in center
        assert "lng" in center
        assert center["lat"] == pytest.approx(40.77045)

    def test_calculate_bounds(self, sample_pois):
        """Test calculating bounds from POIs."""
        renderer = MapRenderer()

        bounds = renderer._calculate_bounds(sample_pois)

        assert "min_lat" in bounds
        assert "max_lat" in bounds
        assert "min_lng" in bounds
        assert "max_lng" in bounds


class TestInteractiveMapRenderer:
    """Test interactive map renderer."""

    @pytest.mark.asyncio
    async def test_render_interactive_map(self, sample_pois):
        """Test rendering interactive map."""
        from src.maps.renderer import InteractiveMapRenderer

        renderer = InteractiveMapRenderer()

        result = await renderer.render_interactive_map(
            pois=sample_pois,
            width="100%",
            height="400px",
        )

        assert "html" in result
        assert "map_id" in result
        assert "<div" in result["html"]
        assert "google.maps.Map" in result["html"]


class TestMapService:
    """Test map service."""

    @pytest.mark.asyncio
    async def test_geocode_address(self, sample_pois):
        """Test geocoding address."""
        from unittest.mock import AsyncMock
        from sqlalchemy.ext.asyncio import AsyncSession

        service = MapService(AsyncMock(spec=AsyncSession))

        with patch.object(service.client, 'geocode', return_value={"lat": 40.7128, "lng": -74.0060}):
            result = await service.geocode_address("New York, NY")

            assert result is not None
            assert result["lat"] == 40.7128

    @pytest.mark.asyncio
    async def test_batch_geocode(self):
        """Test batch geocoding."""
        from unittest.mock import AsyncMock
        from sqlalchemy.ext.asyncio import AsyncSession

        service = MapService(AsyncMock(spec=AsyncSession))

        addresses = ["New York, NY", "Los Angeles, CA"]

        with patch.object(service.client, 'geocode', return_value={"lat": 40.7128, "lng": -74.0060}):
            results = await service.batch_geocode(addresses)

            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_render_poi_map(self, sample_pois):
        """Test rendering POI map through service."""
        from unittest.mock import AsyncMock
        from sqlalchemy.ext.asyncio import AsyncSession

        service = MapService(AsyncMock(spec=AsyncSession))

        with patch.object(service.renderer, 'render_poi_map', return_value={"url": "test_url"}):
            result = await service.render_poi_map(
                pois=sample_pois,
                interactive=False,
            )

            assert "url" in result

    @pytest.mark.asyncio
    async def test_calculate_route_stats(self, sample_pois):
        """Test calculating route statistics."""
        from unittest.mock import AsyncMock
        from sqlalchemy.ext.asyncio import AsyncSession

        service = MapService(AsyncMock(spec=AsyncSession))

        route = {"pois": sample_pois}

        with patch.object(service.client, 'get_directions', return_value={
            "distance_km": 5.0,
            "duration_min": 60,
        }):
            stats = await service.calculate_route_stats(route)

            assert "total_pois" in stats
            assert "estimated_distance_km" in stats
            assert "estimated_duration_minutes" in stats
