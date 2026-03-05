"""Unit tests for routing modules."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.routing.constraints import (
    RouteConstraints,
    RouteConstraint,
    ConstraintBuilder,
)
from src.routing.planner import RoutePlanner, RoutePlan
from src.routing.optimizer import RouteOptimizer, TimeWindowOptimizer


@pytest.fixture
def sample_pois():
    """Create sample POIs for testing."""
    return [
        {
            "id": "poi_1",
            "name": "Central Park",
            "category": "park",
            "latitude": 40.7829,
            "longitude": -73.9654,
            "rating": 4.8,
        },
        {
            "id": "poi_2",
            "name": "Times Square",
            "category": "attraction",
            "latitude": 40.7580,
            "longitude": -73.9855,
            "rating": 4.5,
        },
        {
            "id": "poi_3",
            "name": "Empire State Building",
            "category": "attraction",
            "latitude": 40.7484,
            "longitude": -73.9857,
            "rating": 4.7,
        },
    ]


@pytest.fixture
def sample_constraints():
    """Create sample route constraints."""
    return RouteConstraints(
        max_duration_hours=8.0,
        max_pois=5,
        transport_mode="walking",
        prioritize_rating=True,
    )


class TestRouteConstraints:
    """Test route constraints."""

    def test_route_constraints_validation(self):
        """Test RouteConstraints validation."""
        constraints = RouteConstraints(
            max_duration_hours=8.0,
            max_pois=10,
            transport_mode="walking",
        )

        assert constraints.max_duration_hours == 8.0
        assert constraints.max_pois == 10

    def test_constraint_builder(self):
        """Test ConstraintBuilder."""
        builder = ConstraintBuilder()

        constraints = (
            builder
            .with_time_limit(6.0)
            .with_distance_limit(50.0)
            .with_poi_limit(8)
            .with_required_categories(["park", "museum"])
            .build()
        )

        assert constraints.max_duration_hours == 6.0
        assert constraints.max_distance_km == 50.0
        assert constraints.max_pois == 8
        assert "park" in constraints.required_categories


class TestRouteOptimizer:
    """Test route optimizer."""

    @pytest.mark.asyncio
    async def test_optimize_route(self, sample_pois):
        """Test route optimization."""
        optimizer = RouteOptimizer()

        locations = [
            {
                "id": poi["id"],
                "lat": poi["latitude"],
                "lng": poi["longitude"],
            }
            for poi in sample_pois
        ]

        order = await optimizer.optimize_route(
            locations=locations,
            transport_mode="walking",
        )

        assert len(order) == 3
        assert all(isinstance(i, int) for i in order)

    @pytest.mark.asyncio
    async def test_nearest_neighbor(self):
        """Test nearest neighbor heuristic."""
        optimizer = RouteOptimizer()

        locations = [
            {"id": "0", "lat": 40.7128, "lng": -74.0060},
            {"id": "1", "lat": 40.7580, "lng": -73.9855},
            {"id": "2", "lat": 40.7829, "lng": -73.9654},
        ]

        import numpy as np
        distance_matrix = np.zeros((3, 3))

        for i in range(3):
            for j in range(3):
                if i != j:
                    distance_matrix[i][j] = optimizer._haversine_distance(
                        locations[i]["lat"],
                        locations[i]["lng"],
                        locations[j]["lat"],
                        locations[j]["lng"],
                    )

        order = optimizer._nearest_neighbor(distance_matrix)

        assert len(order) == 3
        assert order[0] == 0  # Should start from first location


class TestTimeWindowOptimizer:
    """Test time window optimizer."""

    @pytest.mark.asyncio
    async def test_optimize_with_time_windows(self, sample_pois):
        """Test optimization with time windows."""
        optimizer = TimeWindowOptimizer()

        locations = [
            {
                "id": poi["id"],
                "lat": poi["latitude"],
                "lng": poi["longitude"],
            }
            for poi in sample_pois
        ]

        time_windows = {
            "poi_1": (
                datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 17, 0, tzinfo=timezone.utc),
            ),
            "poi_2": (
                datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 1, 18, 0, tzinfo=timezone.utc),
            ),
        }

        service_times = {
            "poi_1": 60,
            "poi_2": 90,
        }

        order, schedule = await optimizer.optimize_with_time_windows(
            locations=locations,
            time_windows=time_windows,
            service_times=service_times,
            transport_mode="walking",
        )

        assert isinstance(order, list)
        assert "stops" in schedule


class TestRoutePlanner:
    """Test route planner."""

    @pytest.mark.asyncio
    async def test_plan_route(self, sample_pois, sample_constraints):
        """Test planning a route."""
        planner = RoutePlanner()

        with patch.object(planner.optimizer, 'optimize_route', return_value=[0, 1, 2]):
            plan = await planner.plan_route(
                pois=sample_pois,
                constraints=sample_constraints,
            )

            assert isinstance(plan, RoutePlan)
            assert plan.total_pois == 3
            assert plan.estimated_distance_km >= 0

    @pytest.mark.asyncio
    async def test_plan_multi_day_route(self, sample_pois, sample_constraints):
        """Test multi-day route planning."""
        planner = RoutePlanner()

        # Create enough POIs for 2 days
        all_pois = sample_pois + [
            {
                **sample_pois[0],
                "id": "poi_4",
                "name": "Brooklyn Bridge",
                "category": "attraction",
                "latitude": 40.7061,
                "longitude": -73.9969,
            },
            {
                **sample_pois[1],
                "id": "poi_5",
                "name": "Statue of Liberty",
                "category": "attraction",
                "latitude": 40.6892,
                "longitude": -74.0445,
            },
        ]

        with patch.object(planner.optimizer, 'optimize_route', return_value=[0, 1]):
            plans = await planner.plan_multi_day_route(
                pois=all_pois,
                constraints=sample_constraints,
                days=2,
            )

            assert len(plans) >= 1  # At least 1 day should have POIs

    @pytest.mark.asyncio
    async def test_suggest_alternative_routes(self, sample_pois, sample_constraints):
        """Test suggesting alternative routes."""
        planner = RoutePlanner()

        with patch.object(planner.optimizer, 'optimize_route', return_value=[0, 1]):
            alternatives = await planner.suggest_alternative_routes(
                pois=sample_pois,
                constraints=sample_constraints,
                count=3,
            )

            assert len(alternatives) == 3


class TestRoutePlan:
    """Test RoutePlan."""

    def test_route_plan_properties(self, sample_pois, sample_constraints):
        """Test RoutePlan properties."""
        plan = RoutePlan(
            pois=sample_pois,
            constraints=sample_constraints,
            metadata={
                "total_distance_km": 5.5,
                "total_duration_minutes": 180,
            },
        )

        assert plan.total_pois == 3
        assert plan.estimated_distance_km == 5.5
        assert plan.estimated_duration_minutes == 180

    def test_to_dict(self, sample_pois, sample_constraints):
        """Test RoutePlan to_dict method."""
        plan = RoutePlan(
            pois=sample_pois,
            constraints=sample_constraints,
        )

        plan_dict = plan.to_dict()

        assert "pois" in plan_dict
        assert "total_pois" in plan_dict
        assert "estimated_distance_km" in plan_dict
