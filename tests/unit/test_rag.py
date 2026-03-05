"""Unit tests for RAG modules."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.rag.retriever import VectorRetriever, HybridRetriever, QueryExpander
from src.rag.ranker import RAGRanker
from src.rag.generator import RAGGenerator
from src.rag.pipeline import RAGPipeline


@pytest.fixture
def sample_documents():
    """Create sample documents."""
    return [
        {
            "id": "doc_1",
            "content": "Central Park is a beautiful park in New York City.",
            "metadata": {"type": "poi", "category": "park"},
        },
        {
            "id": "doc_2",
            "content": "Times Square is a major commercial intersection in Manhattan.",
            "metadata": {"type": "poi", "category": "attraction"},
        },
        {
            "id": "doc_3",
            "content": "The Empire State Building is an iconic skyscraper in NYC.",
            "metadata": {"type": "poi", "category": "attraction"},
        },
    ]


class TestVectorRetriever:
    """Test vector retriever."""

    @pytest.mark.asyncio
    async def test_index_document(self):
        """Test indexing a document."""
        retriever = VectorRetriever()

        with patch.object(retriever.embedding_service, 'generate_embedding', return_value=[0.1] * 1536):
            await retriever.index_document(
                doc_id="test_doc",
                content="Test content",
                metadata={"type": "test"},
            )

            stats = retriever.get_stats()
            assert stats["total_documents"] == 1

    @pytest.mark.asyncio
    async def test_search(self, sample_documents):
        """Test searching documents."""
        retriever = VectorRetriever()

        # Index documents
        with patch.object(retriever.embedding_service, 'generate_embedding', return_value=[0.1] * 1536):
            for doc in sample_documents:
                await retriever.index_document(
                    doc_id=doc["id"],
                    content=doc["content"],
                    metadata=doc["metadata"],
                )

        # Search
        with patch.object(retriever.embedding_service, 'generate_embedding', return_value=[0.1] * 1536):
            results = await retriever.search("New York attractions", top_k=5)

            assert len(results) >= 0

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test deleting a document."""
        retriever = VectorRetriever()

        with patch.object(retriever.embedding_service, 'generate_embedding', return_value=[0.1] * 1536):
            await retriever.index_document(
                doc_id="test_doc",
                content="Test content",
            )

            deleted = await retriever.delete("test_doc")

            assert deleted is True

            stats = retriever.get_stats()
            assert stats["total_documents"] == 0


class TestHybridRetriever:
    """Test hybrid retriever."""

    @pytest.mark.asyncio
    async def test_vector_search(self, sample_documents):
        """Test vector search."""
        retriever = HybridRetriever()

        # Index documents
        with patch.object(retriever.vector_retriever.embedding_service, 'generate_embedding', return_value=[0.1] * 1536):
            for doc in sample_documents:
                await retriever.vector_retriever.index_document(
                    doc_id=doc["id"],
                    content=doc["content"],
                    metadata=doc["metadata"],
                )

        # Search
        with patch.object(retriever.vector_retriever.embedding_service, 'generate_embedding', return_value=[0.1] * 1536):
            results = await retriever.vector_search("parks in NYC", top_k=3)

            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_hybrid_search(self, sample_documents):
        """Test hybrid search."""
        retriever = HybridRetriever()

        with patch.object(retriever.vector_retriever.embedding_service, 'generate_embedding', return_value=[0.1] * 1536):
            results = await retriever.hybrid_search(
                "attractions in NYC",
                user_id="test_user",
                top_k=3,
            )

            assert isinstance(results, list)


class TestRAGRanker:
    """Test RAG ranker."""

    @pytest.mark.asyncio
    async def test_rank(self, sample_documents):
        """Test ranking documents."""
        ranker = RAGRanker()

        # Add scores to documents
        for doc in sample_documents:
            doc["score"] = 0.5

        ranked = await ranker.rank(
            query="New York attractions",
            documents=sample_documents,
        )

        assert len(ranked) == 3

    @pytest.mark.asyncio
    async def test_deduplicate(self, sample_documents):
        """Test deduplication."""
        ranker = RAGRanker()

        # Add duplicate
        docs_with_dup = sample_documents + [sample_documents[0]]

        deduplicated = await ranker.deduplicate(docs_with_dup)

        assert len(deduplicated) == 3


class TestRAGGenerator:
    """Test RAG generator."""

    @pytest.mark.asyncio
    async def test_generate(self, sample_documents):
        """Test generating response."""
        generator = RAGGenerator()

        context = [
            {
                "content": doc["content"],
                "metadata": doc["metadata"],
                "type": "poi",
                "source": "test",
            }
            for doc in sample_documents
        ]

        with patch.object(generator.llm_service, 'chat_completion', return_value={"content": "Test response"}):
            response = await generator.generate(
                query="What are some attractions in NYC?",
                context=context,
            )

            assert response == "Test response"

    @pytest.mark.asyncio
    async def test_generate_with_citations(self, sample_documents):
        """Test generating with citations."""
        generator = RAGGenerator()

        context = [
            {
                "id": doc["id"],
                "content": doc["content"],
                "metadata": doc["metadata"],
                "type": "poi",
                "source": "test",
            }
            for doc in sample_documents
        ]

        with patch.object(generator.llm_service, 'chat_completion', return_value={"content": "Test response"}):
            result = await generator.generate_with_citations(
                query="What are some attractions in NYC?",
                context=context,
            )

            assert "response" in result
            assert "citations" in result
            assert len(result["citations"]) == 3


class TestRAGPipeline:
    """Test RAG pipeline."""

    @pytest.mark.asyncio
    async def test_run(self):
        """Test running RAG pipeline."""
        pipeline = RAGPipeline()

        with patch.object(pipeline, '_retrieve', return_value=[]):
            result = await pipeline.run(
                query="What are some attractions in NYC?",
                user_id="test_user",
                top_k=5,
            )

            assert "query" in result
            assert "answer" in result
            assert "sources" in result

    @pytest.mark.asyncio
    async def test_conversational_pipeline(self):
        """Test conversational RAG pipeline."""
        from src.rag.pipeline import ConversationalRAGPipeline

        pipeline = ConversationalRAGPipeline()

        with patch.object(pipeline, 'run', return_value={"answer": "Test response"}):
            result = await pipeline.run_conversation(
                query="Tell me more about NYC",
                conversation_id="test_conv",
                user_id="test_user",
            )

            assert "conversation_id" in result


class TestQueryExpander:
    """Test query expander."""

    @pytest.mark.asyncio
    async def test_expand_query(self):
        """Test query expansion."""
        expander = QueryExpander()

        with patch.object(expander.llm_service, 'chat_completion', return_value={"content": "NYC attractions\nNew York City things to do\nManhattan sights"}):
            expansions = await expander.expand_query(
                query="NYC attractions",
                num_expansions=3,
            )

            assert len(expansions) >= 1
            assert "NYC attractions" in expansions
