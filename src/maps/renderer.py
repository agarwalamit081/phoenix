"""Map renderer for generating map visualizations."""

import asyncio
import base64
import hashlib
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any

from src.maps.client import GoogleMapsClient, get_google_maps_client

logger = logging.getLogger(__name__)


class MapRenderer:
    """Render maps with POIs, routes, and other features."""

    def __init__(
        self,
        maps_client: GoogleMapsClient | None = None,
    ) -> None:
        """Initialize map renderer.

        Args:
            maps_client: Optional Google Maps client
        """
        self.maps_client = maps_client or get_google_maps_client()

    async def render_static_map(
        self,
        center: dict[str, float],
        zoom: int = 13,
        width: int = 600,
        height: int = 400,
        markers: list[dict[str, Any]] | None = None,
        path: list[dict[str, float]] | None = None,
        style: str | None = None,
    ) -> dict[str, Any]:
        """Render a static map image.

        Args:
            center: Map center
            zoom: Zoom level
            width: Map width
            height: Map height
            markers: Optional markers
            path: Optional path
            style: Optional map style

        Returns:
            Map render result with URL
        """
        size = f"{width}x{height}"

        url = await self.maps_client.get_static_map_url(
            center=center,
            zoom=zoom,
            size=size,
            markers=markers,
            path=path,
        )

        return {
            "url": url,
            "center": center,
            "zoom": zoom,
            "size": {"width": width, "height": height},
            "markers_count": len(markers) if markers else 0,
            "has_path": path is not None,
            "style": style,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def render_poi_map(
        self,
        pois: list[dict[str, Any]],
        center: dict[str, float] | None = None,
        zoom: int = 13,
        width: int = 800,
        height: int = 600,
    ) -> dict[str, Any]:
        """Render map with POIs.

        Args:
            pois: List of POIs
            center: Optional map center
            zoom: Zoom level
            width: Map width
            height: Map height

        Returns:
            Map render result
        """
        if not center and pois:
            # Calculate center from POIs
            center = self._calculate_center(pois)

        if not center:
            center = {"lat": 0, "lng": 0}

        # Build markers
        markers = []

        for poi in pois:
            marker = {
                "lat": poi.get("latitude", poi.get("lat", 0)),
                "lng": poi.get("longitude", poi.get("lng", 0)),
                "color": self._get_marker_color(poi),
            }

            # Add label for top rated POIs
            rating = poi.get("rating")
            if rating and rating >= 4.5:
                marker["label"] = poi.get("name", "")[:1].upper()

            markers.append(marker)

        return await self.render_static_map(
            center=center,
            zoom=zoom,
            width=width,
            height=height,
            markers=markers,
        )

    async def render_route_map(
        self,
        route: dict[str, Any],
        width: int = 800,
        height: int = 600,
    ) -> dict[str, Any]:
        """Render map with route.

        Args:
            route: Route data with POIs
            width: Map width
            height: Map height

        Returns:
            Map render result
        """
        pois = route.get("pois", [])

        if not pois:
            return {
                "error": "No POIs in route",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        # Calculate bounds
        bounds = self._calculate_bounds(pois)

        # Build path coordinates
        path = [
            {
                "lat": poi.get("latitude", poi.get("lat", 0)),
                "lng": poi.get("longitude", poi.get("lng", 0)),
            }
            for poi in pois
        ]

        # Calculate center
        center = {
            "lat": (bounds["min_lat"] + bounds["max_lat"]) / 2,
            "lng": (bounds["min_lng"] + bounds["max_lng"]) / 2,
        }

        # Calculate zoom from bounds
        zoom = self._calculate_zoom_from_bounds(bounds)

        # Build markers with numbered labels
        markers = []

        for i, poi in enumerate(pois, 1):
            markers.append({
                "lat": poi.get("latitude", poi.get("lat", 0)),
                "lng": poi.get("longitude", poi.get("lng", 0)),
                "label": str(i),
                "color": "blue" if i == 1 or i == len(pois) else "red",
            })

        return await self.render_static_map(
            center=center,
            zoom=zoom,
            width=width,
            height=height,
            markers=markers,
            path=path,
        )

    def _calculate_center(
        self,
        pois: list[dict[str, Any]],
    ) -> dict[str, float]:
        """Calculate center from POIs.

        Args:
            pois: List of POIs

        Returns:
            Center coordinates
        """
        if not pois:
            return {"lat": 0, "lng": 0}

        lats = [poi.get("latitude", poi.get("lat", 0)) for poi in pois]
        lngs = [poi.get("longitude", poi.get("lng", 0)) for poi in pois]

        return {
            "lat": sum(lats) / len(lats),
            "lng": sum(lngs) / len(lngs),
        }

    def _calculate_bounds(
        self,
        pois: list[dict[str, Any]],
    ) -> dict[str, float]:
        """Calculate bounds from POIs.

        Args:
            pois: List of POIs

        Returns:
            Bounds
        """
        lats = [poi.get("latitude", poi.get("lat", 0)) for poi in pois]
        lngs = [poi.get("longitude", poi.get("lng", 0)) for poi in pois]

        return {
            "min_lat": min(lats),
            "max_lat": max(lats),
            "min_lng": min(lngs),
            "max_lng": max(lngs),
        }

    def _calculate_zoom_from_bounds(
        self,
        bounds: dict[str, float],
    ) -> int:
        """Calculate zoom level from bounds.

        Args:
            bounds: Bounds

        Returns:
            Zoom level
        """
        lat_diff = bounds["max_lat"] - bounds["min_lat"]
        lng_diff = bounds["max_lng"] - bounds["min_lng"]

        # Rough approximation
        max_diff = max(lat_diff, lng_diff)

        if max_diff < 0.01:
            return 15
        elif max_diff < 0.05:
            return 13
        elif max_diff < 0.1:
            return 12
        elif max_diff < 0.5:
            return 10
        elif max_diff < 1.0:
            return 8
        else:
            return 6

    def _get_marker_color(self, poi: dict[str, Any]) -> str:
        """Get marker color based on POI type.

        Args:
            poi: POI data

        Returns:
            Marker color
        """
        category = poi.get("category", "").lower()

        color_map = {
            "restaurant": "red",
            "cafe": "orange",
            "museum": "purple",
            "attraction": "blue",
            "park": "green",
            "shopping": "pink",
            "hotel": "blue",
        }

        return color_map.get(category, "blue")

    async def generate_geojson(
        self,
        pois: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate GeoJSON from POIs.

        Args:
            pois: List of POIs

        Returns:
            GeoJSON feature collection
        """
        features = []

        for poi in pois:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        poi.get("longitude", poi.get("lng", 0)),
                        poi.get("latitude", poi.get("lat", 0)),
                    ],
                },
                "properties": {
                    "name": poi.get("name"),
                    "category": poi.get("category"),
                    "rating": poi.get("rating"),
                },
            }

            features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features,
        }

    async def generate_route_geojson(
        self,
        route: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate GeoJSON for route.

        Args:
            route: Route data

        Returns:
            GeoJSON with LineString
        """
        pois = route.get("pois", [])

        if not pois:
            return {
                "type": "FeatureCollection",
                "features": [],
            }

        # Create LineString for route
        coordinates = [
            [
                poi.get("longitude", poi.get("lng", 0)),
                poi.get("latitude", poi.get("lat", 0)),
            ]
            for poi in pois
        ]

        # Create Point features for each POI
        features = [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordinates,
                },
                "properties": {
                    "type": "route",
                    "total_pois": len(pois),
                },
            }
        ]

        # Add POI features
        for i, poi in enumerate(pois):
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        poi.get("longitude", poi.get("lng", 0)),
                        poi.get("latitude", poi.get("lat", 0)),
                    ],
                },
                "properties": {
                    "name": poi.get("name"),
                    "category": poi.get("category"),
                    "stop_number": i + 1,
                },
            })

        return {
            "type": "FeatureCollection",
            "features": features,
        }


