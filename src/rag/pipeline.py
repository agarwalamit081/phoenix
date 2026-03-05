"""RAG pipeline for retrieval-augmented generation."""

import asyncio
import logging
from collections.abc import AsyncIterable
from datetime import datetime, timezone
from typing import Any

from src.config.settings import settings
from src.core.exceptions import ValidationError
from src.services.llm_service import LLMService
from src.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class RAGPipeline:
    """RAG pipeline for context-aware responses."""

    def __init__(
        self,
        retriever: Any | None = None,
        ranker: Any | None = None,
        generator: Any | None = None,
        embedding_service: EmbeddingService | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        """Initialize RAG pipeline.

        Args:
            retriever: Optional retriever component
            ranker: Optional ranker component
            generator: Optional generator component
            embedding_service: Optional embedding service
            llm_service: Optional LLM service
        """
        self.retriever = retriever
        self.ranker = ranker
        self.generator = generator
        self.embedding_service = embedding_service or EmbeddingService()
        self.llm_service = llm_service or LLMService()

    async def run(
        self,
        query: str,
        user_id: str | None = None,
        context: dict[str, Any] | None = None,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run the RAG pipeline.

        Args:
            query: User query
            user_id: Optional user ID for personalization
            context: Optional context (location, preferences, etc.)
            top_k: Number of results to retrieve
            filters: Optional retrieval filters

        Returns:
            RAG response with context and answer
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Step 1: Retrieve relevant documents
            retrieved = await self._retrieve(
                query,
                user_id,
                context,
                top_k * 3,  # Retrieve more for reranking
                filters,
            )

            if not retrieved:
                logger.warning("No documents retrieved for query")
                return {
                    "query": query,
                    "answer": await self._generate_fallback_response(query, context),
                    "sources": [],
                    "context": [],
                    "metadata": {
                        "retrieval_count": 0,
                        "used_knowledge_graph": False,
                        "processing_time_ms": (
                            datetime.now(timezone.utc) - start_time
                        ).total_seconds() * 1000,
                    },
                }

            # Step 2: Rank retrieved documents
            ranked = await self._rank(query, retrieved, user_id, context)

            # Select top-k
            selected = ranked[:top_k]

            # Step 3: Build context
            context_docs = await self._build_context(selected, context)

            # Step 4: Generate answer
            answer = await self._generate(query, context_docs, user_id)

            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            return {
                "query": query,
                "answer": answer,
                "sources": [
                    {
                        "id": doc.get("id"),
                        "type": doc.get("type", "unknown"),
                        "title": doc.get("title", doc.get("name", "")),
                        "score": doc.get("score", 0.0),
                    }
                    for doc in selected
                ],
                "context": context_docs,
                "metadata": {
                    "retrieval_count": len(retrieved),
                    "used_knowledge_graph": any(
                        doc.get("source") == "knowledge_graph"
                        for doc in selected
                    ),
                    "processing_time_ms": round(processing_time, 2),
                },
            }

        except Exception as e:
            logger.error(f"RAG pipeline error: {e}")
            raise

    async def _retrieve(
        self,
        query: str,
        user_id: str | None,
        context: dict[str, Any] | None,
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant documents.

        Args:
            query: User query
            user_id: Optional user ID
            context: Optional context
            top_k: Number of results
            filters: Optional filters

        Returns:
            Retrieved documents
        """
        results = []

        # Vector search if retriever available
        if self.retriever:
            try:
                vector_results = await self.retriever.vector_search(
                    query=query,
                    top_k=top_k,
                    filters=filters,
                )
                results.extend(vector_results)
            except Exception as e:
                logger.error(f"Vector search failed: {e}")

        # Knowledge graph search if retriever available
        if self.retriever and hasattr(self.retriever, "graph_search"):
            try:
                graph_results = await self.retriever.graph_search(
                    query=query,
                    user_id=user_id,
                    context=context,
                    top_k=top_k // 2,
                )
                results.extend(graph_results)
            except Exception as e:
                logger.error(f"Graph search failed: {e}")

        # POI search if location in context
        if context and context.get("location"):
            try:
                from src.poi.discovery import poi_discovery

                location = context["location"]
                category = context.get("poi_category")

                poi_results = await poi_discovery.search_nearby(
                    location=location,
                    query=query if not category else category,
                    radius=5000,
                    limit=top_k // 2,
                )

                # Convert to document format
                for poi in poi_results:
                    results.append({
                        "id": poi.get("id"),
                        "type": "poi",
                        "title": poi.get("name"),
                        "content": poi.get("description") or poi.get("summary", ""),
                        "metadata": poi,
                        "source": "poi_search",
                        "score": poi.get("rating", 0) / 5.0,  # Normalize rating
                    })
            except Exception as e:
                logger.error(f"POI search failed: {e}")

        # Route search if route context
        if context and context.get("route_id"):
            try:
                from src.services.route_service import get_route_service
                from src.database.connection import get_session

                async with get_session() as session:
                    route_service = get_route_service(session)
                    route = await route_service.get_route(context["route_id"])

                    if route:
                        results.append({
                            "id": route["id"],
                            "type": "route",
                            "title": f"Route with {route['plan']['total_pois']} POIs",
                            "content": f"Travel route covering {route['plan'].get('estimated_distance_km', 0):.1f}km",
                            "metadata": route,
                            "source": "route_data",
                            "score": 0.7,
                        })
            except Exception as e:
                logger.error(f"Route search failed: {e}")

        return results

    async def _rank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        user_id: str | None,
        context: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Rank retrieved documents.

        Args:
            query: User query
            documents: Retrieved documents
            user_id: Optional user ID
            context: Optional context

        Returns:
            Ranked documents
        """
        if not documents:
            return []

        # Use ranker if available
        if self.ranker:
            try:
                ranked = await self.ranker.rank(
                    query=query,
                    documents=documents,
                    user_id=user_id,
                    context=context,
                )
                return ranked
            except Exception as e:
                logger.error(f"Ranking failed: {e}")

        # Fallback: sort by existing score
        return sorted(documents, key=lambda d: d.get("score", 0.0), reverse=True)

    async def _build_context(
        self,
        documents: list[dict[str, Any]],
        query_context: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Build context for generation.

        Args:
            documents: Ranked documents
            query_context: Original query context

        Returns:
            Context documents
        """
        context = []

        for doc in documents:
            context_item = {
                "content": doc.get("content", ""),
                "metadata": doc.get("metadata", {}),
                "type": doc.get("type", "unknown"),
                "source": doc.get("source", "unknown"),
            }

            # Add location context if available
            if query_context and query_context.get("location"):
                context_item["query_location"] = query_context["location"]

            context.append(context_item)

        return context

    async def _generate(
        self,
        query: str,
        context: list[dict[str, Any]],
        user_id: str | None,
    ) -> str:
        """Generate answer.

        Args:
            query: User query
            context: Context documents
            user_id: Optional user ID

        Returns:
            Generated answer
        """
        # Use generator if available
        if self.generator:
            try:
                return await self.generator.generate(
                    query=query,
                    context=context,
                    user_id=user_id,
                )
            except Exception as e:
                logger.error(f"Generation failed: {e}")

        # Fallback: LLM generation
        return await self._generate_with_llm(query, context)

    async def _generate_with_llm(
        self,
        query: str,
        context: list[dict[str, Any]],
    ) -> str:
        """Generate answer using LLM.

        Args:
            query: User query
            context: Context documents

        Returns:
            Generated answer
        """
        # Build context string
        context_str = self._format_context(context)

        # Get prompt
        prompt = self._build_generation_prompt(query, context_str)

        try:
            response = await self.llm_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.7,
                max_tokens=1000,
            )

            return response.get("content", "").strip()

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return "I apologize, but I'm having trouble generating a response right now."

    def _format_context(self, context: list[dict[str, Any]]) -> str:
        """Format context for prompt.

        Args:
            context: Context documents

        Returns:
            Formatted context string
        """
        if not context:
            return "No specific context available."

        parts = []

        for i, doc in enumerate(context[:5], 1):  # Limit to 5 docs
            content = doc.get("content", "")
            doc_type = doc.get("type", "information")

            if content:
                parts.append(f"[{i}] {doc_type.title()}: {content}")

        return "\n\n".join(parts)

    def _build_generation_prompt(
        self,
        query: str,
        context_str: str,
    ) -> str:
        """Build generation prompt.

        Args:
            query: User query
            context_str: Formatted context

        Returns:
            Prompt string
        """
        return f"""Based on the following context, please answer the user's question.

Context:
{context_str}

Question: {query}

Please provide a helpful and accurate answer based on the context provided. If the context doesn't contain enough information to answer the question, please say so and suggest what additional information would be helpful."""

    def _get_system_prompt(self) -> str:
        """Get system prompt.

        Returns:
            System prompt string
        """
        return """You are Phoenix, an AI travel companion for the Phoenix AI Travel Companion application. Your role is to help users plan their travel, discover places of interest, and get personalized recommendations.

Key capabilities:
- Provide travel advice and recommendations
- Help users discover attractions, restaurants, and activities
- Assist with route planning and itineraries
- Offer personalized suggestions based on user preferences

Guidelines:
- Be helpful, friendly, and informative
- Use the provided context to give accurate answers
- When context is insufficient, acknowledge limitations
- Prioritize user safety and practical considerations
- Consider accessibility and family-friendly options when relevant
- Provide specific, actionable recommendations when possible"""

    async def _generate_fallback_response(
        self,
        query: str,
        context: dict[str, Any] | None,
    ) -> str:
        """Generate fallback response when no context is found.

        Args:
            query: User query
            context: Optional context

        Returns:
            Fallback response
        """
        location = context.get("location") if context else None
        location_hint = f" near {location}" if location else ""
        return (
            f"I don't have enough specific context to answer \"{query}\"{location_hint}. "
            "Please share more details such as destination, dates, budget, or interests so I can help."
        )

    async def stream_response(
        self,
        query: str,
        user_id: str | None = None,
        context: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> AsyncIterable[str]:
        """Stream RAG response.

        Args:
            query: User query
            user_id: Optional user ID
            context: Optional context
            top_k: Number of results

        Yields:
            Response chunks
        """
        # Run pipeline (non-streaming for now)
        result = await self.run(query, user_id, context, top_k)

        # Yield full response
        yield result.get("answer", "")


class ConversationalRAGPipeline(RAGPipeline):
    """RAG pipeline with conversation history support."""

    def __init__(
        self,
        retriever: Any | None = None,
        ranker: Any | None = None,
        generator: Any | None = None,
        embedding_service: EmbeddingService | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        """Initialize conversational RAG pipeline.

        Args:
            retriever: Optional retriever
            ranker: Optional ranker
            generator: Optional generator
            embedding_service: Optional embedding service
            llm_service: Optional LLM service
        """
        super().__init__(retriever, ranker, generator, embedding_service, llm_service)
        self.conversation_history: dict[str, list[dict[str, Any]]] = {}

    async def run_conversation(
        self,
        query: str,
        conversation_id: str,
        user_id: str | None = None,
        context: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Run RAG with conversation history.

        Args:
            query: User query
            conversation_id: Conversation ID
            user_id: Optional user ID
            context: Optional context
            top_k: Number of results

        Returns:
            RAG response
        """
        # Get conversation history
        history = self.conversation_history.get(conversation_id, [])

        # Add current query to history
        history.append({
            "role": "user",
            "content": query,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Build context with history
        enhanced_context = {
            "conversation_history": history[-5:],  # Last 5 turns
        }

        if context:
            enhanced_context.update(context)

        # Run pipeline
        result = await self.run(query, user_id, enhanced_context, top_k)

        # Add response to history
        history.append({
            "role": "assistant",
            "content": result.get("answer", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Store updated history
        self.conversation_history[conversation_id] = history

        result["conversation_id"] = conversation_id

        return result

    def clear_history(self, conversation_id: str) -> None:
        """Clear conversation history.

        Args:
            conversation_id: Conversation ID
        """
        if conversation_id in self.conversation_history:
            del self.conversation_history[conversation_id]

    def get_history(self, conversation_id: str) -> list[dict[str, Any]]:
        """Get conversation history.

        Args:
            conversation_id: Conversation ID

        Returns:
            Conversation history
        """
        return self.conversation_history.get(conversation_id, [])


# Global instances
rag_pipeline = RAGPipeline()
conversational_rag_pipeline = ConversationalRAGPipeline()


def get_rag_pipeline() -> RAGPipeline:
    """Get RAG pipeline instance.

    Returns:
        RAG pipeline instance
    """
    return rag_pipeline


def get_conversational_rag_pipeline() -> ConversationalRAGPipeline:
    """Get conversational RAG pipeline instance.

    Returns:
        Conversational RAG pipeline instance
    """
    return conversational_rag_pipeline
