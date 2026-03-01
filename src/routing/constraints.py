"""Route constraints for travel route planning."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, time
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RouteConstraints(BaseModel):
    """Constraints for route planning."""

    # Time constraints
    max_duration_hours: float | None = Field(None, ge=0.5, le=24)
    start_time: str | None = Field(None, description="ISO format time")
    end_time: str | None = Field(None, description="ISO format time")
    start_date: str | None = Field(None, description="ISO format date")

    # Distance constraints
    max_distance_km: float | None = Field(None, ge=1, le=500)
    min_distance_km: float | None = Field(None, ge=0)

    # POI constraints
    max_pois: int = Field(default=20, ge=1, le=100)
    min_pois: int = Field(default=1, ge=0, le=10)
    must_include: list[str] = Field(default_factory=list)
    must_exclude: list[str] = Field(default_factory=list)

    # Category constraints
    required_categories: list[str] = Field(default_factory=list)
    excluded_categories: list[str] = Field(default_factory=list)

    # Transport constraints
    transport_mode: str = Field(default="walking")
    max_walking_distance_km: float | None = Field(None, ge=0.5, le=10)
    walking_speed_kmh: float = Field(default=5.0, ge=2.0, le=8.0)

    # Visit constraints
    min_visit_duration_minutes: int = Field(default=15, ge=5)
    max_visit_duration_minutes: int = Field(default=120, ge=15)

    # Priority constraints
    prioritize_rating: bool = Field(default=True)
    prioritize_distance: bool = Field(default=False)
    prioritize_preferences: bool = Field(default=True)

    # Budget constraints
    max_budget: float | None = Field(None, ge=0)
    currency: str = Field(default="USD")

    # Accessibility
    wheelchair_accessible: bool = Field(default=False)
    family_friendly: bool = Field(default=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return self.model_dump()


@dataclass
class RouteConstraint:
    """Route constraint for optimization."""

    # Time windows
    time_windows: dict[str, tuple[datetime, datetime]] = field(default_factory=dict)

    # POI requirements
    required_pois: list[str] = field(default_factory=list)
    excluded_pois: list[str] = field(default_factory=list)

    # Category requirements
    required_categories: set[str] = field(default_factory=set)
    excluded_categories: set[str] = field(default_factory=set)

    # Spatial constraints
    start_location: tuple[float, float] | None = None
    end_location: tuple[float, float] | None = None
    max_detour_km: float = 5.0

    # Capacity constraints
    max_pois: int = 20
    max_duration_hours: float = 8.0
    max_distance_km: float = 50.0

    # User preferences
    preferences: dict[str, Any] = field(default_factory=dict)

    def add_time_window(
        self,
        poi_id: str,
        start: datetime,
        end: datetime,
    ) -> None:
        """Add time window constraint for a POI.

        Args:
            poi_id: POI ID
            start: Start time
            end: End time
        """
        self.time_windows[poi_id] = (start, end)

    def add_required_poi(self, poi_id: str) -> None:
        """Add required POI.

        Args:
            poi_id: POI ID
        """
        if poi_id not in self.required_pois:
            self.required_pois.append(poi_id)

    def add_excluded_poi(self, poi_id: str) -> None:
        """Add excluded POI.

        Args:
            poi_id: POI ID
        """
        if poi_id not in self.excluded_pois:
            self.excluded_pois.append(poi_id)

    def requires_category(self, category: str) -> bool:
        """Check if category is required.

        Args:
            category: Category name

        Returns:
            True if required
        """
        return category in self.required_categories

    def excludes_category(self, category: str) -> bool:
        """Check if category is excluded.

        Args:
            category: Category name

        Returns:
            True if excluded
        """
        return category in self.excluded_categories

    def is_poi_allowed(self, poi_id: str) -> bool:
        """Check if POI is allowed by constraints.

        Args:
            poi_id: POI ID

        Returns:
            True if allowed
        """
        if poi_id in self.excluded_pois:
            return False

        return True

    def get_time_window(
        self,
        poi_id: str,
    ) -> tuple[datetime, datetime] | None:
        """Get time window for a POI.

        Args:
            poi_id: POI ID

        Returns:
            Time window or None
        """
        return self.time_windows.get(poi_id)

    def estimate_visit_duration(
        self,
        poi: dict[str, Any],
    ) -> int:
        """Estimate visit duration for a POI.

        Args:
            poi: POI data

        Returns:
            Duration in minutes
        """
        # Base duration by category
        category_durations = {
            "restaurant": 60,
            "cafe": 30,
            "museum": 90,
            "attraction": 60,
            "park": 45,
            "shopping": 90,
            "nightlife": 120,
            "nature": 60,
        }

        base_duration = category_durations.get(
            poi.get("category", "other"),
            45,
        )

        # Adjust based on rating (higher rated = longer visit)
        rating = poi.get("rating")
        if rating:
            base_duration = int(base_duration * (0.8 + rating * 0.04))

        return max(base_duration, self.min_visit_duration_minutes)

    def calculate_travel_time(
        self,
        from_loc: tuple[float, float],
        to_loc: tuple[float, float],
        mode: str = "walking",
    ) -> float:
        """Calculate travel time between locations.

        Args:
            from_loc: From location (lat, lng)
            to_loc: To location (lat, lng)
            mode: Transport mode

        Returns:
            Travel time in minutes
        """
        import math

        # Calculate distance
        R = 6371  # Earth radius in km
        lat1, lon1 = math.radians(from_loc[0]), math.radians(from_loc[1])
        lat2, lon2 = math.radians(to_loc[0]), math.radians(to_loc[1])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        distance_km = R * 2 * math.asin(math.sqrt(a))

        # Calculate time based on mode
        speeds = {
            "walking": self.walking_speed_kmh,
            "driving": 30.0,
            "transit": 20.0,
        }

        speed = speeds.get(mode, self.walking_speed_kmh)

        return (distance_km / speed) * 60  # Convert to minutes

    def validate(self) -> list[str]:
        """Validate constraints.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if self.max_duration_hours and self.max_duration_hours < 0.5:
            errors.append("max_duration_hours must be at least 0.5")

        if self.max_pois < 1:
            errors.append("max_pois must be at least 1")

        return errors


