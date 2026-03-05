"""Inference engine for knowledge graph-based recommendations."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.knowledge_graph.neo4j_client import get_neo4j_client

logger = logging.getLogger(__name__)


class InferenceEngine:
    """Inference engine for making recommendations using the knowledge graph."""

    def __init__(self) -> None:
        """Initialize inference engine."""
        self._client = None

    async def _get_client(self):
        """Get Neo4j client."""
        if self._client is None:
            self._client = await get_neo4j_client()
        return self._client

    async def recommend_pois_by_preferences(
        self,
        user_id: uuid.UUID,
        limit: int = 10,
        exclude_visited: bool = True,
    ) -> list[dict[str, Any]]:
        """Recommend POIs based on user preferences.

        Args:
            user_id: User ID
            limit: Maximum number of recommendations
            exclude_visited: Whether to exclude visited POIs

        Returns:
            List of recommended POIs with scores
        """
        client = await self._get_client()

        # Build query based on preferences
        exclude_clause = "AND NOT EXISTS((u)-[:VISITED]->(poi))" if exclude_visited else ""

        query = f"""
        MATCH (u:User {{id: $user_id}})-[:HAS_PREFERENCE]->(p:Preference)
        WHERE p.preference_type = 'like'
        MATCH (poi:POI)
        WHERE poi.category = p.category
        {exclude_clause}
        WITH poi, count(p) as match_count, sum(p.confidence) as total_confidence
        ORDER BY match_count DESC, total_confidence DESC
        LIMIT $limit
        RETURN poi, match_count, total_confidence
        """

        results = await client.execute_query(
            query,
            {"user_id": str(user_id), "limit": limit},
        )

        return [
            {
                "poi": dict(r["poi"]),
                "match_count": r["match_count"],
                "total_confidence": r["total_confidence"],
                "score": r["match_count"] * r["total_confidence"],
            }
            for r in results
        ]

    async def recommend_pois_collaborative(
        self,
        user_id: uuid.UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Recommend POIs using collaborative filtering.

        Args:
            user_id: User ID
            limit: Maximum number of recommendations

        Returns:
            List of recommended POIs
        """
        client = await self._get_client()

        query = """
        MATCH (u1:User {id: $user_id})-[:HAS_PREFERENCE]->(p1:Preference)
        MATCH (u2:User)-[:HAS_PREFERENCE]->(p2:Preference)
        WHERE u1.id <> u2.id
        AND p1.preference_type = 'like'
        AND p2.preference_type = 'like'
        AND p1.category = p2.category
        AND p1.value = p2.value
        MATCH (u2)-[:VISITED]->(poi:POI)
        WHERE NOT EXISTS((u1)-[:VISITED]->(poi))
        WITH poi, count(DISTINCT u2) as visitor_count
        ORDER BY visitor_count DESC
        LIMIT $limit
        RETURN poi, visitor_count
        """

        results = await client.execute_query(
            query,
            {"user_id": str(user_id), "limit": limit},
        )

        return [
            {
                "poi": dict(r["poi"]),
                "visitor_count": r["visitor_count"],
            }
            for r in results
        ]

    async def recommend_pois_content_based(
        self,
        user_id: uuid.UUID,
        poi_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find similar POIs based on content.

        Args:
            user_id: User ID
            poi_id: Reference POI ID
            limit: Maximum number of recommendations

        Returns:
            List of similar POIs
        """
        client = await self._get_client()

        query = """
        MATCH (target:POI {id: $poi_id})
        MATCH (target)-[:IN_CATEGORY]->(c:Category)
        MATCH (similar:POI)-[:IN_CATEGORY]->(c)
        WHERE similar.id <> target.id
        AND NOT EXISTS((:User {id: $user_id})-[:VISITED]->(similar))
        WITH similar, count(c) as shared_categories
        ORDER BY shared_categories DESC
        LIMIT $limit
        RETURN similar, shared_categories
        """

        results = await client.execute_query(
            query,
            {"poi_id": poi_id, "user_id": str(user_id), "limit": limit},
        )

        return [
            {
                "poi": dict(r["similar"]),
                "shared_categories": r["shared_categories"],
            }
            for r in results
        ]

    async def predict_preference_score(
        self,
        user_id: uuid.UUID,
        poi_id: str,
    ) -> dict[str, Any]:
        """Predict user preference score for a POI.

        Args:
            user_id: User ID
            poi_id: POI ID

        Returns:
            Prediction with score
        """
        client = await self._get_client()

        query = """
        MATCH (u:User {id: $user_id})-[:HAS_PREFERENCE]->(p:Preference)
        MATCH (poi:POI {id: $poi_id})-[:IN_CATEGORY]->(c:Category)
        WHERE p.preference_type = 'like'
        AND p.category = c.name
        WITH sum(p.confidence) as score
        RETURN coalesce(score, 0) as preference_score
        """

        results = await client.execute_query(
            query,
            {"user_id": str(user_id), "poi_id": poi_id},
        )

        if results:
            score = results[0]["preference_score"]
            return {
                "poi_id": poi_id,
                "preference_score": score,
                "predicted_rating": min(5.0, score),
            }

        return {
            "poi_id": poi_id,
            "preference_score": 0.0,
            "predicted_rating": 0.0,
        }

    async def find_complementary_pois(
        self,
        poi_ids: list[str],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find POIs that complement the given list.

        Args:
            poi_ids: List of POI IDs
            limit: Maximum number of results

        Returns:
            List of complementary POIs
        """
        client = await self._get_client()

        query = """
        MATCH (poi:POI)
        WHERE poi.id IN $poi_ids
        MATCH (poi)-[:IN_CATEGORY]->(c:Category)
        MATCH (complementary:POI)-[:IN_CATEGORY]->(c)
        WHERE NOT complementary.id IN $poi_ids
        WITH complementary, count(DISTINCT c) as shared_categories
        ORDER BY shared_categories DESC
        LIMIT $limit
        RETURN complementary, shared_categories
        """

        results = await client.execute_query(
            query,
            {"poi_ids": poi_ids, "limit": limit},
        )

        return [
            {
                "poi": dict(r["complementary"]),
                "shared_categories": r["shared_categories"],
            }
            for r in results
        ]

    async def detect_travel_pattern(
        self,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Detect travel patterns from user history.

        Args:
            user_id: User ID

        Returns:
            Detected patterns
        """
        client = await self._get_client()

        query = """
        MATCH (u:User {id: $user_id})-[:VISITED]->(poi:POI)
        OPTIONAL MATCH (poi)-[:IN_CATEGORY]->(c:Category)
        WITH c.name as category, count(poi) as visit_count
        WHERE category IS NOT NULL
        ORDER BY visit_count DESC
        RETURN category, visit_count
        """

        results = await client.execute_query(query, {"user_id": str(user_id)})

        categories = [r["category"] for r in results]

        # Determine travel style
        total_visits = sum(r["visit_count"] for r in results)

        if total_visits == 0:
            travel_style = "explorer"
        else:
            museum_ratio = next(
                (r["visit_count"] / total_visits for r in results if r["category"] == "museum"),
                0,
            )
            food_ratio = next(
                (r["visit_count"] / total_visits for r in results if r["category"] == "restaurant"),
                0,
            )

            if museum_ratio > 0.4:
                travel_style = "cultural"
            elif food_ratio > 0.4:
                travel_style = "foodie"
            else:
                travel_style = "explorer"

        return {
            "travel_style": travel_style,
            "preferred_categories": categories[:5],
            "total_visits": total_visits,
        }

    async def suggest_itinerary_sequence(
        self,
        poi_ids: list[str],
        start_lat: float,
        start_lng: float,
    ) -> list[dict[str, Any]]:
        """Suggest optimal visiting sequence.

        Args:
            poi_ids: List of POI IDs to visit
            start_lat: Starting latitude
            start_lng: Starting longitude

        Returns:
            Ordered list of POIs
        """
        # This is a simple distance-based suggestion
        # For production, use proper routing algorithms
        client = await self._get_client()

        query = """
        MATCH (poi:POI)
        WHERE poi.id IN $poi_ids
        RETURN poi.id as id, poi.name as name,
               poi.latitude as latitude, poi.longitude as longitude
        """

        results = await client.execute_query(query, {"poi_ids": poi_ids})

        pois = [dict(r) for r in results]

        # Simple nearest neighbor algorithm
        unvisited = pois.copy()
        sequence = []
        current_lat = start_lat
        current_lng = start_lng

        while unvisited:
            # Find nearest unvisited POI
            nearest = min(
                unvisited,
                key=lambda p: ((p["latitude"] - current_lat) ** 2 +
                              (p["longitude"] - current_lng) ** 2) ** 0.5,
            )

            sequence.append(nearest)
            unvisited.remove(nearest)
            current_lat = nearest["latitude"]
            current_lng = nearest["longitude"]

        return sequence

    async def explain_recommendation(
        self,
        user_id: uuid.UUID,
        poi_id: str,
    ) -> dict[str, Any]:
        """Explain why a POI is recommended.

        Args:
            user_id: User ID
            poi_id: POI ID

        Returns:
            Explanation with reasons
        """
        client = await self._get_client()

        query = """
        MATCH (u:User {id: $user_id})-[:HAS_PREFERENCE]->(p:Preference)
        MATCH (poi:POI {id: $poi_id})-[:IN_CATEGORY]->(c:Category)
        WHERE p.preference_type = 'like'
        AND p.category = c.name
        RETURN p.value as preference_value, c.name as category
        """

        results = await client.execute_query(
            query,
            {"user_id": str(user_id), "poi_id": poi_id},
        )

        reasons = []
        for r in results:
            reasons.append({
                "type": "preference_match",
                "category": r["category"],
                "value": r["preference_value"],
                "description": f"You like {r['preference_value']} in {r['category']} category",
            })

        # Check collaborative reasons
        collab_query = """
        MATCH (u:User {id: $user_id})-[:HAS_PREFERENCE]->(p1:Preference)
        MATCH (similar:User)-[:HAS_PREFERENCE]->(p2:Preference)
        WHERE p1.preference_type = 'like'
        AND p2.preference_type = 'like'
        AND p1.category = p2.category
        AND p1.value = p2.value
        MATCH (similar)-[:VISITED]->(poi:POI {id: $poi_id})
        RETURN count(DISTINCT similar) as similar_visitors
        """

        collab_results = await client.execute_query(
            collab_query,
            {"user_id": str(user_id), "poi_id": poi_id},
        )

        if collab_results and collab_results[0]["similar_visitors"] > 0:
            count = collab_results[0]["similar_visitors"]
            reasons.append({
                "type": "collaborative",
                "count": count,
                "description": f"{count} similar users visited this place",
            })

        return {
            "poi_id": poi_id,
            "reasons": reasons,
            "total_reasons": len(reasons),
        }


# Global instance
inference_engine = InferenceEngine()
