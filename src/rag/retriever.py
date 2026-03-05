"""RAG retriever for hybrid vector and knowledge graph retrieval."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import numpy as np

from src.services.embedding_service import EmbeddingService
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class VectorRetriever:
    """Retrieve documents using vector similarity search."""

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        """Initialize vector retriever.

        Args:
            embedding_service: Optional embedding service
        """
        # Default to an in-memory embedding service for unit/runtime convenience.
        self.embedding_service = embedding_service or EmbeddingService()
        self._documents: dict[str, dict[str, Any]] = {}
        self._embeddings: dict[str, list[float]] = {}

    async def index_document(
        self,
        doc_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Index a document for retrieval.

        Args:
            doc_id: Document ID
            content: Document content
            metadata: Optional metadata
        """
        # Generate embedding
        if not self.embedding_service:
            logger.warning("No embedding service configured")
            return

        embedding = await self.embedding_service.generate_embedding(content)

        if not embedding:
            logger.error(f"Failed to generate embedding for document {doc_id}")
            return

        # Store document and embedding
        self._documents[doc_id] = {
            "id": doc_id,
            "content": content,
            "metadata": metadata or {},
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }

        self._embeddings[doc_id] = embedding

        logger.debug(f"Indexed document {doc_id}")

    async def index_batch(
        self,
        documents: list[dict[str, Any]],
    ) -> None:
        """Index multiple documents.

        Args:
            documents: List of documents with id, content, metadata
        """
        for doc in documents:
            await self.index_document(
                doc_id=doc["id"],
                content=doc["content"],
                metadata=doc.get("metadata"),
            )

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        score_threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Search for similar documents.

        Args:
            query: Search query
            top_k: Number of results
            filters: Optional metadata filters
            score_threshold: Minimum similarity score

        Returns:
            List of relevant documents with scores
        """
        if not self._embeddings:
            return []

        if not self.embedding_service:
            logger.warning("No embedding service configured for search")
            return []

        # Generate query embedding
        query_embedding = await self.embedding_service.generate_embedding(query)

        if not query_embedding:
            return []

        # Calculate similarities
        results = []

        for doc_id, doc_embedding in self._embeddings.items():
            # Apply filters
            if filters:
                doc = self._documents.get(doc_id)
                if not doc:
                    continue

                metadata = doc.get("metadata", {})

                # Check all filters
                filter_match = True
                for key, value in filters.items():
                    if metadata.get(key) != value:
                        filter_match = False
                        break

                if not filter_match:
                    continue

            # Calculate similarity
            similarity = await self.embedding_service.compute_similarity(
                query_embedding,
                doc_embedding,
            )

            if similarity >= score_threshold:
                results.append({
                    "id": doc_id,
                    "score": similarity,
                    "document": self._documents[doc_id],
                })

        # Sort by score and return top-k
        results.sort(key=lambda r: r["score"], reverse=True)

        return results[:top_k]

    async def delete(self, doc_id: str) -> bool:
        """Delete a document from index.

        Args:
            doc_id: Document ID

        Returns:
            True if deleted
        """
        if doc_id in self._documents:
            del self._documents[doc_id]

        if doc_id in self._embeddings:
            del self._embeddings[doc_id]
            return True

        return False

    def get_stats(self) -> dict[str, Any]:
        """Get retriever statistics.

        Returns:
            Statistics
        """
        return {
            "total_documents": len(self._documents),
            "total_embeddings": len(self._embeddings),
        }


class KnowledgeGraphRetriever:
    """Retrieve information from knowledge graph."""

    def __init__(
        self,
        graph_service: Any | None = None,
    ) -> None:
        """Initialize knowledge graph retriever.

        Args:
            graph_service: Optional graph service
        """
        self.graph_service = graph_service

    async def search(
        self,
        query: str,
        user_id: str | None = None,
        context: dict[str, Any] | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Search knowledge graph.

        Args:
            query: Search query
            user_id: Optional user ID
            context: Optional context
            top_k: Number of results

        Returns:
            List of relevant graph results
        """
        if not self.graph_service:
            return []

        try:
            # Get user-specific recommendations
            if user_id:
                recommendations = await self.graph_service.get_recommendations(
                    user_id=user_id,
                    limit=top_k,
                )

                results = []
                for rec in recommendations:
                    results.append({
                        "id": rec.get("poi_id", rec.get("id")),
                        "type": "knowledge_graph_recommendation",
                        "content": rec.get("description", ""),
                        "metadata": rec,
                        "source": "knowledge_graph",
                        "score": rec.get("score", 0.5),
                    })

                return results[:top_k]

        except Exception as e:
            logger.error(f"Knowledge graph search failed: {e}")

        return []

    async def get_related_entities(
        self,
        entity_id: str,
        relation_type: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get related entities from graph.

        Args:
            entity_id: Entity ID
            relation_type: Optional relation type filter
            limit: Number of results

        Returns:
            Related entities
        """
        if not self.graph_service:
            return []

        try:
            # This would query the knowledge graph
            # For now, return empty
            return []

        except Exception as e:
            logger.error(f"Failed to get related entities: {e}")
            return []


class HybridRetriever:
    """Hybrid retriever combining vector and knowledge graph search."""

    def __init__(
        self,
        vector_retriever: VectorRetriever | None = None,
        kg_retriever: KnowledgeGraphRetriever | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        """Initialize hybrid retriever.

        Args:
            vector_retriever: Optional vector retriever
            kg_retriever: Optional knowledge graph retriever
            embedding_service: Optional embedding service
        """
        self.vector_retriever = vector_retriever or VectorRetriever(embedding_service)
        self.kg_retriever = kg_retriever or KnowledgeGraphRetriever()
        self.embedding_service = embedding_service  # May be None

    async def vector_search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Vector similarity search.

        Args:
            query: Search query
            top_k: Number of results
            filters: Optional filters

        Returns:
            Search results
        """
        return await self.vector_retriever.search(
            query=query,
            top_k=top_k,
            filters=filters,
        )

    async def graph_search(
        self,
        query: str,
        user_id: str | None = None,
        context: dict[str, Any] | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Knowledge graph search.

        Args:
            query: Search query
            user_id: Optional user ID
            context: Optional context
            top_k: Number of results

        Returns:
            Graph results
        """
        return await self.kg_retriever.search(
            query=query,
            user_id=user_id,
            context=context,
            top_k=top_k,
        )

    async def hybrid_search(
        self,
        query: str,
        user_id: str | None = None,
        context: dict[str, Any] | None = None,
        top_k: int = 10,
        vector_weight: float = 0.6,
        graph_weight: float = 0.4,
    ) -> list[dict[str, Any]]:
        """Hybrid search combining both methods.

        Args:
            query: Search query
            user_id: Optional user ID
            context: Optional context
            top_k: Number of results
            vector_weight: Weight for vector results
            graph_weight: Weight for graph results

        Returns:
            Combined results
        """
        # Run both searches in parallel
        vector_results, graph_results = await asyncio.gather(
            self.vector_search(query, top_k * 2),
            self.graph_search(query, user_id, context, top_k * 2),
            return_exceptions=True,
        )

        # Handle exceptions
        if isinstance(vector_results, Exception):
            logger.error(f"Vector search failed: {vector_results}")
            vector_results = []

        if isinstance(graph_results, Exception):
            logger.error(f"Graph search failed: {graph_results}")
            graph_results = []

        # Combine and re-score
        combined = []

        # Add vector results
        for result in vector_results:
            combined.append({
                **result,
                "combined_score": result.get("score", 0.0) * vector_weight,
                "source": "vector",
            })

        # Add graph results
        for result in graph_results:
            # Check if already exists
            existing = next(
                (c for c in combined if c.get("id") == result.get("id")),
                None,
            )

            if existing:
                # Combine scores
                existing["combined_score"] += result.get("score", 0.0) * graph_weight
                existing["source"] = "hybrid"
            else:
                combined.append({
                    **result,
                    "combined_score": result.get("score", 0.0) * graph_weight,
                    "source": "graph",
                })

        # Sort by combined score
        combined.sort(key=lambda r: r.get("combined_score", 0.0), reverse=True)

        return combined[:top_k]

    async def index_from_pois(
        self,
        pois: list[dict[str, Any]],
    ) -> None:
        """Index POIs for retrieval.

        Args:
            pois: List of POIs
        """
        for poi in pois:
            doc_id = poi.get("id", str(id(poi)))

            # Build content
            content_parts = []

            if poi.get("name"):
                content_parts.append(f"Name: {poi['name']}")

            if poi.get("description"):
                content_parts.append(f"Description: {poi['description']}")

            if poi.get("category"):
                content_parts.append(f"Category: {poi['category']}")

            if poi.get("summary"):
                content_parts.append(f"Summary: {poi['summary']}")

            content = " | ".join(content_parts)

            # Build metadata
            metadata = {
                "type": "poi",
                "name": poi.get("name"),
                "category": poi.get("category"),
                "latitude": poi.get("latitude"),
                "longitude": poi.get("longitude"),
                "rating": poi.get("rating"),
            }

            await self.vector_retriever.index_document(
                doc_id=doc_id,
                content=content,
                metadata=metadata,
            )

        logger.info(f"Indexed {len(pois)} POIs")

    async def index_from_routes(
        self,
        routes: list[dict[str, Any]],
    ) -> None:
        """Index routes for retrieval.

        Args:
            routes: List of routes
        """
        for route in routes:
            doc_id = route.get("id", str(id(route)))

            # Build content
            plan = route.get("plan", {})
            pois = plan.get("pois", [])

            content_parts = [
                f"Route with {len(pois)} points of interest",
            ]

            for poi in pois[:5]:  # First 5 POIs
                if poi.get("name"):
                    content_parts.append(f"- {poi['name']}: {poi.get('category', 'attraction')}")

            content = "\n".join(content_parts)

            # Build metadata
            metadata = {
                "type": "route",
                "total_pois": len(pois),
                "estimated_distance_km": plan.get("estimated_distance_km"),
                "estimated_duration_minutes": plan.get("estimated_duration_minutes"),
            }

            await self.vector_retriever.index_document(
                doc_id=doc_id,
                content=content,
                metadata=metadata,
            )

        logger.info(f"Indexed {len(routes)} routes")

    async def index_from_preferences(
        self,
        preferences: list[dict[str, Any]],
        user_id: str,
    ) -> None:
        """Index user preferences.

        Args:
            preferences: List of preferences
            user_id: User ID
        """
        for i, pref in enumerate(preferences):
            doc_id = f"{user_id}_pref_{i}"

            content = f"User preference: {pref.get('preference_type')} {pref.get('category')} - {pref.get('value')}"

            metadata = {
                "type": "preference",
                "user_id": user_id,
                "preference_type": pref.get("preference_type"),
                "category": pref.get("category"),
                "value": pref.get("value"),
            }

            await self.vector_retriever.index_document(
                doc_id=doc_id,
                content=content,
                metadata=metadata,
            )

        logger.info(f"Indexed {len(preferences)} preferences for user {user_id}")


class QueryExpander:
    """Expand queries for better retrieval."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
    ) -> None:
        """Initialize query expander.

        Args:
            llm_service: Optional LLM service
        """
        self.llm_service = llm_service or LLMService()

    async def expand_query(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        num_expansions: int = 3,
    ) -> list[str]:
        """Generate query expansions.

        Args:
            query: Original query
            context: Optional context
            num_expansions: Number of expansions

        Returns:
            List of expanded queries
        """
        expansions = [query]

        try:
            # Build prompt
            context_str = ""
            if context:
                if context.get("location"):
                    context_str += f"Location: {context['location']}\n"
                if context.get("preferences"):
                    context_str += f"Preferences: {context['preferences']}\n"

            prompt = f"""Generate {num_expansions} alternative search queries that would help find relevant information for the user's request.

{context_str}

Original query: {query}

Generate {num_expansions} paraphrased or expanded versions of this query that would help with information retrieval. Return only the queries, one per line, without numbering."""

            response = await self.llm_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a search query optimizer. Generate useful query variations.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.8,
                max_tokens=200,
            )

            content = response.get("content", "")

            # Parse expansions
            for line in content.strip().split("\n"):
                line = line.strip()
                if line and line.lower() != query.lower():
                    expansions.append(line)

        except Exception as e:
            logger.error(f"Query expansion failed: {e}")

        return expansions[:num_expansions + 1]


# Global instances
vector_retriever = VectorRetriever()
kg_retriever = KnowledgeGraphRetriever()
hybrid_retriever = HybridRetriever(vector_retriever, kg_retriever)
query_expander = QueryExpander()


def get_vector_retriever() -> VectorRetriever:
    """Get vector retriever instance.

    Returns:
        Vector retriever instance
    """
    return vector_retriever


def get_hybrid_retriever() -> HybridRetriever:
    """Get hybrid retriever instance.

    Returns:
        Hybrid retriever instance
    """
    return hybrid_retriever


def get_query_expander() -> QueryExpander:
    """Get query expander instance.

    Returns:
        Query expander instance
    """
    return query_expander
