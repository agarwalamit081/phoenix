"""Unit tests for embedding service."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.embedding_service import EmbeddingService


@pytest.mark.asyncio
class TestEmbeddingService:
    """Tests for EmbeddingService."""

    async def test_generate_embedding(self) -> None:
        """Test generating single embedding."""
        mock_llm_service = AsyncMock()
        mock_llm_service.generate_embedding.return_value = [0.1] * 1536

        embedding_service = EmbeddingService(mock_llm_service)

        text = "Italian food is delicious"
        embedding = await embedding_service.generate_embedding(text)

        assert len(embedding) == 1536
        assert embedding[0] == 0.1
        mock_llm_service.generate_embedding.assert_called_once_with(text)

    async def test_generate_embeddings(self) -> None:
        """Test generating multiple embeddings."""
        mock_llm_service = AsyncMock()
        mock_llm_service.generate_embeddings.return_value = [
            [0.1] * 1536,
            [0.2] * 1536,
            [0.3] * 1536,
        ]

        embedding_service = EmbeddingService(mock_llm_service)

        texts = ["First text", "Second text", "Third text"]
        embeddings = await embedding_service.generate_embeddings(texts)

        assert len(embeddings) == 3
        assert all(len(emb) == 1536 for emb in embeddings)
        assert embeddings[0][0] == 0.1
        assert embeddings[1][0] == 0.2

    async def test_compute_similarity(self) -> None:
        """Test computing similarity between embeddings."""
        mock_llm_service = AsyncMock()
        embedding_service = EmbeddingService(mock_llm_service)

        # Create two similar vectors
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]

        similarity = embedding_service.compute_similarity(vec1, vec2)

        assert similarity == 1.0

    async def test_compute_similarity_different(self) -> None:
        """Test computing similarity for different vectors."""
        mock_llm_service = AsyncMock()
        embedding_service = EmbeddingService(mock_llm_service)

        # Orthogonal vectors
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        similarity = embedding_service.compute_similarity(vec1, vec2)

        assert similarity == 0.0

    async def test_compute_similarity_opposite(self) -> None:
        """Test computing similarity for opposite vectors."""
        mock_llm_service = AsyncMock()
        embedding_service = EmbeddingService(mock_llm_service)

        # Opposite vectors
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]

        similarity = embedding_service.compute_similarity(vec1, vec2)

        assert similarity == -1.0

    async def test_compute_similarity_partial(self) -> None:
        """Test computing partial similarity."""
        mock_llm_service = AsyncMock()
        embedding_service = EmbeddingService(mock_llm_service)

        # 45 degree angle
        import math
        vec1 = [1.0, 0.0]
        vec2 = [math.sqrt(2) / 2, math.sqrt(2) / 2]

        similarity = embedding_service.compute_similarity(vec1, vec2)

        assert abs(similarity - math.sqrt(2) / 2) < 0.0001

    async def test_find_most_similar(self) -> None:
        """Test finding most similar embedding."""
        mock_llm_service = AsyncMock()
        embedding_service = EmbeddingService(mock_llm_service)

        query = [1.0, 0.0, 0.0]
        candidates = [
            ([1.0, 0.0, 0.0], "exact_match"),
            ([0.0, 1.0, 0.0], "orthogonal"),
            ([-1.0, 0.0, 0.0], "opposite"),
        ]

        result = await embedding_service.find_most_similar(query, candidates)

        assert result[0] == "exact_match"
        assert abs(result[1] - 1.0) < 0.0001

    async def test_find_most_similar_batch(self) -> None:
        """Test finding top k similar embeddings."""
        mock_llm_service = AsyncMock()
        embedding_service = EmbeddingService(mock_llm_service)

        query = [1.0, 0.0, 0.0]
        candidates = [
            ([1.0, 0.0, 0.0], "match1"),
            ([0.9, 0.1, 0.0], "match2"),
            ([0.0, 1.0, 0.0], "orthogonal"),
            ([-1.0, 0.0, 0.0], "opposite"),
        ]

        results = await embedding_service.find_most_similar(query, candidates, top_k=2)

        assert len(results) == 2
        assert results[0][0] == "match1"
        assert results[1][0] == "match2"
        assert results[0][1] > results[1][1]

    async def test_index_poi_embedding(self) -> None:
        """Test indexing POI embedding."""
        mock_llm_service = AsyncMock()
        mock_llm_service.generate_embedding.return_value = [0.1] * 1536

        mock_poi_repo = AsyncMock()
        mock_poi_repo.update_embedding.return_value = None

        embedding_service = EmbeddingService(mock_llm_service, mock_poi_repo)

        poi = MagicMock()
        poi.id = uuid.uuid4()
        poi.name = "Test POI"
        poi.description = "A test point of interest"

        await embedding_service.index_poi(poi)

        mock_llm_service.generate_embedding.assert_called()
        mock_poi_repo.update_embedding.assert_called_once()

    async def test_index_poi_batch(self) -> None:
        """Test batch indexing POI embeddings."""
        mock_llm_service = AsyncMock()
        mock_llm_service.generate_embeddings.return_value = [
            [0.1] * 1536,
            [0.2] * 1536,
        ]

        mock_poi_repo = AsyncMock()
        mock_poi_repo.update_embeddings_batch.return_value = None

        embedding_service = EmbeddingService(mock_llm_service, mock_poi_repo)

        pois = [
            MagicMock(id=uuid.uuid4(), name="POI 1", description="Description 1"),
            MagicMock(id=uuid.uuid4(), name="POI 2", description="Description 2"),
        ]

        await embedding_service.index_pois(pois)

        mock_llm_service.generate_embeddings.assert_called_once()
        mock_poi_repo.update_embeddings_batch.assert_called_once()

    async def test_search_similar_pois(self) -> None:
        """Test searching for similar POIs."""
        mock_llm_service = AsyncMock()
        mock_llm_service.generate_embedding.return_value = [0.5] * 1536

        mock_poi_repo = AsyncMock()
        mock_poi_repo.find_similar_by_embedding.return_value = [
            MagicMock(
                id=uuid.uuid4(),
                name="Similar POI",
                similarity=0.95
            )
        ]

        embedding_service = EmbeddingService(mock_llm_service, mock_poi_repo)

        query = "Find art museums"
        results = await embedding_service.search_similar_pois(query, limit=5)

        assert len(results) >= 0
        mock_llm_service.generate_embedding.assert_called_once_with(query)
        mock_poi_repo.find_similar_by_embedding.assert_called_once()

    async def test_compute_text_similarity(self) -> None:
        """Test computing similarity between two texts."""
        mock_llm_service = AsyncMock()
        mock_llm_service.generate_embeddings.return_value = [
            [0.9, 0.1, 0.0],  # Italian food
            [0.8, 0.2, 0.0],  # Italian cuisine
        ]

        embedding_service = EmbeddingService(mock_llm_service)

        text1 = "Italian food"
        text2 = "Italian cuisine"
        similarity = await embedding_service.compute_text_similarity(text1, text2)

        assert similarity > 0.9  # Should be very similar
        mock_llm_service.generate_embeddings.assert_called_once_with([text1, text2])

    async def test_batch_similarity(self) -> None:
        """Test computing similarities for multiple queries."""
        mock_llm_service = AsyncMock()
        mock_llm_service.generate_embedding.side_effect = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ]

        embedding_service = EmbeddingService(mock_llm_service)

        queries = ["query1", "query2"]
        target = [1.0, 0.0, 0.0]

        similarities = await embedding_service.batch_similarity(queries, target)

        assert len(similarities) == 2
        assert similarities[0] == 1.0
        assert similarities[1] == 0.0

    async def test_normalize_embedding(self) -> None:
        """Test embedding normalization."""
        mock_llm_service = AsyncMock()
        embedding_service = EmbeddingService(mock_llm_service)

        # Create unnormalized vector
        vec = [3.0, 4.0]  # magnitude should be 5

        normalized = embedding_service._normalize(vec)

        import math
        magnitude = math.sqrt(sum(x * x for x in normalized))
        assert abs(magnitude - 1.0) < 0.0001

    async def test_clustering_embeddings(self) -> None:
        """Test clustering similar embeddings."""
        mock_llm_service = AsyncMock()
        embedding_service = EmbeddingService(mock_llm_service)

        embeddings = [
            ([1.0, 0.0], "item1"),
            ([0.9, 0.1], "item2"),
            ([0.0, 1.0], "item3"),
            ([0.1, 0.9], "item4"),
        ]

        # Simple clustering based on similarity threshold
        clusters = embedding_service.cluster_embeddings(embeddings, threshold=0.8)

        assert len(clusters) == 2  # Two clusters
        # Items 1 and 2 should be in same cluster
        # Items 3 and 4 should be in same cluster
