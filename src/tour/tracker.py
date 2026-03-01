"""GPS tracker for monitoring user location during tours."""

import asyncio
import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class LocationAccuracy(str, Enum):
    """GPS accuracy levels."""

    EXCELLENT = "excellent"  # < 5m
    GOOD = "good"  # 5-10m
    FAIR = "fair"  # 10-20m
    POOR = "poor"  # > 20m


class MovementState(str, Enum):
    """User movement state."""

    STATIONARY = "stationary"
    WALKING = "walking"
    RUNNING = "running"
    DRIVING = "driving"
    UNKNOWN = "unknown"


@dataclass
class LocationReading:
    """Single GPS location reading."""

    latitude: float
    longitude: float
    accuracy: float | None = None  # in meters
    altitude: float | None = None  # in meters
    speed: float | None = None  # in m/s
    heading: float | None = None  # degrees from north
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "gps"  # gps, network, passive

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "accuracy": self.accuracy,
            "altitude": self.altitude,
            "speed": self.speed,
            "heading": self.heading,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
        }

    @property
    def accuracy_level(self) -> LocationAccuracy:
        """Get accuracy level.

        Returns:
            Accuracy level
        """
        if self.accuracy is None:
            return LocationAccuracy.POOR

        if self.accuracy < 5:
            return LocationAccuracy.EXCELLENT
        elif self.accuracy < 10:
            return LocationAccuracy.GOOD
        elif self.accuracy < 20:
            return LocationAccuracy.FAIR
        else:
            return LocationAccuracy.POOR


@dataclass
class LocationHistory:
    """Location history for a tour."""

    tour_id: str
    user_id: uuid.UUID
    readings: deque[LocationReading] = field(default_factory=lambda: deque(maxlen=1000))
    distance_meters: float = 0.0
    duration_seconds: int = 0
    started_at: datetime | None = None
    last_update: datetime | None = None

    def add_reading(self, reading: LocationReading) -> float:
        """Add a location reading.

        Args:
            reading: Location reading

        Returns:
            Distance traveled since last reading in meters
        """
        distance = 0.0

        if self.readings:
            last_reading = self.readings[-1]
            distance = GPSTracker.calculate_distance(
                last_reading.latitude,
                last_reading.longitude,
                reading.latitude,
                reading.longitude,
            )
            self.distance_meters += distance

            # Update duration
            if last_reading.timestamp:
                elapsed = (reading.timestamp - last_reading.timestamp).total_seconds()
                self.duration_seconds += int(elapsed)

        self.readings.append(reading)
        self.last_update = reading.timestamp

        if not self.started_at:
            self.started_at = reading.timestamp

        return distance

    def get_recent_readings(
        self,
        count: int = 10,
    ) -> list[LocationReading]:
        """Get recent location readings.

        Args:
            count: Number of readings to return

        Returns:
            List of recent readings
        """
        return list(self.readings)[-count:]

    def get_average_speed(self) -> float | None:
        """Calculate average speed.

        Returns:
            Average speed in m/s
        """
        if self.duration_seconds == 0:
            return None

        return self.distance_meters / self.duration_seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "tour_id": self.tour_id,
            "user_id": str(self.user_id),
            "total_readings": len(self.readings),
            "distance_meters": self.distance_meters,
            "duration_seconds": self.duration_seconds,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "average_speed_mps": self.get_average_speed(),
        }


