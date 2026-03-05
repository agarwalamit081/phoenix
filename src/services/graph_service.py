"""Knowledge graph service for travel recommendations."""

import logging
import uuid
from typing import Any

from src.knowledge_graph.graph_builder import graph_builder
from src.knowledge_graph.inference_engine import inference_engine
from src.knowledge_graph.neo4j_client import get_neo4j_client
from src.knowledge_graph.preference_mapper import preference_mapper

logger = logging.getLogger(__name__)


class GraphService:
    """Service for knowledge graph operations."""

    def __init__(self) -> None:
        """Initialize graph service."""
        self._client = None
        self._builder = graph_builder
        self._inference = inference_engine
        self._mapper = preference_mapper
        self._initialized = False

    async def _get_client(self):
        """Get Neo4j client."""
        if self._client is None:
            self._client = await get_neo4j_client()
        return self._client

    async def initialize(self) -> None:
        """Initialize the knowledge graph."""
        if self._initialized:
            return

        try:
            await self._builder.initialize_schema()
            self._initialized = True
            logger.info("Graph service initialized")

        except Exception as e:
            logger.error(f"Failed to initialize graph service: {e}")
            raise

    async def sync_user_to_graph(
        self,
        user_id: uuid.UUID,
        email: str,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        """Sync user to knowledge graph.

        Args:
            user_id: User ID
            email: User email
            display_name: Display name

        Returns:
            Created user node
        """
        await self.initialize()

        # Check if user exists
        client = await self._get_client()
        existing = await client.get_node("User", "id", str(user_id))

        if existing:
            return existing

        # Create new user node
        return await self._builder.create_user_node(
            user_id=user_id,
            email=email,
            display_name=display_name,
        )

    async def sync_preference_to_graph(
        self,
        user_id: uuid.UUID,
        preference_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Sync preference to knowledge graph.

        Args:
            user_id: User ID
            preference_data: Preference data

        Returns:
            Created preference node
        """
        await self.initialize()

        return await self._mapper.sync_preference_to_graph(
            user_id=user_id,
            preference=preference_data,
        )

    async def get_recommendations(
        self,
        user_id: uuid.UUID,
        limit: int = 10,
        method: str = "preference_based",
    ) -> list[dict[str, Any]]:
        """Get POI recommendations for user.

        Args:
            user_id: User ID
            limit: Maximum recommendations
            method: Recommendation method

        Returns:
            List of recommended POIs
        """
        await self.initialize()

        if method == "preference_based":
            return await self._inference.recommend_pois_by_preferences(
                user_id=user_id,
                limit=limit,
            )
        elif method == "collaborative":
            return await self._inference.recommend_pois_collaborative(
                user_id=user_id,
                limit=limit,
            )
        else:
            # Combine both methods
            pref_recs = await self._inference.recommend_pois_by_preferences(
                user_id=user_id,
                limit=limit // 2,
            )
            collab_recs = await self._inference.recommend_pois_collaborative(
                user_id=user_id,
                limit=limit // 2,
            )

            # Merge and deduplicate
            seen = set()
            combined = []
            for rec in pref_recs + collab_recs:
                poi_id = rec["poi"]["id"]
                if poi_id not in seen:
                    seen.add(poi_id)
                    combined.append(rec)

            return combined[:limit]

    async def get_explanation(
        self,
        user_id: uuid.UUID,
        poi_id: str,
    ) -> dict[str, Any]:
        """Get explanation for a recommendation.

        Args:
            user_id: User ID
            poi_id: POI ID

        Returns:
            Explanation with reasons
        """
        await self.initialize()

        return await self._inference.explain_recommendation(
            user_id=user_id,
            poi_id=poi_id,
        )

    async def find_similar_users(
        self,
        user_id: uuid.UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find users with similar preferences.

        Args:
            user_id: User ID
            limit: Maximum results

        Returns:
            List of similar users
        """
        await self.initialize()

        return await self._mapper.find_users_with_similar_preferences(
            user_id=user_id,
            min_shared=2,
            limit=limit,
        )

    async def find_similar_pois(
        self,
        user_id: uuid.UUID,
        poi_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find similar POIs.

        Args:
            user_id: User ID
            poi_id: Reference POI ID
            limit: Maximum results

        Returns:
            List of similar POIs
        """
        await self.initialize()

        return await self._inference.recommend_pois_content_based(
            user_id=user_id,
            poi_id=poi_id,
            limit=limit,
        )

    async def predict_rating(
        self,
        user_id: uuid.UUID,
        poi_id: str,
    ) -> dict[str, Any]:
        """Predict user rating for a POI.

        Args:
            user_id: User ID
            poi_id: POI ID

        Returns:
            Predicted rating
        """
        await self.initialize()

        return await self._inference.predict_preference_score(
            user_id=user_id,
            poi_id=poi_id,
        )

    async def get_travel_pattern(
        self,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Get user's travel pattern.

        Args:
            user_id: User ID

        Returns:
            Travel pattern analysis
        """
        await self.initialize()

        return await self._inference.detect_travel_pattern(
            user_id=user_id,
        )

    async def get_preference_summary(
        self,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Get preference summary.

        Args:
            user_id: User ID

        Returns:
            Preference summary
        """
        await self.initialize()

        return await self._mapper.get_preference_summary(
            user_id=user_id,
        )

    async def get_graph_statistics(self) -> dict[str, Any]:
        """Get knowledge graph statistics.

        Returns:
            Graph statistics
        """
        client = await self._get_client()

        return await client.get_graph_stats()

    async def create_poi_node(
        self,
        poi_id: str,
        name: str,
        category: str,
        latitude: float,
        longitude: float,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a POI node.

        Args:
            poi_id: POI ID
            name: POI name
            category: POI category
            latitude: Latitude
            longitude: Longitude
            properties: Additional properties

        Returns:
            Created node
        """
        await self.initialize()

        # Ensure category exists
        await self._builder.create_category_node(name=category)

        # Create POI node
        node = await self._builder.create_poi_node(
            poi_id=poi_id,
            name=name,
            category=category,
            latitude=latitude,
            longitude=longitude,
            properties=properties,
        )

        # Link to category
        await self._builder.link_poi_to_category(
            poi_id=poi_id,
            category_name=category,
        )

        return node

    async def record_visit(
        self,
        user_id: uuid.UUID,
        poi_id: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Record a user visit to a POI.

        Args:
            user_id: User ID
            poi_id: POI ID
            properties: Additional visit properties

        Returns:
            Created relationship
        """
        await self.initialize()

        return await self._builder.link_user_to_poi(
            user_id=user_id,
            poi_id=poi_id,
            relationship_type="VISITED",
            properties=properties,
        )

    async def get_user_graph(
        self,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Get user's knowledge graph.

        Args:
            user_id: User ID

        Returns:
            User graph data
        """
        await self.initialize()

        return await self._builder.get_user_preference_graph(
            user_id=user_id,
        )

    async def delete_preference(
        self,
        preference_id: str,
    ) -> bool:
        """Delete a preference from graph.

        Args:
            preference_id: Preference ID

        Returns:
            True if deleted
        """
        await self.initialize()

        return await self._mapper.delete_preference_from_graph(
            preference_id=preference_id,
        )

    async def update_preference(
        self,
        preference_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Update a preference in graph.

        Args:
            preference_id: Preference ID
            updates: Properties to update

        Returns:
            Updated node
        """
        await self.initialize()

        return await self._mapper.update_preference_in_graph(
            preference_id=preference_id,
            updates=updates,
        )


# Global instance
graph_service = GraphService()
