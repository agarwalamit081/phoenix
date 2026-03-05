"""Embedding service for generating and managing text embeddings."""

import hashlib
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.logging import logger
from src.core.exceptions import ExternalServiceError
from src.services.llm_service import LLMService


class _AwaitableFloat(float):
    """Float value that can also be awaited for backward compatibility."""

    def __await__(self):
        async def _value() -> float:
            return float(self)

        return _value().__await__()


class EmbeddingService:
    """Service for generating and caching text embeddings."""

    def __init__(
        self,
        session: AsyncSession | Any | None = None,
        llm_service: LLMService | Any | None = None,
        poi_repo: Any | None = None,
    ) -> None:
        """Initialize the embedding service.

        Args:
            session: Optional database session or legacy llm service argument
            llm_service: Optional LLM service
            poi_repo: Optional POI repository for indexing/search helpers
        """
        # Backward compatibility: old call sites/tests pass llm service as first arg.
        if session is not None and hasattr(session, "generate_embeddings"):
            if llm_service is not None and poi_repo is None:
                poi_repo = llm_service
            llm_service = session
            session = None

        self.session = session
        self.llm_service = llm_service or LLMService()
        self.poi_repo = poi_repo
        self._cache: dict[str, list[float]] = {}

    async def generate_embedding(
        self,
        text: str,
        use_cache: bool = True,
    ) -> list[float]:
        """Generate embedding for a single text."""
        if use_cache:
            cache_key = self._get_cache_key(text)
            if cache_key in self._cache:
                return self._cache[cache_key]

        try:
            if hasattr(self.llm_service, "generate_embedding"):
                embedding = await self.llm_service.generate_embedding(text)
            else:
                embeddings = await self.llm_service.generate_embeddings([text])
                embedding = embeddings[0]

            if use_cache:
                cache_key = self._get_cache_key(text)
                self._cache[cache_key] = embedding

            return embedding

        except ExternalServiceError as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    async def generate_embeddings(
        self,
        texts: list[str],
        use_cache: bool = True,
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        uncached_texts: list[str] = []
        uncached_indices: list[int] = []
        embeddings: list[list[float] | None] = [None] * len(texts)

        if use_cache:
            for i, text in enumerate(texts):
                cache_key = self._get_cache_key(text)
                if cache_key in self._cache:
                    embeddings[i] = self._cache[cache_key]
                else:
                    uncached_texts.append(text)
                    uncached_indices.append(i)
        else:
            uncached_texts = texts
            uncached_indices = list(range(len(texts)))

        if uncached_texts:
            try:
                if hasattr(self.llm_service, "generate_embeddings"):
                    new_embeddings = await self.llm_service.generate_embeddings(uncached_texts)
                else:
                    new_embeddings = []
                    for text in uncached_texts:
                        new_embeddings.append(await self.llm_service.generate_embedding(text))

                for idx, embedding in zip(uncached_indices, new_embeddings):
                    embeddings[idx] = embedding
                    if use_cache:
                        cache_key = self._get_cache_key(texts[idx])
                        self._cache[cache_key] = embedding

            except ExternalServiceError as e:
                logger.error(f"Failed to generate embeddings: {e}")
                raise

        return [emb for emb in embeddings if emb is not None]

    def compute_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
    ) -> _AwaitableFloat:
        """Compute cosine similarity between two embeddings."""
        import math

        if len(embedding1) != len(embedding2):
            raise ValueError("Embeddings must have the same length")

        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        magnitude1 = math.sqrt(sum(a * a for a in embedding1))
        magnitude2 = math.sqrt(sum(a * a for a in embedding2))

        if magnitude1 == 0 or magnitude2 == 0:
            return _AwaitableFloat(0.0)

        return _AwaitableFloat(dot_product / (magnitude1 * magnitude2))

    async def find_similar(
        self,
        query_embedding: list[float],
        candidate_embeddings: list[list[float]],
        threshold: float = 0.7,
        top_k: int | None = None,
    ) -> list[tuple[int, float]]:
        """Find similar embeddings from candidates."""
        similarities = []

        for i, candidate in enumerate(candidate_embeddings):
            similarity = float(await self.compute_similarity(query_embedding, candidate))
            if similarity >= threshold:
                similarities.append((i, similarity))

        similarities.sort(key=lambda x: x[1], reverse=True)

        if top_k:
            similarities = similarities[:top_k]

        return similarities

    async def find_most_similar(
        self,
        query_embedding: list[float],
        candidates: list[tuple[list[float], Any]],
        top_k: int | None = None,
    ) -> Any:
        """Backward-compatible helper to find most similar candidates."""
        scored: list[tuple[Any, float]] = []
        for embedding, payload in candidates:
            similarity = float(await self.compute_similarity(query_embedding, embedding))
            scored.append((payload, similarity))

        scored.sort(key=lambda x: x[1], reverse=True)
        if top_k is not None:
            return scored[:top_k]
        return scored[0] if scored else (None, 0.0)

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        text_normalized = text.lower().strip()
        return hashlib.md5(text_normalized.encode()).hexdigest()

    def clear_cache(self) -> None:
        """Clear the in-memory embedding cache."""
        self._cache.clear()
        logger.info("Embedding cache cleared")

    def get_cache_size(self) -> int:
        """Get the number of cached embeddings."""
        return len(self._cache)

    async def embed_user_preference(
        self,
        category: str,
        value: str,
        preference_type: str,
    ) -> list[float]:
        """Generate an embedding for a user preference."""
        text = f"{preference_type} {category}: {value}"
        return await self.generate_embedding(text)

    async def embed_poi(
        self,
        name: str,
        description: str | None,
        categories: list[str],
    ) -> list[float]:
        """Generate an embedding for a POI."""
        parts = [name]
        if description:
            parts.append(description)
        if categories:
            parts.append(" ".join(categories))

        text = ". ".join(parts)
        return await self.generate_embedding(text)

    async def batch_embed_pois(
        self,
        pois: list[dict[str, Any]],
    ) -> list[list[float]]:
        """Generate embeddings for multiple POIs in batch."""
        texts = []
        for poi in pois:
            parts = [poi.get("name", "")]
            if poi.get("description"):
                parts.append(poi["description"])
            if poi.get("categories"):
                parts.append(" ".join(poi["categories"]))
            texts.append(". ".join(parts))

        return await self.generate_embeddings(texts)

    async def compute_text_similarity(self, text1: str, text2: str) -> float:
        """Compute similarity between two texts."""
        embeddings = await self.generate_embeddings([text1, text2])
        return float(self.compute_similarity(embeddings[0], embeddings[1]))

    async def batch_similarity(
        self,
        queries: list[str],
        target_embedding: list[float],
    ) -> list[float]:
        """Compute similarities between query texts and a target embedding."""
        similarities = []
        for query in queries:
            query_embedding = await self.generate_embedding(query)
            similarities.append(float(self.compute_similarity(query_embedding, target_embedding)))
        return similarities

    def _normalize(self, vector: list[float]) -> list[float]:
        """Normalize a vector to unit length."""
        import math

        norm = math.sqrt(sum(x * x for x in vector))
        if norm == 0:
            return vector
        return [x / norm for x in vector]

    def cluster_embeddings(
        self,
        embeddings: list[tuple[list[float], Any]],
        threshold: float = 0.8,
    ) -> list[list[Any]]:
        """Simple threshold-based clustering for embeddings."""
        clusters: list[list[tuple[list[float], Any]]] = []

        for embedding, payload in embeddings:
            placed = False
            for cluster in clusters:
                centroid = cluster[0][0]
                if float(self.compute_similarity(embedding, centroid)) >= threshold:
                    cluster.append((embedding, payload))
                    placed = True
                    break
            if not placed:
                clusters.append([(embedding, payload)])

        return [[payload for _, payload in cluster] for cluster in clusters]

    async def index_poi(self, poi: Any) -> list[float]:
        """Generate and optionally persist a POI embedding."""
        text = ". ".join(part for part in [getattr(poi, "name", ""), getattr(poi, "description", "")] if part)
        embedding = await self.generate_embedding(text)

        if self.poi_repo and hasattr(self.poi_repo, "update_embedding"):
            await self.poi_repo.update_embedding(poi.id, embedding)

        return embedding

    async def index_pois(self, pois: list[Any]) -> list[list[float]]:
        """Generate and optionally persist embeddings for many POIs."""
        texts = [
            ". ".join(
                part
                for part in [str(getattr(poi, "name", "")), str(getattr(poi, "description", ""))]
                if part
            )
            for poi in pois
        ]
        embeddings = await self.generate_embeddings(texts)

        if self.poi_repo and hasattr(self.poi_repo, "update_embeddings_batch"):
            poi_ids = [poi.id for poi in pois]
            await self.poi_repo.update_embeddings_batch(poi_ids, embeddings)

        return embeddings

    async def search_similar_pois(self, query: str, limit: int = 10) -> list[Any]:
        """Search similar POIs via repository if available."""
        if not self.poi_repo or not hasattr(self.poi_repo, "find_similar_by_embedding"):
            return []

        query_embedding = await self.generate_embedding(query)
        return await self.poi_repo.find_similar_by_embedding(query_embedding, limit=limit)
