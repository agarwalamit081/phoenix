"""POI enricher for generating embeddings and enriching POI data."""

import asyncio
import logging
from collections.abc import AsyncIterable
from datetime import datetime, timezone
from typing import Any

import numpy as np

from src.config.settings import settings
from src.services.embedding_service import EmbeddingService
from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class POIEnricher:
    """Enrich POI data with embeddings and AI-generated content."""

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        """Initialize POI enricher.

        Args:
            embedding_service: Optional embedding service
            llm_service: Optional LLM service
        """
        self.embedding_service = embedding_service or EmbeddingService()
        self.llm_service = llm_service or LLMService()

    async def generate_embedding(
        self,
        poi: dict[str, Any],
    ) -> list[float] | None:
        """Generate embedding for a POI.

        Args:
            poi: POI data

        Returns:
            Embedding vector or None
        """
        # Build text representation for embedding
        text_parts = []

        if poi.get("name"):
            text_parts.append(f"Name: {poi['name']}")

        if poi.get("description"):
            text_parts.append(f"Description: {poi['description']}")

        if poi.get("category"):
            text_parts.append(f"Category: {poi['category']}")

        if poi.get("types"):
            text_parts.append(f"Types: {', '.join(poi['types'])}")

        if poi.get("address"):
            text_parts.append(f"Address: {poi['address']}")

        text = " | ".join(text_parts)

        if not text:
            return None

        try:
            embedding = await self.embedding_service.generate_embedding(text)
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding for {poi.get('name')}: {e}")
            return None

    async def generate_summary(
        self,
        poi: dict[str, Any],
        max_length: int = 200,
    ) -> str | None:
        """Generate AI summary for a POI.

        Args:
            poi: POI data
            max_length: Maximum summary length

        Returns:
            Generated summary or None
        """
        # If description exists, truncate it
        if poi.get("description"):
            description = poi["description"]
            if len(description) > max_length:
                return description[:max_length] + "..."
            return description

        # Generate summary from other data
        prompt = self._build_summary_prompt(poi)

        try:
            response = await self.llm_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a travel guide writer. Create concise, engaging descriptions of places.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.7,
                max_tokens=300,
            )

            summary = response.get("content", "").strip()

            # Truncate if needed
            if len(summary) > max_length:
                summary = summary[:max_length] + "..."

            return summary

        except Exception as e:
            logger.error(f"Failed to generate summary for {poi.get('name')}: {e}")
            return None

    def _build_summary_prompt(self, poi: dict[str, Any]) -> str:
        """Build prompt for summary generation.

        Args:
            poi: POI data

        Returns:
            Prompt string
        """
        parts = [f"Write a brief description (under 100 words) for:"]

        if poi.get("name"):
            parts.append(f"Name: {poi['name']}")

        if poi.get("category"):
            parts.append(f"Type: {poi['category']}")

        if poi.get("types"):
            parts.append(f"Features: {', '.join(poi['types'][:5])}")

        if poi.get("rating"):
            parts.append(f"Rating: {poi['rating']}/5")

        return ". ".join(parts)

    async def enrich_poi(
        self,
        poi: dict[str, Any],
        generate_embedding: bool = True,
        generate_summary: bool = True,
    ) -> dict[str, Any]:
        """Enrich a single POI.

        Args:
            poi: POI data
            generate_embedding: Whether to generate embedding
            generate_summary: Whether to generate summary

        Returns:
            Enriched POI data
        """
        enriched = poi.copy()

        # Generate embedding
        if generate_embedding:
            embedding = await self.generate_embedding(poi)
            if embedding:
                enriched["embedding"] = embedding
                enriched["embedding_model"] = settings.openai_model_embedding

        # Generate summary
        if generate_summary and not poi.get("summary"):
            summary = await self.generate_summary(poi)
            if summary:
                enriched["summary"] = summary

        enriched["enriched_at"] = datetime.now(timezone.utc).isoformat()

        return enriched

    async def enrich_batch(
        self,
        pois: list[dict[str, Any]],
        generate_embeddings: bool = True,
        generate_summaries: bool = True,
        concurrency: int = 5,
    ) -> list[dict[str, Any]]:
        """Enrich a batch of POIs.

        Args:
            pois: List of POI data
            generate_embeddings: Whether to generate embeddings
            generate_summaries: Whether to generate summaries
            concurrency: Number of concurrent enrichments

        Returns:
            List of enriched POIs
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def enrich_with_semaphore(poi: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                return await self.enrich_poi(
                    poi,
                    generate_embedding=generate_embeddings,
                    generate_summary=generate_summaries,
                )

        tasks = [enrich_with_semaphore(poi) for poi in pois]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        enriched = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to enrich POI {pois[i].get('name')}: {result}")
                # Return original POI without enrichment
                enriched.append(pois[i])
            else:
                enriched.append(result)

        logger.info(f"Enriched {len(enriched)} POIs")

        return enriched

    async def calculate_similarity(
        self,
        poi1: dict[str, Any],
        poi2: dict[str, Any],
    ) -> float:
        """Calculate similarity between two POIs.

        Args:
            poi1: First POI data
            poi2: Second POI data

        Returns:
            Similarity score (0-1)
        """
        emb1 = poi1.get("embedding")
        emb2 = poi2.get("embedding")

        if not emb1 or not emb2:
            # Fall back to category similarity
            if poi1.get("category") == poi2.get("category"):
                return 0.5
            return 0.0

        try:
            # Calculate cosine similarity
            return await self.embedding_service.compute_similarity(emb1, emb2)

        except Exception as e:
            logger.error(f"Failed to calculate similarity: {e}")
            return 0.0

    async def extract_attributes(
        self,
        poi: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract structured attributes from POI data.

        Args:
            poi: POI data

        Returns:
            Extracted attributes
        """
        attributes = {
            "name": poi.get("name"),
            "category": poi.get("category"),
            "subcategories": [],
            "features": [],
            "price_range": self._extract_price_range(poi),
            "rating_tier": self._extract_rating_tier(poi),
            "accessibility": self._extract_accessibility(poi),
            "best_visit_time": None,
            "duration_estimate": None,
        }

        # Extract subcategories from types
        types = poi.get("types", [])
        for t in types:
            if t != poi.get("category") and len(t) > 2:
                attributes["subcategories"].append(t)

        # Extract features from description
        description = poi.get("description") or poi.get("summary") or ""
        if description:
            attributes["features"] = self._extract_features_from_text(description)

        return attributes

    def _extract_price_range(self, poi: dict[str, Any]) -> str | None:
        """Extract price range from POI data.

        Args:
            poi: POI data

        Returns:
            Price range string
        """
        price_level = poi.get("price_level")

        if price_level is None:
            return None

        mapping = {
            0: "Free",
            1: "Inexpensive",
            2: "Moderate",
            3: "Expensive",
            4: "Very Expensive",
        }

        return mapping.get(price_level)

    def _extract_rating_tier(self, poi: dict[str, Any]) -> str | None:
        """Extract rating tier from POI data.

        Args:
            poi: POI data

        Returns:
            Rating tier
        """
        rating = poi.get("rating")

        if rating is None:
            return None

        if rating >= 4.5:
            return "Excellent"
        elif rating >= 4.0:
            return "Very Good"
        elif rating >= 3.5:
            return "Good"
        elif rating >= 3.0:
            return "Average"
        else:
            return "Below Average"

    def _extract_accessibility(self, poi: dict[str, Any]) -> dict[str, bool]:
        """Extract accessibility information.

        Args:
            poi: POI data

        Returns:
            Accessibility features
        """
        # This would come from detailed place data
        return {
            "wheelchair": False,
            "parking": False,
            "public_transport": False,
        }

    def _extract_features_from_text(self, text: str) -> list[str]:
        """Extract features from description text.

        Args:
            text: Description text

        Returns:
            List of features
        """
        features = []

        # Common feature keywords
        feature_keywords = {
            "wifi": ["wifi", "wi-fi", "internet"],
            "parking": ["parking", "park"],
            "outdoor": ["outdoor", "terrace", "patio"],
            "kid_friendly": ["kid", "family", "children"],
            "pet_friendly": ["pet", "dog"],
            "accessible": ["wheelchair", "accessible"],
            "reservation": ["reservation", "booking"],
        }

        text_lower = text.lower()

        for feature, keywords in feature_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                features.append(feature)

        return features


# Global instance
poi_enricher = POIEnricher()
