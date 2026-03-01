"""Embedding service for generating and managing text embeddings."""

import hashlib
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.logging import logger
from src.core.exceptions import ExternalServiceError
from src.services.llm_service import LLMService


class EmbeddingService:
    """Service for generating and caching text embeddings."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the embedding service.

        Args:
            session: Database session
        """
        self.session = session
        self.llm_service = LLMService()
        self._cache: dict[str, list[float]] = {}

    async def generate_embedding(
        self,
        text: str,
        use_cache: bool = True,
    ) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed
            use_cache: Whether to use in-memory cache

        Returns:
            Embedding vector

        Raises:
            ExternalServiceError: If embedding generation fails
        """
        if use_cache:
            cache_key = self._get_cache_key(text)
            if cache_key in self._cache:
                return self._cache[cache_key]

        try:
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
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            use_cache: Whether to use in-memory cache

        Returns:
            List of embedding vectors

        Raises:
            ExternalServiceError: If embedding generation fails
        """
        if not texts:
            return []

        # Check cache for uncached texts
        uncached_texts = []
        uncached_indices = []
        embeddings = [None] * len(texts)

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

        # Generate embeddings for uncached texts
        if uncached_texts:
            try:
                new_embeddings = await self.llm_service.generate_embeddings(
                    uncached_texts,
                )

                for idx, embedding in zip(uncached_indices, new_embeddings):
                    embeddings[idx] = embedding
                    if use_cache:
                        cache_key = self._get_cache_key(uncached_texts[uncached_indices.index(idx)])
                        self._cache[cache_key] = embedding

            except ExternalServiceError as e:
                logger.error(f"Failed to generate embeddings: {e}")
                raise

        return embeddings

    async def compute_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
    ) -> float:
        """Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Similarity score between 0 and 1
        """
        import math

        if len(embedding1) != len(embedding2):
            raise ValueError("Embeddings must have the same length")

        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
        magnitude1 = math.sqrt(sum(a * a for a in embedding1))
        magnitude2 = math.sqrt(sum(a * a for a in embedding2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    async def find_similar(
        self,
        query_embedding: list[float],
        candidate_embeddings: list[list[float]],
        threshold: float = 0.7,
        top_k: int | None = None,
    ) -> list[tuple[int, float]]:
        """Find similar embeddings from candidates.

        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: List of candidate embeddings
            threshold: Minimum similarity threshold
            top_k: Maximum number of results to return

        Returns:
            List of (index, similarity) tuples sorted by similarity
        """
        similarities = []

        for i, candidate in enumerate(candidate_embeddings):
            similarity = await self.compute_similarity(query_embedding, candidate)
            if similarity >= threshold:
                similarities.append((i, similarity))

        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)

        if top_k:
            similarities = similarities[:top_k]

        return similarities

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text.

        Args:
            text: Text to generate key for

        Returns:
            Cache key hash
        """
        text_normalized = text.lower().strip()
        return hashlib.md5(text_normalized.encode()).hexdigest()

    def clear_cache(self) -> None:
        """Clear the in-memory embedding cache."""
        self._cache.clear()
        logger.info("Embedding cache cleared")

    def get_cache_size(self) -> int:
        """Get the number of cached embeddings.

        Returns:
            Number of cached embeddings
        """
        return len(self._cache)

    async def embed_user_preference(
        self,
        category: str,
        value: str,
        preference_type: str,
    ) -> list[float]:
        """Generate an embedding for a user preference.

        Args:
            category: Preference category
            value: Preference value
            preference_type: Type of preference (like/dislike/neutral)

        Returns:
            Embedding vector
        """
        # Create a descriptive text that captures the preference
        text = f"{preference_type} {category}: {value}"

        return await self.generate_embedding(text)

    async def embed_poi(
        self,
        name: str,
        description: str | None,
        categories: list[str],
    ) -> list[float]:
        """Generate an embedding for a POI.

        Args:
            name: POI name
            description: POI description
            categories: POI categories

        Returns:
            Embedding vector
        """
        # Combine all available information
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
        """Generate embeddings for multiple POIs in batch.

        Args:
            pois: List of POI dictionaries with name, description, categories

        Returns:
            List of embedding vectors
        """
        texts = []
        for poi in pois:
            parts = [poi.get("name", "")]
            if poi.get("description"):
                parts.append(poi["description"])
            if poi.get("categories"):
                parts.append(" ".join(poi["categories"]))
            texts.append(". ".join(parts))

        return await self.generate_embeddings(texts)