class ConstraintBuilder:
    """Builder for creating route constraints."""

    def __init__(self) -> None:
        """Initialize builder."""
        self._constraints = RouteConstraint()

    def with_time_limit(
        self,
        max_hours: float,
    ) -> "ConstraintBuilder":
        """Set time limit.

        Args:
            max_hours: Maximum hours

        Returns:
            Self for chaining
        """
        self._constraints.max_duration_hours = max_hours
        return self

    def with_distance_limit(
        self,
        max_km: float,
    ) -> "ConstraintBuilder":
        """Set distance limit.

        Args:
            max_km: Maximum distance in km

        Returns:
            Self for chaining
        """
        self._constraints.max_distance_km = max_km
        return self

    def with_poi_limit(
        self,
        max_pois: int,
    ) -> "ConstraintBuilder":
        """Set POI limit.

        Args:
            max_pois: Maximum POIs

        Returns:
            Self for chaining
        """
        self._constraints.max_pois = max_pois
        return self

    def with_required_categories(
        self,
        categories: list[str],
    ) -> "ConstraintBuilder":
        """Set required categories.

        Args:
            categories: Required categories

        Returns:
            Self for chaining
        """
        self._constraints.required_categories.update(categories)
        return self

    def with_excluded_categories(
        self,
        categories: list[str],
    ) -> "ConstraintBuilder":
        """Set excluded categories.

        Args:
            categories: Excluded categories

        Returns:
            Self for chaining
        """
        self._constraints.excluded_categories.update(categories)
        return self

    def with_transport_mode(
        self,
        mode: str,
    ) -> "ConstraintBuilder":
        """Set transport mode.

        Args:
            mode: Transport mode

        Returns:
            Self for chaining
        """
        self._constraints.transport_mode = mode
        return self

    def with_start_end(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
    ) -> "ConstraintBuilder":
        """Set start and end locations.

        Args:
            start: Start location (lat, lng)
            end: End location (lat, lng)

        Returns:
            Self for chaining
        """
        self._constraints.start_location = start
        self._constraints.end_location = end
        return self

    def with_preferences(
        self,
        preferences: dict[str, Any],
    ) -> "ConstraintBuilder":
        """Set user preferences.

        Args:
            preferences: User preferences

        Returns:
            Self for chaining
        """
        self._constraints.preferences = preferences
        return self

    def build(self) -> RouteConstraint:
        """Build the constraints.

        Returns:
            Route constraints
        """
        errors = self._constraints.validate()

        if errors:
            raise ValidationError(
                message="Invalid constraints",
                details={"errors": errors},
            )

        return self._constraints


def create_default_constraints() -> RouteConstraint:
    """Create default route constraints.

    Returns:
        Default constraints
    """
    return RouteConstraint()


def create_constraints_from_preferences(
    user_preferences: list[dict[str, Any]],
) -> RouteConstraint:
    """Create constraints from user preferences.

    Args:
        user_preferences: User preference list

    Returns:
        Route constraints
    """
    constraints = RouteConstraint()

    for pref in user_preferences:
        category = pref.get("category")
        value = pref.get("value")
        pref_type = pref.get("preference_type")

        if pref_type == "like":
            if category == "category":
                constraints.required_categories.add(value)
        elif pref_type == "dislike":
            if category == "category":
                constraints.excluded_categories.add(value)

    return constraints
