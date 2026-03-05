"""RAG generator for creating responses from retrieved context."""

import asyncio
import json
import logging
from collections.abc import AsyncIterable
from datetime import datetime, timezone
from typing import Any

from src.services.llm_service import LLMService
from src.rag.prompts import (
    get_system_prompt,
    get_travel_advice_prompt,
    get_poi_recommendation_prompt,
    get_route_planning_prompt,
    get_comparison_prompt,
)


logger = logging.getLogger(__name__)


class RAGGenerator:
    """Generate responses using retrieved context."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
    ) -> None:
        """Initialize RAG generator.

        Args:
            llm_service: Optional LLM service
        """
        self.llm_service = llm_service or LLMService()

    async def generate(
        self,
        query: str,
        context: list[dict[str, Any]],
        user_id: str | None = None,
        response_type: str = "general",
    ) -> str:
        """Generate response from context.

        Args:
            query: User query
            context: Retrieved context documents
            user_id: Optional user ID
            response_type: Type of response (general, travel_advice, poi, route, comparison)

        Returns:
            Generated response
        """
        # Select prompt based on response type
        if response_type == "travel_advice":
            prompt = get_travel_advice_prompt(query, context)
        elif response_type == "poi":
            prompt = get_poi_recommendation_prompt(query, context)
        elif response_type == "route":
            prompt = get_route_planning_prompt(query, context)
        elif response_type == "comparison":
            prompt = get_comparison_prompt(query, context)
        else:
            prompt = self._build_general_prompt(query, context)

        try:
            response = await self.llm_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": get_system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.7,
                max_tokens=1500,
            )

            return response.get("content", "").strip()

        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return self._get_fallback_response(query)

    def _build_general_prompt(
        self,
        query: str,
        context: list[dict[str, Any]],
    ) -> str:
        """Build general prompt.

        Args:
            query: User query
            context: Context documents

        Returns:
            Prompt string
        """
        context_str = self._format_context(context)

        return f"""Based on the following information, please answer the user's question.

{context_str}

Question: {query}

Please provide a helpful, accurate response based on the context above. If the context doesn't contain enough information to fully answer the question, please acknowledge this and provide what guidance you can."""

    def _format_context(self, context: list[dict[str, Any]]) -> str:
        """Format context documents.

        Args:
            context: Context documents

        Returns:
            Formatted context string
        """
        if not context:
            return "No additional context available."

        parts = []

        for i, doc in enumerate(context[:6], 1):  # Limit to 6 docs
            doc_type = doc.get("type", "information")
            content = doc.get("content", "")

            if content:
                source = doc.get("source", "unknown")

                if doc_type == "poi":
                    title = doc.get("metadata", {}).get("name", "Point of Interest")
                    parts.append(
                        f"[{i}] {title} ({doc_type} from {source}):\n{content[:300]}"
                    )
                else:
                    parts.append(
                        f"[{i}] {doc_type.replace('_', ' ').title()} (from {source}):\n{content[:300]}"
                    )

        return "\n\n".join(parts)

    def _get_fallback_response(self, query: str) -> str:
        """Get fallback response.

        Args:
            query: User query

        Returns:
            Fallback response
        """
        return """I apologize, but I'm having trouble generating a response right now. This might be due to:

1. Insufficient information in my current knowledge base
2. Temporary technical difficulties

For the best results, please try:
- Being more specific about what you're looking for
- Including location details if you're asking about places
- Describing your preferences (e.g., budget, interests, group size)

Is there anything else I can help you with?"""

    async def generate_with_citations(
        self,
        query: str,
        context: list[dict[str, Any]],
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate response with citations.

        Args:
            query: User query
            context: Context documents
            user_id: Optional user ID

        Returns:
            Response with citations
        """
        # Generate main response
        response = await self.generate(query, context, user_id)

        # Extract citations from context
        citations = []

        for i, doc in enumerate(context[:5], 1):
            citations.append({
                "id": doc.get("id", f"source_{i}"),
                "type": doc.get("type", "unknown"),
                "title": doc.get("metadata", {}).get("name") or doc.get("title", f"Source {i}"),
                "source": doc.get("source", "unknown"),
            })

        return {
            "response": response,
            "citations": citations,
        }

    async def generate_structured(
        self,
        query: str,
        context: list[dict[str, Any]],
        schema: dict[str, Any],
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate structured response.

        Args:
            query: User query
            context: Context documents
            schema: Response schema
            user_id: Optional user ID

        Returns:
            Structured response
        """
        # Build prompt with schema
        context_str = self._format_context(context)

        prompt = f"""Based on the following information, provide a structured response.

{context_str}

Question: {query}

Please respond with a JSON object following this schema:
{json.dumps(schema, indent=2)}

Return only the JSON, no additional text."""

        try:
            response = await self.llm_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful travel assistant. Always respond with valid JSON.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.5,
                max_tokens=1000,
                response_format={"type": "json_object"},
            )

            content = response.get("content", "{}")

            return json.loads(content)

        except Exception as e:
            logger.error(f"Structured generation failed: {e}")

            # Return empty schema
            return {key: None for key in schema.keys()}

    async def generate_multi_turn(
        self,
        messages: list[dict[str, str]],
        context: list[dict[str, Any]],
        user_id: str | None = None,
    ) -> str:
        """Generate response in multi-turn conversation.

        Args:
            messages: Conversation history
            context: Current context
            user_id: Optional user ID

        Returns:
            Generated response
        """
        # Build messages with context
        system_prompt = get_system_prompt()

        augmented_messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Add conversation history
        for msg in messages[:-1]:
            augmented_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        # Add current query with context
        current_query = messages[-1].get("content", "")
        context_str = self._format_context(context)

        augmented_messages.append({
            "role": "user",
            "content": f"""Context:
{context_str}

Current message: {current_query}""",
        })

        try:
            response = await self.llm_service.chat_completion(
                messages=augmented_messages,
                temperature=0.7,
                max_tokens=1500,
            )

            return response.get("content", "").strip()

        except Exception as e:
            logger.error(f"Multi-turn generation failed: {e}")
            return self._get_fallback_response(current_query)

    async def stream_generate(
        self,
        query: str,
        context: list[dict[str, Any]],
        user_id: str | None = None,
    ) -> AsyncIterable[str]:
        """Stream generated response.

        Args:
            query: User query
            context: Context documents
            user_id: Optional user ID

        Yields:
            Response chunks
        """
        # Build prompt
        prompt = self._build_general_prompt(query, context)

        try:
            async for chunk in self.llm_service.stream_chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": get_system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.7,
                max_tokens=1500,
            ):
                yield chunk

        except Exception as e:
            logger.error(f"Streaming generation failed: {e}")
            yield self._get_fallback_response(query)