class GPSTracker:
    """GPS tracker for monitoring user location during tours."""

    def __init__(
        self,
        min_accuracy: float = 50.0,  # meters
        max_reading_age_seconds: int = 300,  # 5 minutes
        smoothing_window: int = 5,
    ) -> None:
        """Initialize GPS tracker.

        Args:
            min_accuracy: Minimum accuracy threshold (meters)
            max_reading_age_seconds: Maximum age of readings to consider
            smoothing_window: Window size for position smoothing
        """
        self.min_accuracy = min_accuracy
        self.max_reading_age_seconds = max_reading_age_seconds
        self.smoothing_window = smoothing_window
        self._histories: dict[str, LocationHistory] = {}

    async def start_tracking(
        self,
        tour_id: str,
        user_id: uuid.UUID,
    ) -> LocationHistory:
        """Start tracking a tour.

        Args:
            tour_id: Tour ID
            user_id: User ID

        Returns:
            Location history instance
        """
        history = LocationHistory(
            tour_id=tour_id,
            user_id=user_id,
        )
        self._histories[tour_id] = history

        logger.info(f"Started GPS tracking for tour {tour_id}")

        return history

    async def stop_tracking(self, tour_id: str) -> LocationHistory | None:
        """Stop tracking a tour.

        Args:
            tour_id: Tour ID

        Returns:
            Final location history
        """
        history = self._histories.pop(tour_id, None)

        if history:
            logger.info(f"Stopped GPS tracking for tour {tour_id}")

        return history

    async def update_location(
        self,
        tour_id: str,
        latitude: float,
        longitude: float,
        accuracy: float | None = None,
        altitude: float | None = None,
        speed: float | None = None,
        heading: float | None = None,
        source: str = "gps",
    ) -> tuple[LocationReading | None, float]:
        """Update user location.

        Args:
            tour_id: Tour ID
            latitude: Latitude
            longitude: Longitude
            accuracy: GPS accuracy in meters
            altitude: Altitude in meters
            speed: Speed in m/s
            heading: Heading in degrees
            source: Location source

        Returns:
            Tuple of (location reading or None if filtered, distance traveled)
        """
        history = self._histories.get(tour_id)
        if not history:
            return None, 0.0

        # Create reading
        reading = LocationReading(
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
            altitude=altitude,
            speed=speed,
            heading=heading,
            timestamp=datetime.now(timezone.utc),
            source=source,
        )

        # Filter by accuracy
        if accuracy is not None and accuracy > self.min_accuracy:
            logger.debug(
                f"Filtered reading due to poor accuracy: {accuracy}m > {self.min_accuracy}m"
            )
            return None, 0.0

        # Filter by age
        if history.last_update:
            age = (reading.timestamp - history.last_update).total_seconds()
            if age > self.max_reading_age_seconds:
                logger.debug(f"Filtered reading due to age: {age}s > {self.max_reading_age_seconds}s")
                return None, 0.0

        # Apply smoothing
        smoothed_reading = await self._smooth_position(history, reading)

        # Add to history
        distance = history.add_reading(smoothed_reading)

        logger.debug(
            f"Updated location for tour {tour_id}: "
            f"({latitude:.6f}, {longitude:.6f}), accuracy={accuracy}m, distance={distance:.1f}m"
        )

        return smoothed_reading, distance

    async def get_current_location(self, tour_id: str) -> LocationReading | None:
        """Get current location for a tour.

        Args:
            tour_id: Tour ID

        Returns:
            Current location reading or None
        """
        history = self._histories.get(tour_id)
        if not history or not history.readings:
            return None

        return history.readings[-1]

    async def get_location_history(
        self,
        tour_id: str,
        limit: int = 100,
    ) -> list[LocationReading]:
        """Get location history for a tour.

        Args:
            tour_id: Tour ID
            limit: Maximum number of readings

        Returns:
            List of location readings
        """
        history = self._histories.get(tour_id)
        if not history:
            return []

        return list(history.readings)[-limit:]

    async def detect_movement_state(
        self,
        tour_id: str,
    ) -> MovementState:
        """Detect user movement state.

        Args:
            tour_id: Tour ID

        Returns:
            Movement state
        """
        history = self._histories.get(tour_id)
        if not history or len(history.readings) < 3:
            return MovementState.UNKNOWN

        recent = history.get_recent_readings(10)
        if not recent:
            return MovementState.UNKNOWN

        # Calculate average speed
        total_speed = 0.0
        count = 0
        for reading in recent:
            if reading.speed is not None:
                total_speed += reading.speed
                count += 1

        if count == 0:
            # Calculate from position changes
            avg_speed = history.get_average_speed()
        else:
            avg_speed = total_speed / count

        if avg_speed is None:
            return MovementState.UNKNOWN

        # Classify based on speed (m/s)
        if avg_speed < 0.3:
            return MovementState.STATIONARY
        elif avg_speed < 2.0:
            return MovementState.WALKING
        elif avg_speed < 5.0:
            return MovementState.RUNNING
        else:
            return MovementState.DRIVING

    async def detect_route_deviation(
        self,
        tour_id: str,
        route_pois: list[dict[str, Any]],
        threshold_meters: float = 100.0,
    ) -> bool:
        """Detect if user has deviated from planned route.

        Args:
            tour_id: Tour ID
            route_pois: List of POIs in the route
            threshold_meters: Distance threshold for deviation

        Returns:
            True if deviated from route
        """
        history = self._histories.get(tour_id)
        if not history or not history.readings:
            return False

        current = history.readings[-1]

        # Check distance to next POI
        for poi in route_pois:
            poi_lat = poi.get("latitude")
            poi_lng = poi.get("longitude")

            if poi_lat is None or poi_lng is None:
                continue

            distance = self.calculate_distance(
                current.latitude,
                current.longitude,
                poi_lat,
                poi_lng,
            )

            # If close to any POI, not deviated
            if distance < threshold_meters:
                return False

        # If far from all POIs, might be deviated
        # This is a simplified check - real implementation would use route geometry
        return False

    async def get_statistics(self, tour_id: str) -> dict[str, Any] | None:
        """Get tracking statistics for a tour.

        Args:
            tour_id: Tour ID

        Returns:
            Statistics dictionary
        """
        history = self._histories.get(tour_id)
        if not history:
            return None

        current = await self.get_current_location(tour_id)
        movement_state = await self.detect_movement_state(tour_id)

        return {
            "tour_id": tour_id,
            "total_readings": len(history.readings),
            "distance_meters": history.distance_meters,
            "duration_seconds": history.duration_seconds,
            "average_speed_mps": history.get_average_speed(),
            "current_location": current.to_dict() if current else None,
            "movement_state": movement_state.value,
            "started_at": history.started_at.isoformat() if history.started_at else None,
            "last_update": history.last_update.isoformat() if history.last_update else None,
        }

    async def _smooth_position(
        self,
        history: LocationHistory,
        reading: LocationReading,
    ) -> LocationReading:
        """Apply position smoothing using moving average.

        Args:
            history: Location history
            reading: New reading

        Returns:
            Smoothed reading
        """
        if len(history.readings) < self.smoothing_window - 1:
            return reading

        # Get recent readings for smoothing
        recent = history.get_recent_readings(self.smoothing_window - 1)
        recent.append(reading)

        # Calculate weighted average (more weight to recent)
        total_weight = 0.0
        weighted_lat = 0.0
        weighted_lng = 0.0

        for i, r in enumerate(recent):
            weight = (i + 1) / len(recent)  # Linear weight
            weighted_lat += r.latitude * weight
            weighted_lng += r.longitude * weight
            total_weight += weight

        smoothed_lat = weighted_lat / total_weight
        smoothed_lng = weighted_lng / total_weight

        # Return smoothed reading
        return LocationReading(
            latitude=smoothed_lat,
            longitude=smoothed_lng,
            accuracy=reading.accuracy,
            altitude=reading.altitude,
            speed=reading.speed,
            heading=reading.heading,
            timestamp=reading.timestamp,
            source=reading.source,
        )

    @staticmethod
    def calculate_distance(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """Calculate distance between two coordinates using Haversine formula.

        Args:
            lat1: First latitude
            lon1: First longitude
            lat2: Second latitude
            lon2: Second longitude

        Returns:
            Distance in meters
        """
        import math

        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        # Differences
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        # Haversine formula
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))

        # Earth radius in meters
        r = 6371000

        return r * c

    @staticmethod
    def calculate_bearing(
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """Calculate bearing between two coordinates.

        Args:
            lat1: First latitude
            lon1: First longitude
            lat2: Second latitude
            lon2: Second longitude

        Returns:
            Bearing in degrees (0-360)
        """
        import math

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlon_rad = math.radians(lon2 - lon1)

        x = math.sin(dlon_rad) * math.cos(lat2_rad)
        y = (
            math.cos(lat1_rad) * math.sin(lat2_rad)
            - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon_rad)
        )

        bearing = math.atan2(x, y)
        bearing = math.degrees(bearing)
        bearing = (bearing + 360) % 360

        return bearing

    async def cleanup_old_histories(self, max_age_hours: int = 24) -> int:
        """Clean up old location histories.

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of histories cleaned up
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        cleaned = 0

        for tour_id, history in list(self._histories.items()):
            if history.last_update and history.last_update < cutoff:
                del self._histories[tour_id]
                cleaned += 1
                logger.info(f"Cleaned up old location history for tour {tour_id}")

        return cleaned


# Global instance
tracker = GPSTracker()


def get_tracker() -> GPSTracker:
    """Get global GPS tracker instance.

    Returns:
        GPS tracker instance
    """
    return tracker
