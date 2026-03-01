"""Knowledge graph builder for Phoenix Travel Companion."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.knowledge_graph.neo4j_client import get_neo4j_client

logger = logging.getLogger(__name__)


class KnowledgeGraphBuilder:
    """Builder for creating and maintaining the knowledge graph."""

    def __init__(self) -> None:
        """Initialize graph builder."""
        self._client = None
        self._indexes_created = False

    async def _get_client(self):
        """Get Neo4j client."""
        if self._client is None:
            self._client = await get_neo4j_client()
        return self._client

    async def initialize_schema(self) -> None:
        """Initialize graph schema with indexes and constraints."""
        client = await self._get_client()

        # Create uniqueness constraints
        constraints = [
            "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
            "CREATE CONSTRAINT poi_id_unique IF NOT EXISTS FOR (p:POI) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT category_name_unique IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE",
            "CREATE CONSTRAINT preference_id_unique IF NOT EXISTS FOR (p:Preference) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT itinerary_id_unique IF NOT EXISTS FOR (i:Itinerary) REQUIRE i.id IS UNIQUE",
        ]

        for constraint in constraints:
            try:
                await client.execute_write(constraint)
                logger.info(f"Created constraint: {constraint}")
            except Exception as e:
                logger.debug(f"Constraint may already exist: {e}")

        # Create indexes
        indexes = [
            "CREATE INDEX user_email_idx IF NOT EXISTS FOR (u:User) ON (u.email)",
            "CREATE INDEX poi_name_idx IF NOT EXISTS FOR (p:POI) ON (p.name)",
            "CREATE INDEX poi_location_idx IF NOT EXISTS FOR (p:POI) ON (p.latitude, p.longitude)",
            "CREATE INDEX poi_category_idx IF NOT EXISTS FOR (p:POI) ON (p.category)",
            "CREATE INDEX itinerary_user_idx IF NOT EXISTS FOR (i:Itinerary) ON (i.user_id)",
        ]

        for index in indexes:
            try:
                await client.execute_write(index)
                logger.info(f"Created index: {index}")
            except Exception as e:
                logger.debug(f"Index may already exist: {e}")

        self._indexes_created = True
        logger.info("Knowledge graph schema initialized")

    async def create_user_node(
        self,
        user_id: uuid.UUID,
        email: str,
        display_name: str | None = None,
        preferences: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a user node in the graph.

        Args:
            user_id: User ID
            email: User email
            display_name: Display name
            preferences: User preferences

        Returns:
            Created node data
        """
        client = await self._get_client()

        properties = {
            "id": str(user_id),
            "email": email,
            "display_name": display_name or email.split("@")[0],
            "preferences": preferences or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        return await client.create_node("User", properties)

    async def create_poi_node(
        self,
        poi_id: str,
        name: str,
        category: str,
        latitude: float,
        longitude: float,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a POI node in the graph.

        Args:
            poi_id: POI ID
            name: POI name
            category: POI category
            latitude: Latitude
            longitude: Longitude
            properties: Additional properties

        Returns:
            Created node data
        """
        client = await self._get_client()

        node_properties = {
            "id": poi_id,
            "name": name,
            "category": category,
            "latitude": latitude,
            "longitude": longitude,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if properties:
            node_properties.update(properties)

        return await client.create_node("POI", node_properties)

    async def create_category_node(
        self,
        name: str,
        parent_category: str | None = None,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a category node.

        Args:
            name: Category name
            parent_category: Parent category name
            properties: Additional properties

        Returns:
            Created node data
        """
        client = await self._get_client()

        node_properties = {
            "name": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if parent_category:
            node_properties["parent_category"] = parent_category

        if properties:
            node_properties.update(properties)

        return await client.create_node("Category", node_properties)

    async def create_preference_node(
        self,
        preference_id: str,
        user_id: uuid.UUID,
        category: str,
        value: str,
        preference_type: str,
        confidence: float = 1.0,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a preference node.

        Args:
            preference_id: Preference ID
            user_id: User ID
            category: Preference category
            value: Preference value
            preference_type: Type (like/dislike/neutral)
            confidence: Confidence score
            properties: Additional properties

        Returns:
            Created node data
        """
        client = await self._get_client()

        node_properties = {
            "id": preference_id,
            "user_id": str(user_id),
            "category": category,
            "value": value,
            "preference_type": preference_type,
            "confidence": confidence,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if properties:
            node_properties.update(properties)

        node = await client.create_node("Preference", node_properties)

        # Create relationship to user
        await client.create_relationship(
            from_label="User",
            from_property="id",
            from_value=str(user_id),
            to_label="Preference",
            to_property="id",
            to_value=preference_id,
            relationship_type="HAS_PREFERENCE",
        )

        return node

    async def link_user_to_poi(
        self,
        user_id: uuid.UUID,
        poi_id: str,
        relationship_type: str = "VISITED",
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Link user to POI with a relationship.

        Args:
            user_id: User ID
            poi_id: POI ID
            relationship_type: Type of relationship
            properties: Relationship properties

        Returns:
            Relationship data
        """
        client = await self._get_client()

        rel_properties = {
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if properties:
            rel_properties.update(properties)

        return await client.create_relationship(
            from_label="User",
            from_property="id",
            from_value=str(user_id),
            to_label="POI",
            to_property="id",
            to_value=poi_id,
            relationship_type=relationship_type,
            properties=rel_properties,
        )

    async def link_poi_to_category(
        self,
        poi_id: str,
        category_name: str,
    ) -> dict[str, Any] | None:
        """Link POI to category.

        Args:
            poi_id: POI ID
            category_name: Category name

        Returns:
            Relationship data
        """
        client = await self._get_client()

        return await client.create_relationship(
            from_label="POI",
            from_property="id",
            from_value=poi_id,
            to_label="Category",
            to_property="name",
            to_value=category_name,
            relationship_type="IN_CATEGORY",
        )

    async def link_preference_to_category(
        self,
        preference_id: str,
        category_name: str,
    ) -> dict[str, Any] | None:
        """Link preference to category.

        Args:
            preference_id: Preference ID
            category_name: Category name

        Returns:
            Relationship data
        """
        client = await self._get_client()

        return await client.create_relationship(
            from_label="Preference",
            from_property="id",
            from_value=preference_id,
            to_label="Category",
            to_property="name",
            to_value=category_name,
            relationship_type="ABOUT_CATEGORY",
        )

    async def create_itinerary_node(
        self,
        itinerary_id: str,
        user_id: uuid.UUID,
        name: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create an itinerary node.

        Args:
            itinerary_id: Itinerary ID
            user_id: User ID
            name: Itinerary name
            properties: Additional properties

        Returns:
            Created node data
        """
        client = await self._get_client()

        node_properties = {
            "id": itinerary_id,
            "user_id": str(user_id),
            "name": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if properties:
            node_properties.update(properties)

        node = await client.create_node("Itinerary", node_properties)

        # Link to user
        await client.create_relationship(
            from_label="User",
            from_property="id",
            from_value=str(user_id),
            to_label="Itinerary",
            to_property="id",
            to_value=itinerary_id,
            relationship_type="HAS_ITINERARY",
        )

        return node

    async def add_poi_to_itinerary(
        self,
        itinerary_id: str,
        poi_id: str,
        order: int,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Add POI to itinerary.

        Args:
            itinerary_id: Itinerary ID
            poi_id: POI ID
            order: Order in itinerary
            properties: Additional properties

        Returns:
            Relationship data
        """
        client = await self._get_client()

        rel_properties = {
            "order": order,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        if properties:
            rel_properties.update(properties)

        return await client.create_relationship(
            from_label="Itinerary",
            from_property="id",
            from_value=itinerary_id,
            to_label="POI",
            to_property="id",
            to_value=poi_id,
            relationship_type="INCLUDES_POI",
            properties=rel_properties,
        )

    async def find_similar_users(
        self,
        user_id: uuid.UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find users with similar preferences.

        Args:
            user_id: User ID
            limit: Maximum number of results

        Returns:
            List of similar users
        """
        client = await self._get_client()

        query = """
        MATCH (u1:User {id: $user_id})-[:HAS_PREFERENCE]->(p1:Preference)
        MATCH (u2:User)-[:HAS_PREFERENCE]->(p2:Preference)
        WHERE u1.id <> u2.id
        AND p1.category = p2.category
        AND p1.value = p2.value
        WITH u2, count(p2) as shared_preferences
        ORDER BY shared_preferences DESC
        LIMIT $limit
        RETURN u2, shared_preferences
        """

        results = await client.execute_query(
            query,
            {"user_id": str(user_id), "limit": limit},
        )

        return [
            {
                "user": dict(r["u2"]),
                "shared_preferences": r["shared_preferences"],
            }
            for r in results
        ]

    async def get_user_preference_graph(
        self,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Get user's preference subgraph.

        Args:
            user_id: User ID

        Returns:
            Preference graph data
        """
        client = await self._get_client()

        query = """
        MATCH (u:User {id: $user_id})-[:HAS_PREFERENCE]->(p:Preference)
        OPTIONAL MATCH (p)-[:ABOUT_CATEGORY]->(c:Category)
        RETURN u, collect(DISTINCT {preference: p, category: c}) as preferences
        """

        results = await client.execute_query(query, {"user_id": str(user_id)})

        if results:
            return {
                "user": dict(results[0]["u"]),
                "preferences": results[0]["preferences"],
            }

        return {"user": {}, "preferences": []}

    async def cleanup_old_nodes(
        self,
        label: str,
        timestamp_property: str = "created_at",
        days_old: int = 365,
    ) -> int:
        """Clean up old nodes.

        Args:
            label: Node label
            timestamp_property: Property containing timestamp
            days_old: Age in days

        Returns:
            Number of nodes deleted
        """
        client = await self._get_client()

        cutoff = datetime.now(timezone.utc).timestamp() - (days_old * 86400)

        query = f"""
        MATCH (n:{label})
        WHERE datetime({{epoch: n.{timestamp_property}}}).epoch.seconds < $cutoff
        DETACH DELETE n
        RETURN count(n) as deleted
        """

        results = await client.execute_query(query, {"cutoff": cutoff})

        if results:
            return results[0]["deleted"]

        return 0


# Global builder instance
graph_builder = KnowledgeGraphBuilder()
