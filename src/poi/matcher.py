"""POI matcher for matching POIs to user preferences."""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np

from src.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class POIMatcher:
    """Match POIs to user preferences."""

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        """Initialize POI matcher.

        Args:
            embedding_service: Optional embedding service
        """
        self.embedding_service = embedding_service

    async def calculate_match_score(
        self,
        poi: dict[str, Any],
        preferences: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Calculate match score for a POI against preferences.

        Args:
            poi: POI data
            preferences: User preferences

        Returns:
            Match result with score and details
        """
        score = 0.0
        factors = []

        # Category matching
        category_score = await self._score_category(poi, preferences)
        score += category_score * 0.4
        factors.append({"factor": "category", "score": category_score, "weight": 0.4})

        # Embedding similarity
        embedding_score = await self._score_embedding(poi, preferences)
        score += embedding_score * 0.3
        factors.append({"factor": "embedding", "score": embedding_score, "weight": 0.3})

        # Type matching
        type_score = await self._score_types(poi, preferences)
        score += type_score * 0.15
        factors.append({"factor": "types", "score": type_score, "weight": 0.15})

        # Rating preference
        rating_score = await self._score_rating(poi, preferences)
        score += rating_score * 0.15
        factors.append({"factor": "rating", "score": rating_score, "weight": 0.15})

        return {
            "poi_id": poi.get("id"),
            "poi_name": poi.get("name"),
            "score": min(score, 1.0),
            "factors": factors,
            "matched_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _score_category(
        self,
        poi: dict[str, Any],
        preferences: list[dict[str, Any]],
    ) -> float:
        """Score category matching.

        Args:
            poi: POI data
            preferences: User preferences

        Returns:
            Category score (0-1)
        """
        poi_category = poi.get("category", "")

        # Get liked categories
        liked_categories = [
            p["value"] for p in preferences
            if p["preference_type"] == "like"
            and p["category"] == "category"
        ]

        # Get disliked categories
        disliked_categories = [
            p["value"] for p in preferences
            if p["preference_type"] == "dislike"
            and p["category"] == "category"
        ]

        score = 0.0

        # Check if POI category is liked
        for liked in liked_categories:
            if liked.lower() in poi_category.lower() or poi_category.lower() in liked.lower():
                score += 0.5

        # Check if POI category is disliked
        for disliked in disliked_categories:
            if disliked.lower() in poi_category.lower() or poi_category.lower() in disliked.lower():
                score -= 0.8

        return max(min(score, 1.0), 0.0)

    async def _score_embedding(
        self,
        poi: dict[str, Any],
        preferences: list[dict[str, Any]],
    ) -> float:
        """Score using embedding similarity.

        Args:
            poi: POI data
            preferences: User preferences

        Returns:
            Embedding score (0-1)
        """
        if not self.embedding_service:
            return 0.0

        poi_embedding = poi.get("embedding")

        if not poi_embedding:
            return 0.0

        # Get preference embeddings
        pref_embeddings = [
            p.get("embedding") for p in preferences
            if p.get("preference_type") == "like" and p.get("embedding")
        ]

        if not pref_embeddings:
            return 0.0

        # Calculate average similarity
        similarities = []

        for pref_emb in pref_embeddings:
            try:
                sim = await self.embedding_service.compute_similarity(
                    poi_embedding,
                    pref_emb,
                )
                similarities.append(sim)
            except Exception:
                pass

        if not similarities:
            return 0.0

        # Return max similarity (best match)
        return max(similarities)

    async def _score_types(
        self,
        poi: dict[str, Any],
        preferences: list[dict[str, Any]],
    ) -> float:
        """Score type matching.

        Args:
            poi: POI data
            preferences: User preferences

        Returns:
            Type score (0-1)
        """
        poi_types = set(poi.get("types", []))
        poi_category = poi.get("category", "")

        # Get liked types
        liked_types = [
            p["value"].lower() for p in preferences
            if p["preference_type"] == "like"
            and p["category"] in ["activity", "type", poi_category]
        ]

        if not liked_types:
            return 0.0

        # Count matches
        matches = 0
        for liked in liked_types:
            if any(liked in poi_type.lower() for poi_type in poi_types):
                matches += 1

        return min(matches / len(liked_types), 1.0)

    async def _score_rating(
        self,
        poi: dict[str, Any],
        preferences: list[dict[str, Any]],
    ) -> float:
        """Score based on rating preferences.

        Args:
            poi: POI data
            preferences: User preferences

        Returns:
            Rating score (0-1)
        """
        poi_rating = poi.get("rating")

        if poi_rating is None:
            return 0.0

        # Get rating preference
        rating_prefs = [
            p for p in preferences
            if p["category"] == "rating"
        ]

        if not rating_prefs:
            # Default: prefer higher ratings
            return min(poi_rating / 5.0, 1.0)

        # Check against preferences
        for pref in rating_prefs:
            if pref["preference_type"] == "like":
                try:
                    min_rating = float(pref["value"])
                    if poi_rating >= min_rating:
                        return 1.0
                except (ValueError, TypeError):
                    pass

        return 0.0

    async def rank_pois(
        self,
        pois: list[dict[str, Any]],
        preferences: list[dict[str, Any]],
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Rank POIs by preference match.

        Args:
            pois: List of POI data
            preferences: User preferences
            limit: Maximum POIs to return

        Returns:
            Ranked list of POIs
        """
        # Calculate scores for all POIs
        tasks = [
            self.calculate_match_score(poi, preferences)
            for poi in pois
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter and sort
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to score POI {pois[i].get('name')}: {result}")
            else:
                valid_results.append(result)

        # Sort by score descending
        valid_results.sort(key=lambda r: r["score"], reverse=True)

        return valid_results[:limit]

    async def filter_pois(
        self,
        pois: list[dict[str, Any]],
        preferences: list[dict[str, Any]],
        min_score: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Filter POIs by minimum match score.

        Args:
            pois: List of POI data
            preferences: User preferences
            min_score: Minimum match score

        Returns:
            Filtered list of POIs
        """
        ranked = await self.rank_pois(pois, preferences, limit=len(pois))

        return [
            r for r in ranked
            if r["score"] >= min_score
        ]

    async def find_similar_pois(
        self,
        poi: dict[str, Any],
        candidate_pois: list[dict[str, Any]],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find POIs similar to a given POI.

        Args:
            poi: Reference POI
            candidate_pois: Candidate POIs
            limit: Maximum results

        Returns:
            List of similar POIs with scores
        """
        poi_embedding = poi.get("embedding")

        if not poi_embedding:
            # Fall back to category matching
            category = poi.get("category", "")
            similar = [
                p for p in candidate_pois
                if p.get("category") == category and p.get("id") != poi.get("id")
            ]
            return [
                {
                    "poi_id": p.get("id"),
                    "poi_name": p.get("name"),
                    "similarity": 1.0 if p.get("id") == poi.get("id") else 0.5,
                }
                for p in similar[:limit]
            ]

        # Calculate embedding similarities
        results = []

        for candidate in candidate_pois:
            if candidate.get("id") == poi.get("id"):
                continue

            cand_embedding = candidate.get("embedding")

            if cand_embedding:
                try:
                    similarity = await self.embedding_service.compute_similarity(
                        poi_embedding,
                        cand_embedding,
                    )

                    results.append({
                        "poi_id": candidate.get("id"),
                        "poi_name": candidate.get("name"),
                        "similarity": similarity,
                    })

                except Exception as e:
                    logger.error(f"Failed to calculate similarity: {e}")

        # Sort by similarity descending
        results.sort(key=lambda r: r["similarity"], reverse=True)

        return results[:limit]

    async def recommend_by_preferences(
        self,
        pois: list[dict[str, Any]],
        preferences: list[dict[str, Any]],
        limit_per_category: int = 5,
    ) -> dict[str, list[dict[str, Any]]]:
        """Recommend POIs grouped by category.

        Args:
            pois: List of POI data
            preferences: User preferences
            limit_per_category: Max POIs per category

        Returns:
            Recommendations grouped by category
        """
        # Get preferred categories
        preferred_cats = [
            p["value"] for p in preferences
            if p["preference_type"] == "like"
            and p["category"] == "category"
        ]

        if not preferred_cats:
            # No category preferences, return top ranked POIs
            ranked = await self.rank_pois(pois, preferences, limit=limit_per_category * 3)
            return {"recommended": [{"poi": poi, "score": r["score"]} for poi, r in zip(pois, ranked)]}

        # Group POIs by category
        by_category = defaultdict(list)

        for poi in pois:
            cat = poi.get("category", "other")
            by_category[cat].append(poi)

        # Rank within each category
        recommendations = {}

        for category in preferred_cats:
            if category not in by_category:
                continue

            category_pois = by_category[category]

            ranked = await self.rank_pois(category_pois, preferences, limit=limit_per_category)

            recommendations[category] = [
                {"poi": poi, "score": r["score"]}
                for poi, r in zip(category_pois, ranked)
            ]

        return recommendations


class PreferenceMatcher:
    """High-level preference matching service."""

    def __init__(
        self,
        matcher: POIMatcher | None = None,
    ) -> None:
        """Initialize preference matcher.

        Args:
            matcher: Optional POI matcher
        """
        self.matcher = matcher or POIMatcher()

    async def get_recommendations(
        self,
        user_id: str,
        pois: list[dict[str, Any]],
        preferences: list[dict[str, Any]],
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get personalized POI recommendations.

        Args:
            user_id: User ID
            pois: Available POIs
            preferences: User preferences
            limit: Maximum recommendations

        Returns:
            List of recommended POIs with scores
        """
        ranked = await self.matcher.rank_pois(pois, preferences, limit=limit)

        return [
            {
                **poi,
                "recommendation_score": r["score"],
                "match_factors": r["factors"],
            }
            for r, poi in zip(ranked, pois)
            if r["score"] > 0.3
        ]

    async def get_explanation(
        self,
        poi: dict[str, Any],
        preferences: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate explanation for POI recommendation.

        Args:
            poi: POI data
            preferences: User preferences

        Returns:
            Explanation with reasons
        """
        match_result = await self.matcher.calculate_match_score(poi, preferences)

        reasons = []

        for factor in match_result["factors"]:
            if factor["score"] > 0.1:
                if factor["factor"] == "category":
                    reasons.append({
                        "type": "category_match",
                        "description": f"Matches your interest in {poi.get('category')} places",
                    })
                elif factor["factor"] == "types":
                    reasons.append({
                        "type": "feature_match",
                        "description": f"Has features you like: {', '.join(poi.get('types', [])[:3])}",
                    })
                elif factor["factor"] == "rating":
                    reasons.append({
                        "type": "high_rating",
                        "description": f"Well-rated with {poi.get('rating')}/5 stars",
                    })
                elif factor["factor"] == "embedding":
                    reasons.append({
                        "type": "similar_interests",
                        "description": "Similar to places you've enjoyed",
                    })

        return {
            "poi_id": poi.get("id"),
            "poi_name": poi.get("name"),
            "score": match_result["score"],
            "reasons": reasons,
        }


# Global instances
poi_matcher = POIMatcher()
preference_matcher = PreferenceMatcher()
