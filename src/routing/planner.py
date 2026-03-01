"""Route planner for generating travel routes."""

import asyncio
import logging
from collections.abc import AsyncIterable, AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from src.routing.constraints import (
    RouteConstraint,
    RouteConstraints,
    create_constraints_from_preferences,
)
from src.routing.optimizer import RouteOptimizer, route_optimizer

logger = logging.getLogger(__name__)


class RoutePlan:
    """Represents a planned route."""

    def __init__(
        self,
        pois: list[dict[str, Any]],
        constraints: RouteConstraints,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Initialize route plan.

        Args:
            pois: Ordered list of POIs to visit
            constraints: Route constraints used
            metadata: Additional metadata
        """
        self.pois = pois
        self.constraints = constraints
        self.metadata = metadata or {}

    @property
    def total_pois(self) -> int:
        """Get total number of POIs."""
        return len(self.pois)

    @property
    def estimated_duration_minutes(self) -> float:
        """Get estimated duration in minutes."""
        return self.metadata.get("total_duration_minutes", 0.0)

    @property
    def estimated_distance_km(self) -> float:
        """Get estimated distance in km."""
        return self.metadata.get("total_distance_km", 0.0)

    @property
    def start_location(self) -> dict[str, float] | None:
        """Get start location."""
        if self.pois:
            return {
                "lat": self.pois[0].get("latitude", 0.0),
                "lng": self.pois[0].get("longitude", 0.0),
            }
        return None

    @property
    def end_location(self) -> dict[str, float] | None:
        """Get end location."""
        if self.pois:
            return {
                "lat": self.pois[-1].get("latitude", 0.0),
                "lng": self.pois[-1].get("longitude", 0.0),
            }
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "pois": self.pois,
            "constraints": self.constraints.to_dict(),
            "metadata": self.metadata,
            "total_pois": self.total_pois,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "estimated_distance_km": self.estimated_distance_km,
            "start_location": self.start_location,
            "end_location": self.end_location,
        }


class RoutePlanner:
    """Plan travel routes based on constraints."""

    def __init__(
        self,
        optimizer: RouteOptimizer | None = None,
    ) -> None:
        """Initialize route planner.

        Args:
            optimizer: Optional route optimizer
        """
        self.optimizer = optimizer or route_optimizer

    async def plan_route(
        self,
        pois: list[dict[str, Any]],
        constraints: RouteConstraints,
        preferences: list[dict[str, Any]] | None = None,
        start_location: dict[str, float] | None = None,
        end_location: dict[str, float] | None = None,
    ) -> RoutePlan:
        """Plan a route through POIs.

        Args:
            pois: Available POIs
            constraints: Route constraints
            preferences: Optional user preferences
            start_location: Optional start location
            end_location: Optional end location

        Returns:
            Planned route
        """
        # Filter POIs by constraints
        filtered_pois = await self._filter_pois(pois, constraints)

        if not filtered_pois:
            logger.warning("No POIs match the constraints")
            return RoutePlan([], constraints)

        # Score POIs if preferences provided
        if preferences:
            filtered_pois = await self._score_pois(
                filtered_pois,
                preferences,
                constraints,
            )

        # Select POIs based on constraints
        selected_pois = await self._select_pois(
            filtered_pois,
            constraints,
        )

        if not selected_pois:
            logger.warning("No POIs selected after filtering")
            return RoutePlan([], constraints)

        # Optimize route order
        optimized_pois = await self._optimize_route(
            selected_pois,
            constraints,
            start_location,
            end_location,
        )

        # Calculate metadata
        metadata = await self._calculate_route_metadata(
            optimized_pois,
            constraints,
        )

        return RoutePlan(optimized_pois, constraints, metadata)

    async def _filter_pois(
        self,
        pois: list[dict[str, Any]],
        constraints: RouteConstraints,
    ) -> list[dict[str, Any]]:
        """Filter POIs by constraints.

        Args:
            pois: Available POIs
            constraints: Route constraints

        Returns:
            Filtered POIs
        """
        filtered = []

        for poi in pois:
            # Check excluded POIs
            if poi.get("id") in constraints.must_exclude:
                continue

            # Check excluded categories
            if poi.get("category") in constraints.excluded_categories:
                continue

            # Check distance constraints
            distance = poi.get("distance_km")
            if distance:
                if constraints.max_distance_km and distance > constraints.max_distance_km:
                    continue
                if constraints.min_distance_km and distance < constraints.min_distance_km:
                    continue

            # Check budget
            max_budget = constraints.max_budget
            if max_budget:
                poi_price = poi.get("price_level", 0)
                # Rough cost estimate
                estimated_cost = poi_price * 10  # $10 per price level
                if estimated_cost > max_budget:
                    continue

            # Check accessibility
            if constraints.wheelchair_accessible:
                if not poi.get("wheelchair_accessible", False):
                    continue

            if constraints.family_friendly:
                if not poi.get("family_friendly", True):
                    continue

            filtered.append(poi)

        logger.info(f"Filtered {len(filtered)} POIs from {len(pois)}")

        return filtered

    async def _score_pois(
        self,
        pois: list[dict[str, Any]],
        preferences: list[dict[str, Any]],
        constraints: RouteConstraints,
    ) -> list[dict[str, Any]]:
        """Score POIs based on preferences.

        Args:
            pois: Available POIs
            preferences: User preferences
            constraints: Route constraints

        Returns:
            Scored POIs
        """
        scored_pois = []

        for poi in pois:
            score = 0.0

            # Category matching
            if poi.get("category") in constraints.required_categories:
                score += 0.4

            # Must include
            if poi.get("id") in constraints.must_include:
                score += 0.5

            # Rating preference
            if constraints.prioritize_rating:
                rating = poi.get("rating", 0)
                score += (rating / 5.0) * 0.3

            # Distance preference
            if constraints.prioritize_distance:
                distance = poi.get("distance_km", 0)
                if distance > 0:
                    score += min(1.0 / distance, 0.3)

            # Preference matching
            for pref in preferences:
                if pref.get("preference_type") == "like":
                    pref_category = pref.get("category")
                    pref_value = pref.get("value", "")

                    if pref_category == "category":
                        if pref_value.lower() in poi.get("category", "").lower():
                            score += 0.2

            poi["score"] = min(score, 1.0)
            scored_pois.append(poi)

        # Sort by score
        scored_pois.sort(key=lambda p: p.get("score", 0.0), reverse=True)

        return scored_pois

    async def _select_pois(
        self,
        pois: list[dict[str, Any]],
        constraints: RouteConstraints,
    ) -> list[dict[str, Any]]:
        """Select POIs for the route.

        Args:
            pois: Available POIs
            constraints: Route constraints

        Returns:
            Selected POIs
        """
        selected = []

        # Must include POIs
        for poi in pois:
            if poi.get("id") in constraints.must_include:
                selected.append(poi)

        # Add required categories
        for category in constraints.required_categories:
            for poi in pois:
                if (
                    poi.get("category") == category and
                    poi not in selected and
                    len(selected) < constraints.max_pois
                ):
                    selected.append(poi)
                    break

        # Fill remaining slots with best scored POIs
        for poi in pois:
            if len(selected) >= constraints.max_pois:
                break
            if poi not in selected:
                selected.append(poi)

        # Ensure minimum POIs
        if len(selected) < constraints.min_pois:
            logger.warning(
                f"Only {len(selected)} POIs selected, below minimum {constraints.min_pois}"
            )

        logger.info(f"Selected {len(selected)} POIs for route")

        return selected

    async def _optimize_route(
        self,
        pois: list[dict[str, Any]],
        constraints: RouteConstraints,
        start_location: dict[str, float] | None = None,
        end_location: dict[str, float] | None = None,
    ) -> list[dict[str, Any]]:
        """Optimize route order.

        Args:
            pois: POIs to visit
            constraints: Route constraints
            start_location: Optional start location
            end_location: Optional end location

        Returns:
            Optimized POI order
        """
        if len(pois) <= 2:
            return pois

        # Convert to optimizer format
        locations = []
        for poi in pois:
            locations.append({
                "id": poi.get("id"),
                "lat": poi.get("latitude", 0.0),
                "lng": poi.get("longitude", 0.0),
            })

        # Optimize using TSP solver
        optimized_indices = await self.optimizer.optimize_route(
            locations,
            constraints.transport_mode,
            start=start_location,
            end=end_location,
        )

        # Reorder POIs
        optimized_pois = [pois[i] for i in optimized_indices]

        return optimized_pois

    async def _calculate_route_metadata(
        self,
        pois: list[dict[str, Any]],
        constraints: RouteConstraints,
    ) -> dict[str, Any]:
        """Calculate route metadata.

        Args:
            pois: Route POIs
            constraints: Route constraints

        Returns:
            Route metadata
        """
        total_distance = 0.0
        total_duration = 0.0

        # Calculate distance and duration between consecutive POIs
        for i in range(len(pois) - 1):
            from_poi = pois[i]
            to_poi = pois[i + 1]

            distance = self._calculate_distance(
                from_poi.get("latitude", 0.0),
                from_poi.get("longitude", 0.0),
                to_poi.get("latitude", 0.0),
                to_poi.get("longitude", 0.0),
            )

            total_distance += distance

            # Calculate travel time based on transport mode
            speeds = {
                "walking": constraints.walking_speed_kmh,
                "driving": 30.0,
                "transit": 20.0,
            }

            speed = speeds.get(constraints.transport_mode, constraints.walking_speed_kmh)
            travel_time = (distance / speed) * 60  # minutes
            total_duration += travel_time

        # Add visit durations
        for poi in pois:
            # Estimate visit duration
            category = poi.get("category", "attraction")
            base_duration = 60  # minutes

            category_durations = {
                "restaurant": 60,
                "cafe": 30,
                "museum": 90,
                "attraction": 60,
                "park": 45,
                "shopping": 90,
            }

            duration = category_durations.get(category, base_duration)
            total_duration += duration

        return {
            "total_distance_km": round(total_distance, 2),
            "total_duration_minutes": round(total_duration, 2),
            "total_duration_hours": round(total_duration / 60, 2),
            "transport_mode": constraints.transport_mode,
            "planned_at": datetime.now(timezone.utc).isoformat(),
        }

    def _calculate_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """Calculate distance between two points (Haversine formula).

        Args:
            lat1: Latitude of first point
            lon1: Longitude of first point
            lat2: Latitude of second point
            lon2: Longitude of second point

        Returns:
            Distance in kilometers
        """
        import math

        R = 6371  # Earth radius in km

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = (
            math.sin(dlat / 2) ** 2 +
            math.cos(math.radians(lat1)) *
            math.cos(math.radians(lat2)) *
            math.sin(dlon / 2) ** 2
        )

        c = 2 * math.asin(math.sqrt(a))

        return R * c

    async def plan_multi_day_route(
        self,
        pois: list[dict[str, Any]],
        constraints: RouteConstraints,
        days: int = 2,
        preferences: list[dict[str, Any]] | None = None,
    ) -> list[RoutePlan]:
        """Plan a multi-day route.

        Args:
            pois: Available POIs
            constraints: Route constraints
            days: Number of days
            preferences: Optional user preferences

        Returns:
            List of daily route plans
        """
        # Split POIs across days
        pois_per_day = max(constraints.max_pois, len(pois) // days)

        daily_plans = []

        for day in range(days):
            start_idx = day * pois_per_day
            end_idx = start_idx + pois_per_day
            day_pois = pois[start_idx:end_idx]

            if not day_pois:
                break

            # Create day-specific constraints
            day_constraints = RouteConstraints(
                max_duration_hours=constraints.max_duration_hours,
                transport_mode=constraints.transport_mode,
                max_pois=pois_per_day,
                min_pois=constraints.min_pois,
                prioritize_rating=constraints.prioritize_rating,
                prioritize_distance=constraints.prioritize_distance,
                prioritize_preferences=constraints.prioritize_preferences,
            )

            plan = await self.plan_route(
                day_pois,
                day_constraints,
                preferences,
            )

            plan.metadata["day"] = day + 1
            plan.metadata["total_days"] = days

            daily_plans.append(plan)

        logger.info(f"Planned {len(daily_plans)} day route")

        return daily_plans

    async def suggest_alternative_routes(
        self,
        pois: list[dict[str, Any]],
        constraints: RouteConstraints,
        count: int = 3,
        preferences: list[dict[str, Any]] | None = None,
    ) -> list[RoutePlan]:
        """Suggest alternative route options.

        Args:
            pois: Available POIs
            constraints: Route constraints
            count: Number of alternatives
            preferences: Optional user preferences

        Returns:
            List of alternative route plans
        """
        alternatives = []

        for i in range(count):
            # Vary constraints for each alternative
            alt_constraints = RouteConstraints(
                max_duration_hours=constraints.max_duration_hours,
                max_pois=max(
                    constraints.min_pois,
                    constraints.max_pois - (i * 2)
                ),
                transport_mode=constraints.transport_mode,
                prioritize_rating=i % 2 == 0,
                prioritize_distance=i % 2 == 1,
            )

            plan = await self.plan_route(
                pois,
                alt_constraints,
                preferences,
            )

            plan.metadata["alternative"] = i + 1
            plan.metadata["variant"] = (
                "rating_focused" if i % 2 == 0 else "distance_focused"
            )

            alternatives.append(plan)

        return alternatives


class AdaptiveRoutePlanner(RoutePlanner):
    """Route planner that adapts based on real-time conditions."""

    async def plan_route_with_feedback(
        self,
        pois: list[dict[str, Any]],
        constraints: RouteConstraints,
        feedback: list[dict[str, Any]],
        preferences: list[dict[str, Any]] | None = None,
    ) -> RoutePlan:
        """Plan route incorporating user feedback.

        Args:
            pois: Available POIs
            constraints: Route constraints
            feedback: User feedback from previous routes
            preferences: Optional user preferences

        Returns:
            Adaptive route plan
        """
        # Adjust constraints based on feedback
        adjusted_constraints = self._adjust_constraints_from_feedback(
            constraints,
            feedback,
        )

        # Filter out disliked POIs
        disliked_ids = [
            f.get("poi_id")
            for f in feedback
            if f.get("sentiment") == "negative"
        ]

        adjusted_constraints.must_exclude.extend(disliked_ids)

        # Plan with adjusted constraints
        plan = await self.plan_route(
            pois,
            adjusted_constraints,
            preferences,
        )

        plan.metadata["adaptive"] = True
        plan.metadata["feedback_used"] = len(feedback)

        return plan

    def _adjust_constraints_from_feedback(
        self,
        constraints: RouteConstraints,
        feedback: list[dict[str, Any]],
    ) -> RouteConstraints:
        """Adjust constraints based on feedback.

        Args:
            constraints: Original constraints
            feedback: User feedback

        Returns:
            Adjusted constraints
        """
        adjusted = RouteConstraints(**constraints.model_dump())

        # Adjust duration based on feedback
        duration_feedback = [
            f for f in feedback
            if f.get("type") == "duration"
        ]

        if duration_feedback:
            avg_sentiment = sum(
                1 if f.get("sentiment") == "positive" else -1
                for f in duration_feedback
            ) / len(duration_feedback)

            if avg_sentiment < 0:
                # Reduce duration if negative feedback
                adjusted.max_duration_hours = max(
                    constraints.max_duration_hours * 0.8,
                    2.0,
                )

        # Adjust POI count based on feedback
        count_feedback = [
            f for f in feedback
            if f.get("type") == "poi_count"
        ]

        if count_feedback:
            avg_sentiment = sum(
                1 if f.get("sentiment") == "positive" else -1
                for f in count_feedback
            ) / len(count_feedback)

            if avg_sentiment < 0:
                # Reduce POI count if negative feedback
                adjusted.max_pois = max(
                    constraints.max_pois - 2,
                    adjusted.min_pois,
                )
            elif avg_sentiment > 0:
                # Increase POI count if positive feedback
                adjusted.max_pois = min(
                    constraints.max_pois + 2,
                    100,
                )

        return adjusted


# Global instance
route_planner = RoutePlanner()
adaptive_route_planner = AdaptiveRoutePlanner()


def get_route_planner() -> RoutePlanner:
    """Get route planner instance.

    Returns:
        Route planner instance
    """
    return route_planner


def get_adaptive_route_planner() -> AdaptiveRoutePlanner:
    """Get adaptive route planner instance.

    Returns:
        Adaptive route planner instance
    """
    return adaptive_route_planner
