"""Route service for managing travel routes."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError, ValidationError
from src.poi.discovery import POIDiscovery, poi_discovery
from src.routing.constraints import (
    RouteConstraints,
    RouteConstraint,
    create_constraints_from_preferences,
)
from src.routing.optimizer import TimeWindowOptimizer, time_window_optimizer
from src.routing.planner import (
    RoutePlanner,
    AdaptiveRoutePlanner,
    route_planner,
    adaptive_route_planner,
)
from src.routing.ranker import (
    RouteRanker,
    PersonalizedRanker,
    route_ranker,
    personalized_ranker,
)

logger = logging.getLogger(__name__)


class RouteService:
    """Service for managing travel routes."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        """Initialize route service.

        Args:
            session: Database session
        """
        self.session = session
        self.planner = route_planner
        self.adaptive_planner = adaptive_route_planner
        self.optimizer = time_window_optimizer
        self.ranker = route_ranker
        self.personalized_ranker = personalized_ranker
        self.poi_discovery = poi_discovery

        # In-memory route storage
        self._routes: dict[str, dict[str, Any]] = {}

    async def generate_route(
        self,
        user_id: str,
        location: dict[str, float],
        constraints: RouteConstraints,
        preferences: list[dict[str, Any]] | None = None,
        start_location: dict[str, float] | None = None,
        end_location: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Generate a travel route.

        Args:
            user_id: User ID
            location: Center location
            constraints: Route constraints
            preferences: Optional user preferences
            start_location: Optional start location
            end_location: Optional end location

        Returns:
            Generated route data
        """
        # Discover POIs
        categories = constraints.required_categories or [
            "attractions",
            "restaurants",
            "museums",
        ]

        poi_results = await self.poi_discovery.discover_by_category(
            location=location,
            categories=categories,
            radius=5000,
            limit_per_category=constraints.max_pois // len(categories) + 5,
        )

        # Flatten POI list
        all_pois = []
        for category_pois in poi_results.values():
            all_pois.extend(category_pois)

        if not all_pois:
            raise ValidationError(
                message="No POIs found in the specified area",
                details={"location": location},
            )

        # Plan route
        route_plan = await self.planner.plan_route(
            pois=all_pois,
            constraints=constraints,
            preferences=preferences,
            start_location=start_location,
            end_location=end_location,
        )

        # Store route
        route_id = str(uuid.uuid4())
        route_data = {
            "id": route_id,
            "user_id": user_id,
            "plan": route_plan.to_dict(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
        }

        self._routes[route_id] = route_data

        logger.info(f"Generated route {route_id} with {route_plan.total_pois} POIs")

        return route_data

    async def generate_alternative_routes(
        self,
        user_id: str,
        location: dict[str, float],
        constraints: RouteConstraints,
        count: int = 3,
        preferences: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Generate alternative route options.

        Args:
            user_id: User ID
            location: Center location
            constraints: Route constraints
            count: Number of alternatives
            preferences: Optional user preferences

        Returns:
            List of alternative routes
        """
        # Discover POIs once
        categories = constraints.required_categories or [
            "attractions",
            "restaurants",
            "museums",
        ]

        poi_results = await self.poi_discovery.discover_by_category(
            location=location,
            categories=categories,
            radius=5000,
            limit_per_category=constraints.max_pois,
        )

        all_pois = []
        for category_pois in poi_results.values():
            all_pois.extend(category_pois)

        # Generate alternatives
        alternatives = await self.planner.suggest_alternative_routes(
            pois=all_pois,
            constraints=constraints,
            count=count,
            preferences=preferences,
        )

        # Rank alternatives
        ranked = await self.ranker.rank_routes(alternatives, preferences)

        # Store routes
        route_list = []

        for item in ranked:
            route_id = str(uuid.uuid4())
            route_data = {
                "id": route_id,
                "user_id": user_id,
                "plan": item["route"].to_dict(),
                "score": item["total_score"],
                "scores": item["scores"],
                "rank": item["rank"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "alternative",
            }

            self._routes[route_id] = route_data
            route_list.append(route_data)

        logger.info(f"Generated {len(route_list)} alternative routes")

        return route_list

    async def generate_multi_day_route(
        self,
        user_id: str,
        location: dict[str, float],
        constraints: RouteConstraints,
        days: int = 2,
        preferences: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Generate a multi-day route.

        Args:
            user_id: User ID
            location: Center location
            constraints: Route constraints
            days: Number of days
            preferences: Optional user preferences

        Returns:
            Multi-day route data
        """
        # Discover POIs
        categories = constraints.required_categories or [
            "attractions",
            "restaurants",
            "museums",
            "parks",
        ]

        poi_results = await self.poi_discovery.discover_by_category(
            location=location,
            categories=categories,
            radius=10000,
            limit_per_category=constraints.max_pois * days // len(categories) + 10,
        )

        all_pois = []
        for category_pois in poi_results.values():
            all_pois.extend(category_pois)

        # Plan multi-day route
        daily_plans = await self.planner.plan_multi_day_route(
            pois=all_pois,
            constraints=constraints,
            days=days,
            preferences=preferences,
        )

        # Store route
        route_id = str(uuid.uuid4())
        route_data = {
            "id": route_id,
            "user_id": user_id,
            "type": "multi_day",
            "days": [
                {
                    "day": i + 1,
                    "plan": plan.to_dict(),
                }
                for i, plan in enumerate(daily_plans)
            ],
            "total_days": days,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
        }

        self._routes[route_id] = route_data

        logger.info(f"Generated multi-day route {route_id} for {days} days")

        return route_data

    async def generate_route_with_time_windows(
        self,
        user_id: str,
        location: dict[str, float],
        constraints: RouteConstraints,
        time_windows: dict[str, tuple[datetime, datetime]],
        service_times: dict[str, int],
        start_time: datetime | None = None,
        preferences: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Generate route with time window constraints.

        Args:
            user_id: User ID
            location: Center location
            constraints: Route constraints
            time_windows: Time windows for POIs
            service_times: Service times for POIs
            start_time: Optional start time
            preferences: Optional user preferences

        Returns:
            Route with schedule
        """
        if not start_time:
            start_time = datetime.now(timezone.utc)

        # Discover POIs
        categories = constraints.required_categories or ["attractions", "restaurants"]

        poi_results = await self.poi_discovery.discover_by_category(
            location=location,
            categories=categories,
            radius=5000,
            limit_per_category=constraints.max_pois,
        )

        all_pois = []
        for category_pois in poi_results.values():
            all_pois.extend(category_pois)

        # Build locations list
        locations = [
            {
                "id": poi.get("id", str(i)),
                "lat": poi.get("latitude", 0.0),
                "lng": poi.get("longitude", 0.0),
            }
            for i, poi in enumerate(all_pois)
        ]

        # Optimize with time windows
        order, schedule = await self.optimizer.optimize_with_time_windows(
            locations=locations,
            time_windows=time_windows,
            service_times=service_times,
            transport_mode=constraints.transport_mode,
            start=location,
            start_time=start_time,
        )

        # Reorder POIs
        ordered_pois = [all_pois[i] for i in order if i < len(all_pois)]

        # Create route plan
        from src.routing.planner import RoutePlan
        route_plan = RoutePlan(ordered_pois, constraints, schedule)

        # Store route
        route_id = str(uuid.uuid4())
        route_data = {
            "id": route_id,
            "user_id": user_id,
            "plan": route_plan.to_dict(),
            "schedule": schedule,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "scheduled",
        }

        self._routes[route_id] = route_data

        logger.info(f"Generated scheduled route {route_id}")

        return route_data

    async def get_route(self, route_id: str) -> dict[str, Any]:
        """Get a route by ID.

        Args:
            route_id: Route ID

        Returns:
            Route data

        Raises:
            NotFoundError: If route not found
        """
        route = self._routes.get(route_id)

        if not route:
            raise NotFoundError("Route", route_id)

        return route

    async def update_route(
        self,
        route_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Update a route.

        Args:
            route_id: Route ID
            updates: Updates to apply

        Returns:
            Updated route data

        Raises:
            NotFoundError: If route not found
        """
        route = self._routes.get(route_id)

        if not route:
            raise NotFoundError("Route", route_id)

        # Apply updates
        for key, value in updates.items():
            if key in route:
                route[key] = value

        route["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(f"Updated route {route_id}")

        return route

    async def delete_route(self, route_id: str) -> bool:
        """Delete a route.

        Args:
            route_id: Route ID

        Returns:
            True if deleted
        """
        if route_id in self._routes:
            del self._routes[route_id]
            logger.info(f"Deleted route {route_id}")
            return True

        return False

    async def rank_routes(
        self,
        route_ids: list[str],
        user_id: str,
        preferences: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Rank existing routes.

        Args:
            route_ids: Route IDs to rank
            user_id: User ID
            preferences: Optional preferences

        Returns:
            Ranked routes
        """
        # Get routes
        routes = []
        for route_id in route_ids:
            if route_id in self._routes:
                route_data = self._routes[route_id]
                from src.routing.planner import RoutePlan
                plan = RoutePlan(
                    route_data["plan"]["pois"],
                    RouteConstraints(**route_data["plan"]["constraints"]),
                    route_data["plan"].get("metadata"),
                )
                routes.append(plan)

        if not routes:
            return []

        # Use personalized ranking
        ranked = await self.personalized_ranker.rank_for_user(
            routes=routes,
            user_id=user_id,
            preferences=preferences,
        )

        # Return ranked route data
        results = []
        for item in ranked:
            route_id = None
            for rid, rdata in self._routes.items():
                if rdata["plan"] == item["route"].to_dict():
                    route_id = rid
                    break

            if route_id:
                results.append({
                    "route_id": route_id,
                    "score": item["total_score"],
                    "rank": item["rank"],
                })

        return results

    async def provide_feedback(
        self,
        route_id: str,
        user_id: str,
        feedback: dict[str, Any],
    ) -> dict[str, Any]:
        """Provide feedback on a route.

        Args:
            route_id: Route ID
            user_id: User ID
            feedback: Feedback data

        Returns:
            Updated route
        """
        route = self._routes.get(route_id)

        if not route:
            raise NotFoundError("Route", route_id)

        # Store feedback
        if "feedback_history" not in route:
            route["feedback_history"] = []

        route["feedback_history"].append({
            **feedback,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Update personalized ranker
        from src.routing.planner import RoutePlan
        plan = RoutePlan(
            route["plan"]["pois"],
            RouteConstraints(**route["plan"]["constraints"]),
            route["plan"].get("metadata"),
        )

        await self.personalized_ranker.update_user_history(
            user_id=user_id,
            route=plan,
            feedback=feedback,
        )

        logger.info(f"Recorded feedback for route {route_id}")

        return route

    async def get_user_routes(
        self,
        user_id: str,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get routes for a user.

        Args:
            user_id: User ID
            status: Optional status filter
            limit: Maximum results

        Returns:
            List of routes
        """
        user_routes = []

        for route_id, route_data in self._routes.items():
            if route_data.get("user_id") == user_id:
                if status is None or route_data.get("status") == status:
                    user_routes.append({
                        "route_id": route_id,
                        **route_data,
                    })

        # Sort by created_at descending
        user_routes.sort(
            key=lambda r: r.get("created_at", ""),
            reverse=True,
        )

        return user_routes[:limit]

    async def adapt_route_from_feedback(
        self,
        route_id: str,
        user_id: str,
        feedback: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate adapted route based on feedback.

        Args:
            route_id: Original route ID
            user_id: User ID
            feedback: User feedback list

        Returns:
            New adapted route
        """
        original_route = self._routes.get(route_id)

        if not original_route:
            raise NotFoundError("Route", route_id)

        # Get POIs from original route
        original_plan = original_route["plan"]
        pois = original_plan["pois"]
        constraints = RouteConstraints(**original_plan["constraints"])

        # Get preferences if available
        preferences = original_route.get("preferences")

        # Use adaptive planner
        adapted_plan = await self.adaptive_planner.plan_route_with_feedback(
            pois=pois,
            constraints=constraints,
            feedback=feedback,
            preferences=preferences,
        )

        # Store adapted route
        new_route_id = str(uuid.uuid4())
        route_data = {
            "id": new_route_id,
            "user_id": user_id,
            "plan": adapted_plan.to_dict(),
            "parent_route_id": route_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "adapted",
        }

        self._routes[new_route_id] = route_data

        logger.info(f"Created adapted route {new_route_id} from {route_id}")

        return route_data


# Global instance factory
def get_route_service(session: AsyncSession) -> RouteService:
    """Get route service instance.

    Args:
        session: Database session

    Returns:
        Route service instance
    """
    return RouteService(session)