class TravelAdviceGenerator(RAGGenerator):
    """Specialized generator for travel advice."""

    async def generate(
        self,
        query: str,
        context: list[dict[str, Any]],
        user_id: str | None = None,
        response_type: str = "travel_advice",
    ) -> str:
        """Generate travel advice response.

        Args:
            query: User query
            context: Context documents
            user_id: Optional user ID
            response_type: Response type (ignored, always travel_advice)

        Returns:
            Generated travel advice
        """
        prompt = get_travel_advice_prompt(query, context)

        try:
            response = await self.llm_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": get_system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.8,
                max_tokens=1500,
            )

            return response.get("content", "").strip()

        except Exception as e:
            logger.error(f"Travel advice generation failed: {e}")
            return await super().generate(query, context, user_id)


class POIRecommendationGenerator(RAGGenerator):
    """Specialized generator for POI recommendations."""

    async def generate(
        self,
        query: str,
        context: list[dict[str, Any]],
        user_id: str | None = None,
        response_type: str = "poi",
    ) -> str:
        """Generate POI recommendation response.

        Args:
            query: User query
            context: Context documents
            user_id: Optional user ID
            response_type: Response type (ignored, always poi)

        Returns:
            Generated POI recommendations
        """
        prompt = get_poi_recommendation_prompt(query, context)

        try:
            response = await self.llm_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": get_system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.7,
                max_tokens=1500,
            )

            return response.get("content", "").strip()

        except Exception as e:
            logger.error(f"POI recommendation generation failed: {e}")
            return await super().generate(query, context, user_id)


class RoutePlanningGenerator(RAGGenerator):
    """Specialized generator for route planning."""

    async def generate(
        self,
        query: str,
        context: list[dict[str, Any]],
        user_id: str | None = None,
        response_type: str = "route",
    ) -> str:
        """Generate route planning response.

        Args:
            query: User query
            context: Context documents
            user_id: Optional user ID
            response_type: Response type (ignored, always route)

        Returns:
            Generated route planning advice
        """
        prompt = get_route_planning_prompt(query, context)

        try:
            response = await self.llm_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": get_system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.6,
                max_tokens=2000,
            )

            return response.get("content", "").strip()

        except Exception as e:
            logger.error(f"Route planning generation failed: {e}")
            return await super().generate(query, context, user_id)


# Global instances
rag_generator = RAGGenerator()
travel_advice_generator = TravelAdviceGenerator()
poi_generator = POIRecommendationGenerator()
route_generator = RoutePlanningGenerator()


def get_rag_generator() -> RAGGenerator:
    """Get RAG generator instance.

    Returns:
        RAG generator instance
    """
    return rag_generator


def get_travel_advice_generator() -> TravelAdviceGenerator:
    """Get travel advice generator instance.

    Returns:
        Travel advice generator instance
    """
    return travel_advice_generator


def get_poi_generator() -> POIRecommendationGenerator:
    """Get POI generator instance.

    Returns:
        POI generator instance
    """
    return poi_generator


def get_route_generator() -> RoutePlanningGenerator:
    """Get route generator instance.

    Returns:
        Route generator instance
    """
    return route_generator
