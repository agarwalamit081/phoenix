"""Neo4j knowledge graph repository for user preferences."""

import uuid
from datetime import datetime, timezone
from typing import Any

from src.config.logging import logger
from src.knowledge_graph.neo4j_client import Neo4jClient, get_neo4j_client


class PreferenceRepository:
    """Repository for user preferences in Neo4j knowledge graph."""

    def __init__(self, client: Neo4jClient | None = None) -> None:
        """Initialize the preference repository.

        Args:
            client: Neo4j client (uses global client if None)
        """
        self._client = client

    async def _get_client(self) -> Neo4jClient:
        """Get Neo4j client."""
        if self._client:
            return self._client
        return await get_neo4j_client()

    async def add_preference(
        self,
        user_id: uuid.UUID,
        category: str,
        value: str,
        weight: float = 1.0,
        preference_type: str = "LIKES",
        context: dict[str, Any] | None = None,
    ) -> None:
        """Add a user preference to the knowledge graph.

        Args:
            user_id: User ID
            category: Preference category (e.g., "FOOD", "ART")
            value: Preference value (e.g., "italian", "impressionism")
            weight: Preference weight (0.0 to 1.0)
            preference_type: Type of preference (LIKES, DISLIKES, etc.)
            context: Additional context (source, location, etc.)
        """
        client = await self._get_client()

        query = """
        MERGE (u:User {id: $user_id})
        MERGE (p:Preference {category: $category, value: $value})
        MERGE (u)-[r:HAS_PREFERENCE]->(p)
        SET r.type = $type,
            r.weight = $weight,
            r.updated_at = datetime(),
            r.context = $context
        RETURN u, p, r
        """

        try:
            await client.execute_query(
                query,
                {
                    "user_id": str(user_id),
                    "category": category,
                    "value": value,
                    "type": preference_type,
                    "weight": weight,
                    "context": context or {},
                },
            )
            logger.debug(f"Added preference {category}:{value} for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to add preference: {e}")
            raise

    async def get_preferences(
        self,
        user_id: uuid.UUID,
        preference_type: str | None = None,
        min_weight: float | None = None,
    ) -> list[dict[str, Any]]:
        """Get user preferences.

        Args:
            user_id: User ID
            preference_type: Filter by preference type (optional)
            min_weight: Minimum weight threshold (optional)

        Returns:
            List of preferences
        """
        client = await self._get_client()

        where_clauses = ["u.id = $user_id"]
        if preference_type:
            where_clauses.append("r.type = $type")
        if min_weight is not None:
            where_clauses.append("r.weight >= $min_weight")

        where_clause = " AND ".join(where_clauses)

        query = f"""
        MATCH (u:User)-[r:HAS_PREFERENCE]->(p:Preference)
        WHERE {where_clause}
        RETURN p.category AS category,
               p.value AS value,
               r.type AS type,
               r.weight AS weight,
               r.updated_at AS updated_at,
               r.context AS context
        ORDER BY r.weight DESC
        """

        try:
            params: dict[str, Any] = {"user_id": str(user_id)}
            if preference_type:
                params["type"] = preference_type
            if min_weight is not None:
                params["min_weight"] = min_weight

            results = await client.execute_query(query, params)
            return results
        except Exception as e:
            logger.error(f"Failed to get preferences for user {user_id}: {e}")
            return []

    async def get_dislikes(
        self,
        user_id: uuid.UUID,
        min_weight: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Get user dislikes.

        Args:
            user_id: User ID
            min_weight: Minimum weight for dislike

        Returns:
            List of dislikes
        """
        return await self.get_preferences(
            user_id,
            preference_type="DISLIKES",
            min_weight=min_weight,
        )

    async def get_likes(
        self,
        user_id: uuid.UUID,
        min_weight: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Get user likes.

        Args:
            user_id: User ID
            min_weight: Minimum weight for like

        Returns:
            List of likes
        """
        return await self.get_preferences(
            user_id,
            preference_type="LIKES",
            min_weight=min_weight,
        )

    async def remove_preference(
        self,
        user_id: uuid.UUID,
        category: str,
        value: str,
    ) -> bool:
        """Remove a user preference.

        Args:
            user_id: User ID
            category: Preference category
            value: Preference value

        Returns:
            True if removed
        """
        client = await self._get_client()

        query = """
        MATCH (u:User {id: $user_id})-[r:HAS_PREFERENCE]->(p:Preference {category: $category, value: $value})
        DELETE r
        RETURN count(r) as deleted
        """

        try:
            results = await client.execute_query(
                query,
                {
                    "user_id": str(user_id),
                    "category": category,
                    "value": value,
                },
            )
            deleted = results[0]["deleted"] if results else 0
            logger.debug(f"Removed {deleted} preference(s) for user {user_id}")
            return deleted > 0
        except Exception as e:
            logger.error(f"Failed to remove preference: {e}")
            return False

    async def update_preference_weight(
        self,
        user_id: uuid.UUID,
        category: str,
        value: str,
        new_weight: float,
    ) -> bool:
        """Update preference weight.

        Args:
            user_id: User ID
            category: Preference category
            value: Preference value
            new_weight: New weight value

        Returns:
            True if updated
        """
        client = await self._get_client()

        query = """
        MATCH (u:User {id: $user_id})-[r:HAS_PREFERENCE]->(p:Preference {category: $category, value: $value})
        SET r.weight = $new_weight,
            r.updated_at = datetime()
        RETURN r.weight as weight
        """

        try:
            results = await client.execute_query(
                query,
                {
                    "user_id": str(user_id),
                    "category": category,
                    "value": value,
                    "new_weight": new_weight,
                },
            )
            return len(results) > 0
        except Exception as e:
            logger.error(f"Failed to update preference weight: {e}")
            return False

    async def get_preference_summary(
        self,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Get summary of user preferences.

        Args:
            user_id: User ID

        Returns:
            Preference summary with category breakdown
        """
        client = await self._get_client()

        query = """
        MATCH (u:User {id: $user_id})-[r:HAS_PREFERENCE]->(p:Preference)
        WITH p.category as category,
             count(p) as count,
             avg(r.weight) as avg_weight,
             collect({value: p.value, weight: r.weight, type: r.type}) as preferences
        RETURN category,
               count,
               avg_weight,
               preferences
        ORDER BY count DESC
        """

        try:
            results = await client.execute_query(query, {"user_id": str(user_id)})

            return {
                "user_id": str(user_id),
                "categories": results,
                "total_preferences": sum(r["count"] for r in results),
            }
        except Exception as e:
            logger.error(f"Failed to get preference summary: {e}")
            return {"user_id": str(user_id), "categories": [], "total_preferences": 0}

    async def find_similar_users(
        self,
        user_id: uuid.UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find users with similar preferences.

        Args:
            user_id: User ID
            limit: Maximum number of similar users

        Returns:
            List of similar users with similarity scores
        """
        client = await self._get_client()

        query = """
        MATCH (u1:User {id: $user_id})-[r1:HAS_PREFERENCE]->(p:Preference)<-[r2:HAS_PREFERENCE]-(u2:User)
        WHERE u1.id <> u2.id
        WITH u2, p, (r1.weight * r2.weight) as weight_product
        WITH u2, sum(weight_product) as similarity_score
        RETURN u2.id as user_id,
               similarity_score
        ORDER BY similarity_score DESC
        LIMIT $limit
        """

        try:
            results = await client.execute_query(
                query,
                {
                    "user_id": str(user_id),
                    "limit": limit,
                },
            )
            return results
        except Exception as e:
            logger.error(f"Failed to find similar users: {e}")
            return []

    async def get_recommendations_from_preferences(
        self,
        user_id: uuid.UUID,
        category: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get POI recommendations based on user preferences.

        Args:
            user_id: User ID
            category: Filter by category (optional)
            limit: Maximum number of recommendations

        Returns:
            List of recommended preference values
        """
        client = await self._get_client()

        where_conditions = ["u.id = $user_id", "r.type = 'LIKES'"]
        if category:
            where_conditions.append("p.category = $category")

        where_clause = " AND ".join(where_conditions)

        query = f"""
        MATCH (u:User)-[r:HAS_PREFERENCE]->(p:Preference)
        WHERE {where_clause}
        RETURN p.category AS category,
               p.value AS value,
               r.weight AS relevance
        ORDER BY r.weight DESC
        LIMIT $limit
        """

        try:
            params: dict[str, Any] = {"user_id": str(user_id), "limit": limit}
            if category:
                params["category"] = category

            results = await client.execute_query(query, params)
            return results
        except Exception as e:
            logger.error(f"Failed to get recommendations: {e}")
            return []

    async def record_behavior(
        self,
        user_id: uuid.UUID,
        behavior_type: str,
        category: str,
        value: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Record user behavior for preference learning.

        Args:
            user_id: User ID
            behavior_type: Type of behavior (visited, skipped, rated, etc.)
            category: POI category
            value: POI value
            context: Additional context
        """
        client = await self._get_client()

        query = """
        MERGE (u:User {id: $user_id})
        MERGE (b:Behavior {type: $behavior_type, category: $category, value: $value})
        CREATE (u)-[r:PERFORMED]->(b)
        SET r.timestamp = datetime(),
            r.context = $context
        """

        try:
            await client.execute_query(
                query,
                {
                    "user_id": str(user_id),
                    "behavior_type": behavior_type,
                    "category": category,
                    "value": value,
                    "context": context or {},
                },
            )
            logger.debug(f"Recorded behavior {behavior_type} for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to record behavior: {e}")
            raise

    async def get_behavior_history(
        self,
        user_id: uuid.UUID,
        behavior_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get user behavior history.

        Args:
            user_id: User ID
            behavior_type: Filter by behavior type (optional)
            limit: Maximum number of records

        Returns:
            List of behaviors
        """
        client = await self._get_client()

        where_conditions = ["u.id = $user_id"]
        if behavior_type:
            where_conditions.append("b.type = $behavior_type")

        where_clause = " AND ".join(where_conditions)

        query = f"""
        MATCH (u:User)-[r:PERFORMED]->(b:Behavior)
        WHERE {where_clause}
        RETURN b.type AS behavior_type,
               b.category AS category,
               b.value AS value,
               r.timestamp AS timestamp,
               r.context AS context
        ORDER BY r.timestamp DESC
        LIMIT $limit
        """

        try:
            params: dict[str, Any] = {"user_id": str(user_id), "limit": limit}
            if behavior_type:
                params["behavior_type"] = behavior_type

            results = await client.execute_query(query, params)
            return results
        except Exception as e:
            logger.error(f"Failed to get behavior history: {e}")
            return []


# Global repository instance
_global_repository: PreferenceRepository | None = None


def get_preference_repository() -> PreferenceRepository:
    """Get global preference repository instance.

    Returns:
        Preference repository
    """
    global _global_repository

    if _global_repository is None:
        _global_repository = PreferenceRepository()

    return _global_repository
