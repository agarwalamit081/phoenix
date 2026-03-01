"""Route ranker for scoring and ranking route alternatives."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import numpy as np

from src.routing.planner import RoutePlan
from src.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class RouteRanker:
    """Rank route alternatives by multiple criteria."""

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        """Initialize route ranker.

        Args:
            embedding_service: Optional embedding service
        """
        self.embedding_service = embedding_service

    async def rank_routes(
        self,
        routes: list[RoutePlan],
        preferences: list[dict[str, Any]] | None = None,
        weights: dict[str, float] | None = None,
    ) -> list[dict[str, Any]]:
        """Rank routes by multiple criteria.

        Args:
            routes: List of route plans
            preferences: Optional user preferences
            weights: Optional scoring weights

        Returns:
            Ranked routes with scores
        """
        if not routes:
            return []

        # Default weights
        default_weights = {
            "distance_efficiency": 0.25,
            "poi_quality": 0.25,
            "variety": 0.15,
            "preference_match": 0.20,
            "time_efficiency": 0.15,
        }

        scoring_weights = weights or default_weights

        # Score all routes
        scored_routes = []

        for i, route in enumerate(routes):
            scores = await self._score_route(route, preferences, scoring_weights)

            total_score = sum(
                scores.get(factor, 0) * weight
                for factor, weight in scoring_weights.items()
            )

            scored_routes.append({
                "route": route,
                "total_score": total_score,
                "scores": scores,
                "rank": 0,
            })

        # Sort by total score
        scored_routes.sort(key=lambda r: r["total_score"], reverse=True)

        # Assign ranks
        for i, item in enumerate(scored_routes):
            item["rank"] = i + 1

        return scored_routes

    async def _score_route(
        self,
        route: RoutePlan,
        preferences: list[dict[str, Any]] | None,
        weights: dict[str, float],
    ) -> dict[str, float]:
        """Score a route on multiple dimensions.

        Args:
            route: Route plan
            preferences: User preferences
            weights: Scoring weights

        Returns:
            Dimension scores
        """
        scores = {}

        # Distance efficiency (lower is better)
        if route.total_pois > 1:
            scores["distance_efficiency"] = await self._score_distance_efficiency(route)
        else:
            scores["distance_efficiency"] = 0.0

        # POI quality (higher ratings is better)
        scores["poi_quality"] = await self._score_poi_quality(route)

        # Variety (different categories is better)
        scores["variety"] = await self._score_variety(route)

        # Preference match
        if preferences:
            scores["preference_match"] = await self._score_preference_match(
                route,
                preferences,
            )
        else:
            scores["preference_match"] = 0.5

        # Time efficiency
        scores["time_efficiency"] = await self._score_time_efficiency(route)

        return scores

    async def _score_distance_efficiency(self, route: RoutePlan) -> float:
        """Score distance efficiency.

        Args:
            route: Route plan

        Returns:
            Score (0-1)
        """
        if not route.pois or len(route.pois) < 2:
            return 0.5

        # Calculate average distance between consecutive POIs
        total_distance = route.estimated_distance_km
        avg_distance = total_distance / (len(route.pois) - 1)

        # Lower average distance is better
        # Assume 2km is ideal average distance
        ideal_distance = 2.0

        if avg_distance <= ideal_distance:
            return 1.0
        else:
            return max(0.0, 1.0 - (avg_distance - ideal_distance) / 10.0)

    async def _score_poi_quality(self, route: RoutePlan) -> float:
        """Score POI quality based on ratings.

        Args:
            route: Route plan

        Returns:
            Score (0-1)
        """
        if not route.pois:
            return 0.0

        ratings = [
            poi.get("rating", 0)
            for poi in route.pois
            if poi.get("rating")
        ]

        if not ratings:
            return 0.5

        avg_rating = sum(ratings) / len(ratings)

        # Normalize to 0-1 (assuming 5-point scale)
        return min(avg_rating / 5.0, 1.0)

    async def _score_variety(self, route: RoutePlan) -> float:
        """Score category variety.

        Args:
            route: Route plan

        Returns:
            Score (0-1)
        """
        if not route.pois:
            return 0.0

        categories = set(
            poi.get("category", "other")
            for poi in route.pois
        )

        # More unique categories is better
        # Ideal is each POI has different category
        variety_ratio = len(categories) / len(route.pois)

        return variety_ratio

    async def _score_preference_match(
        self,
        route: RoutePlan,
        preferences: list[dict[str, Any]],
    ) -> float:
        """Score preference matching.

        Args:
            route: Route plan
            preferences: User preferences

        Returns:
            Score (0-1)
        """
        if not route.pois or not preferences:
            return 0.5

        # Get liked categories
        liked_categories = set(
            p["value"]
            for p in preferences
            if p.get("preference_type") == "like"
            and p.get("category") == "category"
        )

        if not liked_categories:
            return 0.5

        # Count matches
        matches = 0
        for poi in route.pois:
            category = poi.get("category", "")
            if any(liked.lower() in category.lower() for liked in liked_categories):
                matches += 1

        return matches / len(route.pois)

    async def _score_time_efficiency(self, route: RoutePlan) -> float:
        """Score time efficiency.

        Args:
            route: Route plan

        Returns:
            Score (0-1)
        """
        if not route.pois:
            return 0.5

        duration_hours = route.estimated_duration_minutes / 60

        # Ideal is 6-8 hours
        if 6 <= duration_hours <= 8:
            return 1.0
        elif duration_hours < 6:
            # Too short, penalize
            return max(0.0, duration_hours / 6)
        else:
            # Too long, penalize
            return max(0.0, 1.0 - (duration_hours - 8) / 8)

    async def compare_routes(
        self,
        route1: RoutePlan,
        route2: RoutePlan,
    ) -> dict[str, Any]:
        """Compare two routes in detail.

        Args:
            route1: First route
            route2: Second route

        Returns:
            Comparison results
        """
        comparison = {
            "route1": {
                "total_pois": route1.total_pois,
                "distance_km": route1.estimated_distance_km,
                "duration_minutes": route1.estimated_duration_minutes,
            },
            "route2": {
                "total_pois": route2.total_pois,
                "distance_km": route2.estimated_distance_km,
                "duration_minutes": route2.estimated_duration_minutes,
            },
            "differences": {},
            "recommendation": None,
        }

        # Calculate differences
        diff_pois = route1.total_pois - route2.total_pois
        diff_distance = route1.estimated_distance_km - route2.estimated_distance_km
        diff_duration = route1.estimated_duration_minutes - route2.estimated_duration_minutes

        comparison["differences"] = {
            "total_pois": diff_pois,
            "distance_km": round(diff_distance, 2),
            "duration_minutes": round(diff_duration, 2),
        }

        # Simple recommendation
        if abs(diff_pois) <= 1:
            if diff_distance < 0 and diff_duration < 0:
                comparison["recommendation"] = "route1"
            elif diff_distance > 0 and diff_duration > 0:
                comparison["recommendation"] = "route2"
            else:
                comparison["recommendation"] = "similar"
        else:
            comparison["recommendation"] = "route1" if diff_pois > 0 else "route2"

        return comparison

    async def find_best_alternative(
        self,
        routes: list[RoutePlan],
        criteria: dict[str, Any],
    ) -> RoutePlan | None:
        """Find best route based on specific criteria.

        Args:
            routes: List of routes
            criteria: Selection criteria

        Returns:
            Best matching route
        """
        if not routes:
            return None

        priority = criteria.get("priority", "balanced")

        if priority == "shortest":
            return min(routes, key=lambda r: r.estimated_distance_km)
        elif priority == "fastest":
            return min(routes, key=lambda r: r.estimated_duration_minutes)
        elif priority == "most_pois":
            return max(routes, key=lambda r: r.total_pois)
        elif priority == "highest_quality":
            best_route = None
            best_score = 0.0

            for route in routes:
                score = await self._score_poi_quality(route)
                if score > best_score:
                    best_score = score
                    best_route = route

            return best_route
        else:
            # Balanced - use full ranking
            ranked = await self.rank_routes(routes)
            return ranked[0]["route"] if ranked else None

    async def generate_route_explanation(
        self,
        route: RoutePlan,
        scores: dict[str, float],
    ) -> dict[str, Any]:
        """Generate explanation for route score.

        Args:
            route: Route plan
            scores: Dimension scores

        Returns:
            Explanation details
        """
        explanation = {
            "route_id": str(id(route)),
            "overall_score": sum(scores.values()) / len(scores),
            "strengths": [],
            "weaknesses": [],
            "details": {},
        }

        # Analyze each dimension
        for dimension, score in scores.items():
            explanation["details"][dimension] = {
                "score": score,
                "label": self._get_score_label(score),
            }

            if score >= 0.7:
                explanation["strengths"].append({
                    "dimension": dimension,
                    "description": self._get_strength_description(dimension, route),
                })
            elif score <= 0.3:
                explanation["weaknesses"].append({
                    "dimension": dimension,
                    "description": self._get_weakness_description(dimension, route),
                })

        return explanation

    def _get_score_label(self, score: float) -> str:
        """Get label for score value.

        Args:
            score: Score value

        Returns:
            Label string
        """
        if score >= 0.8:
            return "Excellent"
        elif score >= 0.6:
            return "Good"
        elif score >= 0.4:
            return "Fair"
        else:
            return "Poor"

    def _get_strength_description(
        self,
        dimension: str,
        route: RoutePlan,
    ) -> str:
        """Get strength description.

        Args:
            dimension: Score dimension
            route: Route plan

        Returns:
            Description string
        """
        descriptions = {
            "distance_efficiency": f"Efficient route covering {route.estimated_distance_km:.1f}km",
            "poi_quality": "High-quality POIs with excellent ratings",
            "variety": f"Diverse experience with {len(set(p.get('category', '') for p in route.pois))} categories",
            "preference_match": "Well-matched to your preferences",
            "time_efficiency": f"Optimal duration of {route.estimated_duration_minutes:.0f} minutes",
        }

        return descriptions.get(dimension, "Strong performance")

    def _get_weakness_description(
        self,
        dimension: str,
        route: RoutePlan,
    ) -> str:
        """Get weakness description.

        Args:
            dimension: Score dimension
            route: Route plan

        Returns:
            Description string
        """
        descriptions = {
            "distance_efficiency": f"Route covers {route.estimated_distance_km:.1f}km - consider shorter alternatives",
            "poi_quality": "Some POIs have lower ratings",
            "variety": "Limited variety - consider adding different categories",
            "preference_match": "May not fully align with your preferences",
            "time_efficiency": f"Duration of {route.estimated_duration_minutes:.0f} minutes - consider adjusting",
        }

        return descriptions.get(dimension, "Room for improvement")

    async def rank_by_embedding_similarity(
        self,
        routes: list[RoutePlan],
        reference_route: RoutePlan,
    ) -> list[dict[str, Any]]:
        """Rank routes by embedding similarity to reference.

        Args:
            routes: Routes to rank
            reference_route: Reference route

        Returns:
            Ranked routes with similarity scores
        """
        if not routes:
            return []

        # Generate embeddings for routes
        reference_embedding = await self._generate_route_embedding(reference_route)

        scored = []

        for route in routes:
            route_embedding = await self._generate_route_embedding(route)

            if reference_embedding and route_embedding and self.embedding_service:
                similarity = await self.embedding_service.compute_similarity(
                    reference_embedding,
                    route_embedding,
                )
            else:
                similarity = 0.0

            scored.append({
                "route": route,
                "similarity": similarity,
                "rank": 0,
            })

        # Sort by similarity
        scored.sort(key=lambda r: r["similarity"], reverse=True)

        for i, item in enumerate(scored):
            item["rank"] = i + 1

        return scored

    async def _generate_route_embedding(
        self,
        route: RoutePlan,
    ) -> list[float] | None:
        """Generate embedding for route.

        Args:
            route: Route plan

        Returns:
            Embedding vector or None
        """
        if not self.embedding_service:
            return None

        # Build text description
        parts = []

        parts.append(f"Route with {route.total_pois} POIs")

        # Add categories
        categories = [p.get("category", "other") for p in route.pois]
        if categories:
            parts.append(f"Categories: {', '.join(set(categories))}")

        # Add POI names
        names = [p.get("name", "") for p in route.pois if p.get("name")]
        if names:
            parts.append(f"Places: {', '.join(names[:5])}")

        text = ". ".join(parts)

        try:
            return await self.embedding_service.generate_embedding(text)
        except Exception as e:
            logger.error(f"Failed to generate route embedding: {e}")
            return None


class PersonalizedRanker(RouteRanker):
    """Ranker with personalization based on user history."""

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        """Initialize personalized ranker.

        Args:
            embedding_service: Optional embedding service
        """
        super().__init__(embedding_service)
        self.user_history: dict[str, list[dict[str, Any]]] = {}

    async def update_user_history(
        self,
        user_id: str,
        route: RoutePlan,
        feedback: dict[str, Any],
    ) -> None:
        """Update user history with route feedback.

        Args:
            user_id: User ID
            route: Route taken
            feedback: User feedback
        """
        if user_id not in self.user_history:
            self.user_history[user_id] = []

        self.user_history[user_id].append({
            "route": route,
            "feedback": feedback,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def rank_for_user(
        self,
        routes: list[RoutePlan],
        user_id: str,
        preferences: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Rank routes personalized for user.

        Args:
            routes: Routes to rank
            user_id: User ID
            preferences: User preferences

        Returns:
            Ranked routes
        """
        # Get base ranking
        ranked = await self.rank_routes(routes, preferences)

        # Adjust based on user history
        if user_id in self.user_history:
            history = self.user_history[user_id]

            for item in ranked:
                personalization_boost = await self._calculate_personalization_boost(
                    item["route"],
                    history,
                )
                item["total_score"] += personalization_boost * 0.2
                item["personalization_boost"] = personalization_boost

        # Re-sort after personalization
        ranked.sort(key=lambda r: r["total_score"], reverse=True)

        # Update ranks
        for i, item in enumerate(ranked):
            item["rank"] = i + 1

        return ranked

    async def _calculate_personalization_boost(
        self,
        route: RoutePlan,
        history: list[dict[str, Any]],
    ) -> float:
        """Calculate personalization boost from history.

        Args:
            route: Route to score
            history: User history

        Returns:
            Boost score (0-1)
        """
        if not history:
            return 0.0

        total_boost = 0.0
        count = 0

        for entry in history:
            feedback = entry["feedback"]
            sentiment = feedback.get("sentiment", "neutral")

            # Only learn from positive feedback
            if sentiment == "positive":
                # Check for similar POIs
                liked_categories = set()
                for poi in entry["route"].pois:
                    cat = poi.get("category", "")
                    if cat:
                        liked_categories.add(cat)

                # Match against current route
                matches = 0
                for poi in route.pois:
                    if poi.get("category") in liked_categories:
                        matches += 1

                if route.total_pois > 0:
                    total_boost += matches / route.total_pois
                    count += 1

        return total_boost / count if count > 0 else 0.0


# Global instances
route_ranker = RouteRanker()
personalized_ranker = PersonalizedRanker()


def get_route_ranker() -> RouteRanker:
    """Get route ranker instance.

    Returns:
        Route ranker instance
    """
    return route_ranker


def get_personalized_ranker() -> PersonalizedRanker:
    """Get personalized ranker instance.

    Returns:
        Personalized ranker instance
    """
    return personalized_ranker
