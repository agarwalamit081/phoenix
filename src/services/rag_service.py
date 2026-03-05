"""RAG service for retrieval-augmented generation operations."""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ValidationError
from src.rag.generator import (
    RAGGenerator,
    TravelAdviceGenerator,
    POIRecommendationGenerator,
    RoutePlanningGenerator,
    get_rag_generator,
    get_travel_advice_generator,
    get_poi_generator,
    get_route_generator,
)
from src.rag.pipeline import (
    RAGPipeline,
    ConversationalRAGPipeline,
    get_rag_pipeline,
    get_conversational_rag_pipeline,
)
from src.rag.ranker import (
    RAGRanker,
    PersonalizedRAGRanker,
    get_rag_ranker,
    get_personalized_rag_ranker,
)
from src.rag.retriever import (
    HybridRetriever,
    QueryExpander,
    get_hybrid_retriever,
    get_query_expander,
)

logger = logging.getLogger(__name__)


class RAGService:
    """Service for RAG operations."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        """Initialize RAG service.

        Args:
            session: Database session
        """
        self.session = session
        self.pipeline = get_rag_pipeline()
        self.conversational_pipeline = get_conversational_rag_pipeline()
        self.retriever = get_hybrid_retriever()
        self.query_expander = get_query_expander()
        self.ranker = get_rag_ranker()
        self.personalized_ranker = get_personalized_rag_ranker()

        # Generators
        self.general_generator = get_rag_generator()
        self.travel_advice_generator = get_travel_advice_generator()
        self.poi_generator = get_poi_generator()
        self.route_generator = get_route_generator()

        # Conversation storage
        self._conversations: dict[str, dict[str, Any]] = {}

    async def query(
        self,
        user_id: str,
        query_text: str,
        context: dict[str, Any] | None = None,
        top_k: int = 5,
        response_type: str = "general",
    ) -> dict[str, Any]:
        """Execute RAG query.

        Args:
            user_id: User ID
            query_text: Query text
            context: Optional context (location, preferences, etc.)
            top_k: Number of results to retrieve
            response_type: Type of response

        Returns:
            RAG response
        """
        if not query_text or not query_text.strip():
            raise ValidationError(
                message="Query cannot be empty",
                details={"query": query_text},
            )

        # Run pipeline
        result = await self.pipeline.run(
            query=query_text,
            user_id=user_id,
            context=context,
            top_k=top_k,
        )

        # Store query for analytics
        await self._store_query(user_id, query_text, result)

        return result

    async def query_conversation(
        self,
        user_id: str,
        query_text: str,
        conversation_id: str | None = None,
        context: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Execute conversational RAG query.

        Args:
            user_id: User ID
            query_text: Query text
            conversation_id: Optional conversation ID
            context: Optional context
            top_k: Number of results

        Returns:
            RAG response with conversation ID
        """
        if not query_text or not query_text.strip():
            raise ValidationError(
                message="Query cannot be empty",
                details={"query": query_text},
            )

        # Get or create conversation
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        # Run conversational pipeline
        result = await self.conversational_pipeline.run_conversation(
            query=query_text,
            conversation_id=conversation_id,
            user_id=user_id,
            context=context,
            top_k=top_k,
        )

        # Update conversation metadata
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = {
                "id": conversation_id,
                "user_id": user_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "message_count": 0,
            }

        self._conversations[conversation_id]["message_count"] += 1
        self._conversations[conversation_id]["last_activity"] = datetime.now(
            timezone.utc
        ).isoformat()

        return result

    async def stream_query(
        self,
        user_id: str,
        query_text: str,
        context: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> AsyncIterable[str]:
        """Stream RAG query response.

        Args:
            user_id: User ID
            query_text: Query text
            context: Optional context
            top_k: Number of results

        Yields:
            Response chunks
        """
        if not query_text or not query_text.strip():
            raise ValidationError(
                message="Query cannot be empty",
                details={"query": query_text},
            )

        async for chunk in self.pipeline.stream_response(
            query=query_text,
            user_id=user_id,
            context=context,
            top_k=top_k,
        ):
            yield chunk

    async def get_conversation(
        self,
        conversation_id: str,
        user_id: str,
    ) -> dict[str, Any] | None:
        """Get conversation by ID.

        Args:
            conversation_id: Conversation ID
            user_id: User ID

        Returns:
            Conversation data or None
        """
        conversation = self._conversations.get(conversation_id)

        if not conversation or conversation.get("user_id") != user_id:
            return None

        history = self.conversational_pipeline.get_history(conversation_id)

        return {
            **conversation,
            "messages": history,
        }

    async def end_conversation(
        self,
        conversation_id: str,
        user_id: str,
    ) -> bool:
        """End a conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID

        Returns:
            True if ended
        """
        conversation = self._conversations.get(conversation_id)

        if not conversation or conversation.get("user_id") != user_id:
            return False

        self.conversational_pipeline.clear_history(conversation_id)
        del self._conversations[conversation_id]

        return True

    async def provide_feedback(
        self,
        user_id: str,
        query: str,
        selected_doc_ids: list[str],
        skipped_doc_ids: list[str] | None = None,
    ) -> None:
        """Provide feedback on RAG results.

        Args:
            user_id: User ID
            query: Query text
            selected_doc_ids: Document IDs user selected
            skipped_doc_ids: Document IDs user skipped
        """
        await self.personalized_ranker.record_feedback(
            user_id=user_id,
            query=query,
            selected_doc_ids=selected_doc_ids,
            skipped_doc_ids=skipped_doc_ids,
        )

        logger.info(f"Recorded feedback for user {user_id}")

    async def index_documents(
        self,
        documents: list[dict[str, Any]],
        document_type: str = "general",
    ) -> dict[str, Any]:
        """Index documents for retrieval.

        Args:
            documents: Documents to index
            document_type: Type of documents

        Returns:
            Indexing results
        """
        if document_type == "poi":
            await self.retriever.index_from_pois(documents)
        elif document_type == "route":
            await self.retriever.index_from_routes(documents)
        elif document_type == "preference":
            # Requires user_id
            user_id = documents[0].get("user_id") if documents else None
            if user_id:
                await self.retriever.index_from_preferences(documents, user_id)
        else:
            # General indexing
            await self.retriever.vector_retriever.index_batch(documents)

        return {
            "indexed_count": len(documents),
            "document_type": document_type,
        }

    async def expand_query(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        num_expansions: int = 3,
    ) -> list[str]:
        """Expand query for better retrieval.

        Args:
            query: Original query
            context: Optional context
            num_expansions: Number of expansions

        Returns:
            Expanded queries
        """
        return await self.query_expander.expand_query(
            query=query,
            context=context,
            num_expansions=num_expansions,
        )

    async def search_similar(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for similar documents.

        Args:
            query: Search query
            filters: Optional filters
            top_k: Number of results

        Returns:
            Similar documents
        """
        return await self.retriever.vector_search(
            query=query,
            top_k=top_k,
            filters=filters,
        )

    async def get_travel_advice(
        self,
        user_id: str,
        question: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Get travel advice.

        Args:
            user_id: User ID
            question: Question
            context: Optional context

        Returns:
            Travel advice response
        """
        result = await self.pipeline.run(
            query=question,
            user_id=user_id,
            context=context,
            top_k=5,
        )

        # Use specialized generator
        answer = await self.travel_advice_generator.generate(
            query=question,
            context=result.get("context", []),
            user_id=user_id,
            response_type="travel_advice",
        )

        result["answer"] = answer

        return result

    async def get_poi_recommendations(
        self,
        user_id: str,
        request: str,
        location: dict[str, float] | None = None,
        preferences: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Get POI recommendations.

        Args:
            user_id: User ID
            request: Recommendation request
            location: Optional location
            preferences: Optional preferences

        Returns:
            POI recommendations
        """
        context = {
            "location": location,
            "preferences": preferences,
        }

        result = await self.pipeline.run(
            query=request,
            user_id=user_id,
            context=context,
            top_k=8,
        )

        # Use POI generator
        answer = await self.poi_generator.generate(
            query=request,
            context=result.get("context", []),
            user_id=user_id,
            response_type="poi",
        )

        result["answer"] = answer

        return result

    async def get_route_advice(
        self,
        user_id: str,
        request: str,
        route_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Get route planning advice.

        Args:
            user_id: User ID
            request: Route planning request
            route_id: Optional existing route ID
            context: Additional context

        Returns:
            Route advice response
        """
        enhanced_context = context or {}
        if route_id:
            enhanced_context["route_id"] = route_id

        result = await self.pipeline.run(
            query=request,
            user_id=user_id,
            context=enhanced_context,
            top_k=5,
        )

        # Use route generator
        answer = await self.route_generator.generate(
            query=request,
            context=result.get("context", []),
            user_id=user_id,
            response_type="route",
        )

        result["answer"] = answer

        return result

    async def compare_options(
        self,
        user_id: str,
        question: str,
        options: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Compare options.

        Args:
            user_id: User ID
            question: Comparison question
            options: Options to compare

        Returns:
            Comparison response
        """
        # Build context from options
        context_docs = []

        for i, option in enumerate(options):
            context_docs.append({
                "id": f"option_{i}",
                "type": "comparison_option",
                "content": option.get("description", str(option)),
                "metadata": option,
                "source": "user_input",
                "score": 0.5,
            })

        result = await self.pipeline.run(
            query=question,
            user_id=user_id,
            context={"options": options},
            top_k=5,
        )

        # Add options to context
        result["context"] = context_docs + result.get("context", [])

        # Generate comparison
        answer = await self.general_generator.generate(
            query=question,
            context=result["context"],
            user_id=user_id,
            response_type="comparison",
        )

        result["answer"] = answer
        result["options"] = options

        return result

    async def _store_query(
        self,
        user_id: str,
        query_text: str,
        result: dict[str, Any],
    ) -> None:
        """Store query for analytics.

        Args:
            user_id: User ID
            query_text: Query text
            result: Query result
        """
        # In production, would store in database
        logger.debug(f"Stored query for user {user_id}: {query_text[:50]}...")

    async def get_user_stats(
        self,
        user_id: str,
    ) -> dict[str, Any]:
        """Get user RAG statistics.

        Args:
            user_id: User ID

        Returns:
            User statistics
        """
        # Count active conversations
        active_conversations = sum(
            1 for conv in self._conversations.values()
            if conv.get("user_id") == user_id
        )

        return {
            "user_id": user_id,
            "active_conversations": active_conversations,
        }


# Global instance factory
def get_rag_service(session: AsyncSession) -> RAGService:
    """Get RAG service instance.

    Args:
        session: Database session

    Returns:
        RAG service instance
    """
    return RAGService(session)