class InteractiveMapRenderer(MapRenderer):
    """Renderer for interactive maps (HTML/JS)."""

    async def render_interactive_map(
        self,
        pois: list[dict[str, Any]],
        width: str = "100%",
        height: str = "400px",
        center: dict[str, float] | None = None,
        zoom: int = 13,
    ) -> dict[str, Any]:
        """Render interactive map HTML.

        Args:
            pois: List of POIs
            width: Map width
            height: Map height
            center: Optional center
            zoom: Zoom level

        Returns:
            HTML map code
        """
        if not center and pois:
            center = self._calculate_center(pois)

        if not center:
            center = {"lat": 0, "lng": 0}

        # Generate unique map ID
        map_id = f"map_{hashlib.md5(json.dumps(pois).encode()).hexdigest()[:8]}"

        # Build markers JSON
        markers_data = [
            {
                "position": {
                    "lat": poi.get("latitude", poi.get("lat", 0)),
                    "lng": poi.get("longitude", poi.get("lng", 0)),
                },
                "title": poi.get("name", "POI"),
                "description": poi.get("description", "")[:100],
            }
            for poi in pois
        ]

        html = f"""
        <div id="{map_id}" style="width: {width}; height: {height};"></div>
        <script>
            function initMap() {{
                const {map_id} = new google.maps.Map(document.getElementById("{map_id}"), {{
                    center: {{ lat: {center['lat']}, lng: {center['lng']} }},
                    zoom: {zoom},
                }});

                const markers = {json.dumps(markers_data)};

                markers.forEach(function(markerData) {{
                    const marker = new google.maps.Marker({{
                        position: markerData.position,
                        map: {map_id},
                        title: markerData.title,
                    }});

                    if (markerData.description) {{
                        const infoWindow = new google.maps.InfoWindow({{
                            content: '<div><h3>' + markerData.title + '</h3><p>' + markerData.description + '</p></div>'
                        }});

                        marker.addListener('click', function() {{
                            infoWindow.open({map_id}, marker);
                        }});
                    }}
                }});
            }}
        </script>
        <script src="https://maps.googleapis.com/maps/api/js?key={self.maps_client.api_key}&callback=initMap" async defer></script>
        """

        return {
            "map_id": map_id,
            "html": html,
            "center": center,
            "zoom": zoom,
            "markers_count": len(pois),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def render_interactive_route_map(
        self,
        route: dict[str, Any],
        width: str = "100%",
        height: str = "400px",
    ) -> dict[str, Any]:
        """Render interactive route map.

        Args:
            route: Route data
            width: Map width
            height: Map height

        Returns:
            HTML map code
        """
        pois = route.get("pois", [])

        if not pois:
            return {
                "error": "No POIs in route",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        bounds = self._calculate_bounds(pois)
        center = {
            "lat": (bounds["min_lat"] + bounds["max_lat"]) / 2,
            "lng": (bounds["min_lng"] + bounds["max_lng"]) / 2,
        }
        zoom = self._calculate_zoom_from_bounds(bounds)

        # Build markers with stop numbers
        markers_data = []

        for i, poi in enumerate(pois, 1):
            markers_data.append({
                "position": {
                    "lat": poi.get("latitude", poi.get("lat", 0)),
                    "lng": poi.get("longitude", poi.get("lng", 0)),
                },
                "title": f"Stop {i}: {poi.get('name', 'POI')}",
                "label": str(i),
            })

        # Build path
        path = [
            {
                "lat": poi.get("latitude", poi.get("lat", 0)),
                "lng": poi.get("longitude", poi.get("lng", 0)),
            }
            for poi in pois
        ]

        map_id = f"route_map_{hashlib.md5(json.dumps(route).encode()).hexdigest()[:8]}"

        html = f"""
        <div id="{map_id}" style="width: {width}; height: {height};"></div>
        <script>
            function initRouteMap() {{
                const {map_id} = new google.maps.Map(document.getElementById("{map_id}"), {{
                    center: {{ lat: {center['lat']}, lng: {center['lng']} }},
                    zoom: {zoom},
                }});

                // Draw path
                const pathCoords = {json.dumps(path)};

                const routePath = new google.maps.Polyline({{
                    path: pathCoords,
                    geodesic: true,
                    strokeColor: '#FF0000',
                    strokeOpacity: 1.0,
                    strokeWeight: 2,
                }});

                routePath.setMap({map_id});

                // Add markers
                const markers = {json.dumps(markers_data)};

                markers.forEach(function(markerData, index) {{
                    const marker = new google.maps.Marker({{
                        position: markerData.position,
                        map: {map_id},
                        title: markerData.title,
                        label: {{
                            text: markerData.label,
                            color: 'white',
                        }},
                    }});
                }});
            }}
        </script>
        <script src="https://maps.googleapis.com/maps/api/js?key={self.maps_client.api_key}&callback=initRouteMap" async defer></script>
        """

        return {
            "map_id": map_id,
            "html": html,
            "center": center,
            "zoom": zoom,
            "stops_count": len(pois),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# Global instances
map_renderer = MapRenderer()
interactive_renderer = InteractiveMapRenderer()


def get_map_renderer() -> MapRenderer:
    """Get map renderer instance.

    Returns:
        Map renderer instance
    """
    return map_renderer


def get_interactive_renderer() -> InteractiveMapRenderer:
    """Get interactive renderer instance.

    Returns:
        Interactive renderer instance
    """
    return interactive_renderer
