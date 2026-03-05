"""Preference mapper for integrating preferences with knowledge graph."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.knowledge_graph.graph_builder import graph_builder
from src.knowledge_graph.neo4j_client import get_neo4j_client
from src.models.preference import Preference
from src.schemas.preference import PreferenceCreateRequest, PreferenceType

logger = logging.getLogger(__name__)


class PreferenceMapper:
    """Map user preferences to knowledge graph nodes and relationships."""

    def __init__(self) -> None:
        """Initialize preference mapper."""
        self._client = None
        self._builder = graph_builder

    async def _get_client(self):
        """Get Neo4j client."""
        if self._client is None:
            self._client = await get_neo4j_client()
        return self._client

    async def sync_preference_to_graph(
        self,
        user_id: uuid.UUID,
        preference: Preference | PreferenceCreateRequest,
    ) -> dict[str, Any]:
        """Sync a preference to the knowledge graph.

        Args:
            user_id: User ID
            preference: Preference data

        Returns:
            Created graph node data
        """
        pref_id = str(preference.id) if isinstance(preference, Preference) else str(uuid.uuid4())

        # Ensure category node exists
        await self._builder.create_category_node(
            name=preference.category,
        )

        # Create preference node
        node = await self._builder.create_preference_node(
            preference_id=pref_id,
            user_id=user_id,
            category=preference.category,
            value=preference.value,
            preference_type=preference.preference_type.value,
            confidence=preference.confidence_score,
        )

        # Link to category
        await self._builder.link_preference_to_category(
            preference_id=pref_id,
            category_name=preference.category,
        )

        # Extract and link POIs if mentioned in value
        await self._extract_and_link_pois(pref_id, preference.value, preference.category)

        logger.info(f"Synced preference {pref_id} to graph")

        return node

    async def _extract_and_link_pois(
        self,
        preference_id: str,
        value: str,
        category: str,
    ) -> None:
        """Extract POI names from preference value and create relationships.

        Args:
            preference_id: Preference ID
            value: Preference value (may contain POI names)
            category: Preference category
        """
        client = await self._get_client()

        # Look for POIs with matching names or categories
        query = """
        MATCH (p:POI)
        WHERE p.name CONTAINS $value OR p.category = $category
        MATCH (pref:Preference {id: $preference_id})
        MERGE (pref)-[r:REFERS_TO]->(p)
        SET r.created_at = datetime()
        RETURN p.name as poi_name
        """

        try:
            results = await client.execute_query(
                query,
                {
                    "value": value,
                    "category": category,
                    "preference_id": preference_id,
                },
            )

            if results:
                poi_names = [r["poi_name"] for r in results]
                logger.debug(f"Linked preference {preference_id} to POIs: {poi_names}")

        except Exception as e:
            logger.error(f"Failed to link POIs: {e}")

    async def get_preference_recommendations(
        self,
        user_id: uuid.UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get POI recommendations based on user preferences.

        Args:
            user_id: User ID
            limit: Maximum recommendations

        Returns:
            List of recommended POIs
        """
        client = await self._get_client()

        query = """
        MATCH (u:User {id: $user_id})-[:HAS_PREFERENCE]->(p:Preference)
        WHERE p.preference_type = 'like'
        MATCH (poi:POI)
        WHERE poi.category = p.category
        AND NOT EXISTS((u)-[:VISITED]->(poi))
        WITH poi, count(p) as relevance
        ORDER BY relevance DESC
        LIMIT $limit
        RETURN poi, relevance
        """

        results = await client.execute_query(
            query,
            {"user_id": str(user_id), "limit": limit},
        )

        return [
            {
                "poi": dict(r["poi"]),
                "relevance": r["relevance"],
            }
            for r in results
        ]

    async def get_conflicting_preferences(
        self,
        user_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Find conflicting user preferences.

        Args:
            user_id: User ID

        Returns:
            List of conflicts
        """
        client = await self._get_client()

        query = """
        MATCH (u:User {id: $user_id})-[:HAS_PREFERENCE]->(p1:Preference)
        MATCH (u)-[:HAS_PREFERENCE]->(p2:Preference)
        WHERE p1.category = p2.category
        AND p1.preference_type <> p2.preference_type
        AND p1.id < p2.id
        RETURN p1, p2
        """

        results = await client.execute_query(query, {"user_id": str(user_id)})

        return [
            {
                "preference_1": dict(r["p1"]),
                "preference_2": dict(r["p2"]),
            }
            for r in results
        ]

    async def find_users_with_similar_preferences(
        self,
        user_id: uuid.UUID,
        min_shared: int = 2,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find users with similar preferences.

        Args:
            user_id: User ID
            min_shared: Minimum shared preferences
            limit: Maximum results

        Returns:
            List of similar users
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
        WITH u2, count(DISTINCT p1.category) as shared
        WHERE shared >= $min_shared
        ORDER BY shared DESC
        LIMIT $limit
        RETURN u2, shared
        """

        results = await client.execute_query(
            query,
            {
                "user_id": str(user_id),
                "min_shared": min_shared,
                "limit": limit,
            },
        )

        return [
            {
                "user": dict(r["u2"]),
                "shared_preferences": r["shared"],
            }
            for r in results
        ]

    async def get_popular_preferences(
        self,
        category: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get most popular preferences.

        Args:
            category: Optional category filter
            limit: Maximum results

        Returns:
            List of popular preferences
        """
        client = await self._get_client()

        if category:
            query = """
            MATCH (p:Preference)
            WHERE p.preference_type = 'like'
            AND p.category = $category
            WITH p.value as value, p.category as category, count(p) as popularity
            ORDER BY popularity DESC
            LIMIT $limit
            RETURN value, category, popularity
            """
            params = {"category": category, "limit": limit}
        else:
            query = """
            MATCH (p:Preference)
            WHERE p.preference_type = 'like'
            WITH p.value as value, p.category as category, count(p) as popularity
            ORDER BY popularity DESC
            LIMIT $limit
            RETURN value, category, popularity
            """
            params = {"limit": limit}

        results = await client.execute_query(query, params)

        return [
            {
                "value": r["value"],
                "category": r["category"],
                "popularity": r["popularity"],
            }
            for r in results
        ]

    async def delete_preference_from_graph(
        self,
        preference_id: str,
    ) -> bool:
        """Delete a preference from the graph.

        Args:
            preference_id: Preference ID

        Returns:
            True if deleted
        """
        client = await self._get_client()

        return await client.delete_node(
            label="Preference",
            property_name="id",
            property_value=preference_id,
        )

    async def update_preference_in_graph(
        self,
        preference_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Update a preference in the graph.

        Args:
            preference_id: Preference ID
            updates: Properties to update

        Returns:
            Updated node data
        """
        client = await self._get_client()

        return await client.update_node(
            label="Preference",
            property_name="id",
            property_value=preference_id,
            updates=updates,
        )

    async def infer_preferences_from_behavior(
        self,
        user_id: uuid.UUID,
        visited_pois: list[str],
    ) -> list[dict[str, Any]]:
        """Infer preferences from visited POIs.

        Args:
            user_id: User ID
            visited_pois: List of visited POI IDs

        Returns:
            List of inferred preferences
        """
        client = await self._get_client()

        # Find categories of visited POIs
        query = """
        MATCH (u:User {id: $user_id})
        MATCH (poi:POI)
        WHERE poi.id IN $visited_pois
        OPTIONAL MATCH (poi)-[:IN_CATEGORY]->(c:Category)
        RETURN DISTINCT c.name as category, count(poi) as visit_count
        ORDER BY visit_count DESC
        """

        results = await client.execute_query(
            query,
            {"user_id": str(user_id), "visited_pois": visited_pois},
        )

        inferred = []
        for r in results:
            if r["category"]:
                inferred.append({
                    "category": r["category"],
                    "value": "inferred_from_visits",
                    "preference_type": "like",
                    "confidence": min(0.9, 0.1 + r["visit_count"] * 0.1),
                    "source": "behavioral_inference",
                })

        return inferred

    async def get_preference_summary(
        self,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Get summary of user's preferences.

        Args:
            user_id: User ID

        Returns:
            Preference summary
        """
        client = await self._get_client()

        query = """
        MATCH (u:User {id: $user_id})-[:HAS_PREFERENCE]->(p:Preference)
        WITH p.preference_type as type, count(p) as count
        RETURN type, count
        """

        results = await client.execute_query(query, {"user_id": str(user_id)})

        summary = {r["type"]: r["count"] for r in results}
        summary["total"] = sum(summary.values())

        return summary


# Global mapper instance
preference_mapper = PreferenceMapper()
