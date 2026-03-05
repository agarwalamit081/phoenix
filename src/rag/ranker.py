"""RAG ranker for ranking retrieved documents."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import numpy as np

from src.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class RAGRanker:
    """Rank retrieved documents by relevance."""

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        """Initialize RAG ranker.

        Args:
            embedding_service: Optional embedding service
        """
        self.embedding_service = embedding_service or EmbeddingService()

    async def rank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        user_id: str | None = None,
        context: dict[str, Any] | None = None,
        method: str = "hybrid",
    ) -> list[dict[str, Any]]:
        """Rank documents by relevance to query.

        Args:
            query: User query
            documents: Retrieved documents
            user_id: Optional user ID for personalization
            context: Optional context
            method: Ranking method (hybrid, semantic, diversity)

        Returns:
            Ranked documents
        """
        if not documents:
            return []

        if method == "semantic":
            return await self._semantic_rank(query, documents)
        elif method == "diversity":
            return await self._diversity_rank(query, documents)
        else:
            return await self._hybrid_rank(query, documents, user_id, context)

    async def _semantic_rank(
        self,
        query: str,
        documents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Rank by semantic similarity.

        Args:
            query: User query
            documents: Documents to rank

        Returns:
            Ranked documents
        """
        # Generate query embedding
        query_embedding = await self.embedding_service.generate_embedding(query)

        if not query_embedding:
            # Return documents with existing scores
            return sorted(documents, key=lambda d: d.get("score", 0.0), reverse=True)

        # Score each document
        scored = []

        for doc in documents:
            # Check if document has embedding
            doc_embedding = doc.get("embedding")

            if doc_embedding:
                similarity = await self.embedding_service.compute_similarity(
                    query_embedding,
                    doc_embedding,
                )
            else:
                # Use content-based similarity
                content = doc.get("content", "")
                if content:
                    content_embedding = await self.embedding_service.generate_embedding(
                        content[:500]  # Truncate for efficiency
                    )
                    if content_embedding:
                        similarity = await self.embedding_service.compute_similarity(
                            query_embedding,
                            content_embedding,
                        )
                    else:
                        similarity = doc.get("score", 0.0)
                else:
                    similarity = doc.get("score", 0.0)

            scored.append({
                **doc,
                "rerank_score": similarity,
            })

        # Sort by similarity
        scored.sort(key=lambda d: d.get("rerank_score", 0.0), reverse=True)

        return scored

    async def _diversity_rank(
        self,
        query: str,
        documents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Rank with diversity consideration (MMR).

        Args:
            query: User query
            documents: Documents to rank

        Returns:
            Ranked documents with diversity
        """
        if not documents:
            return []

        # Generate query embedding
        query_embedding = await self.embedding_service.generate_embedding(query)

        if not query_embedding:
            return documents

        # Initial semantic ranking
        ranked = await self._semantic_rank(query, documents)

        # MMR (Maximal Marginal Relevance) for diversity
        lambda_param = 0.5  # Balance relevance and diversity
        selected = []
        remaining = ranked.copy()

        while remaining and len(selected) < len(ranked):
            best_idx = 0
            best_score = float("-inf")

            for i, doc in enumerate(remaining):
                # Relevance to query
                relevance = doc.get("rerank_score", 0.0)

                # Diversity from selected
                diversity = 0.0
                if selected:
                    doc_embedding = self._get_doc_embedding(doc)
                    min_sim = 1.0

                    for sel in selected:
                        sel_embedding = self._get_doc_embedding(sel)
                        if doc_embedding and sel_embedding:
                            sim = await self.embedding_service.compute_similarity(
                                doc_embedding,
                                sel_embedding,
                            )
                            min_sim = min(min_sim, sim)

                    diversity = 1 - min_sim

                # MMR score
                mmr_score = lambda_param * relevance + (1 - lambda_param) * diversity

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i

            selected.append(remaining.pop(best_idx))

        return selected

    def _get_doc_embedding(self, doc: dict[str, Any]) -> list[float] | None:
        """Get document embedding.

        Args:
            doc: Document

        Returns:
            Embedding or None
        """
        return doc.get("embedding")

    async def _hybrid_rank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        user_id: str | None,
        context: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Hybrid ranking with multiple factors.

        Args:
            query: User query
            documents: Documents to rank
            user_id: Optional user ID
            context: Optional context

        Returns:
            Ranked documents
        """
        scored = []

        for doc in documents:
            scores = {}

            # Semantic similarity
            scores["semantic"] = doc.get("score", 0.5)

            # Type preference
            scores["type"] = self._score_type(doc, context)

            # Recency
            scores["recency"] = self._score_recency(doc)

            # Location proximity
            scores["location"] = self._score_location(doc, context)

            # User preference match
            if user_id:
                scores["preference"] = await self._score_preference(doc, user_id)
            else:
                scores["preference"] = 0.5

            # Combined score
            weights = {
                "semantic": 0.4,
                "type": 0.15,
                "recency": 0.1,
                "location": 0.2,
                "preference": 0.15,
            }

            combined = sum(
                scores.get(factor, 0.0) * weight
                for factor, weight in weights.items()
            )

            scored.append({
                **doc,
                "rerank_score": combined,
                "score_breakdown": scores,
            })

        # Sort by combined score
        scored.sort(key=lambda d: d.get("rerank_score", 0.0), reverse=True)

        return scored

    def _score_type(
        self,
        doc: dict[str, Any],
        context: dict[str, Any] | None,
    ) -> float:
        """Score based on document type.

        Args:
            doc: Document
            context: Query context

        Returns:
            Type score (0-1)
        """
        doc_type = doc.get("type", "")
        doc_source = doc.get("source", "")

        # Preferred types
        preferred_types = ["poi", "route", "knowledge_graph_recommendation"]

        if doc_type in preferred_types:
            return 0.8
        elif doc_source == "knowledge_graph":
            return 0.7
        elif doc_source == "poi_search":
            return 0.6
        else:
            return 0.4

    def _score_recency(
        self,
        doc: dict[str, Any],
    ) -> float:
        """Score based on recency.

        Args:
            doc: Document

        Returns:
            Recency score (0-1)
        """
        indexed_at = doc.get("indexed_at") or doc.get("created_at")

        if not indexed_at:
            return 0.5

        try:
            indexed_time = datetime.fromisoformat(indexed_at.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - indexed_time).days

            # Decay over time
            if age_days < 1:
                return 1.0
            elif age_days < 7:
                return 0.8
            elif age_days < 30:
                return 0.6
            elif age_days < 90:
                return 0.4
            else:
                return 0.2
        except Exception:
            return 0.5

    def _score_location(
        self,
        doc: dict[str, Any],
        context: dict[str, Any] | None,
    ) -> float:
        """Score based on location proximity.

        Args:
            doc: Document
            context: Query context

        Returns:
            Location score (0-1)
        """
        if not context or not context.get("location"):
            return 0.5

        doc_location = doc.get("metadata", {}).get("location")

        if not doc_location:
            # Check for lat/lng in metadata
            metadata = doc.get("metadata", {})
            lat = metadata.get("latitude")
            lng = metadata.get("longitude")

            if lat and lng:
                doc_location = {"lat": lat, "lng": lng}

        if not doc_location:
            return 0.5

        # Calculate distance
        query_location = context["location"]
        distance = self._calculate_distance(
            query_location.get("lat", 0),
            query_location.get("lng", 0),
            doc_location.get("lat", 0),
            doc_location.get("lng", 0),
        )

        # Score based on distance (closer is better)
        if distance < 1:
            return 1.0
        elif distance < 5:
            return 0.8
        elif distance < 10:
            return 0.6
        elif distance < 25:
            return 0.4
        else:
            return 0.2

    def _calculate_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """Calculate distance between two points.

        Args:
            lat1: First latitude
            lon1: First longitude
            lat2: Second latitude
            lon2: Second longitude

        Returns:
            Distance in km
        """
        import math

        R = 6371

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = (
            math.sin(dlat / 2) ** 2 +
            math.cos(math.radians(lat1)) *
            math.cos(math.radians(lat2)) *
            math.sin(dlon / 2) ** 2
        )

        c = 2 * math.asin(math.sqrt(a))

        return R * c

    async def _score_preference(
        self,
        doc: dict[str, Any],
        user_id: str,
    ) -> float:
        """Score based on user preferences.

        Args:
            doc: Document
            user_id: User ID

        Returns:
            Preference score (0-1)
        """
        # This would integrate with user preference service
        # For now, return neutral score
        return 0.5

    async def filter_by_threshold(
        self,
        documents: list[dict[str, Any]],
        threshold: float = 0.3,
        score_key: str = "rerank_score",
    ) -> list[dict[str, Any]]:
        """Filter documents by score threshold.

        Args:
            documents: Documents to filter
            threshold: Minimum score
            score_key: Key for score field

        Returns:
            Filtered documents
        """
        return [
            doc for doc in documents
            if doc.get(score_key, 0.0) >= threshold
        ]

    async def deduplicate(
        self,
        documents: list[dict[str, Any]],
        similarity_threshold: float = 0.95,
    ) -> list[dict[str, Any]]:
        """Remove duplicate documents.

        Args:
            documents: Documents to deduplicate
            similarity_threshold: Similarity threshold for duplicates

        Returns:
            Deduplicated documents
        """
        if not documents:
            return []

        unique = []
        seen_ids = set()

        for doc in documents:
            doc_id = doc.get("id")

            if doc_id:
                if doc_id not in seen_ids:
                    unique.append(doc)
                    seen_ids.add(doc_id)
            else:
                # Check content similarity
                is_duplicate = False

                content = doc.get("content", "")
                if not content:
                    unique.append(doc)
                    continue

                for seen_doc in unique:
                    seen_content = seen_doc.get("content", "")
                    if seen_content and content == seen_content:
                        is_duplicate = True
                        break

                if not is_duplicate:
                    unique.append(doc)

        return unique


class PersonalizedRAGRanker(RAGRanker):
    """Personalized ranker with user history."""

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        """Initialize personalized ranker.

        Args:
            embedding_service: Optional embedding service
        """
        super().__init__(embedding_service)
        self.user_history: dict[str, list[dict[str, Any]]] = {}

    async def record_feedback(
        self,
        user_id: str,
        query: str,
        selected_doc_ids: list[str],
        skipped_doc_ids: list[str] | None = None,
    ) -> None:
        """Record user feedback for personalization.

        Args:
            user_id: User ID
            query: Query
            selected_doc_ids: Document IDs user selected
            skipped_doc_ids: Document IDs user skipped
        """
        if user_id not in self.user_history:
            self.user_history[user_id] = []

        self.user_history[user_id].append({
            "query": query,
            "selected": selected_doc_ids,
            "skipped": skipped_doc_ids or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def _score_preference(
        self,
        doc: dict[str, Any],
        user_id: str,
    ) -> float:
        """Score based on user preference history.

        Args:
            doc: Document
            user_id: User ID

        Returns:
            Preference score (0-1)
        """
        if user_id not in self.user_history:
            return 0.5

        history = self.user_history[user_id]

        if not history:
            return 0.5

        doc_id = doc.get("id")
        doc_type = doc.get("type")
        doc_category = doc.get("metadata", {}).get("category")

        score = 0.5
        count = 0

        for entry in history:
            selected = entry.get("selected", [])
            skipped = entry.get("skipped", [])

            if doc_id in selected:
                score += 0.3
                count += 1
            elif doc_id in skipped:
                score -= 0.2
                count += 1

            # Type/category preference
            for sel_id in selected:
                # This is simplified - would need document lookup
                if doc_type or doc_category:
                    score += 0.1
                    count += 1

        if count > 0:
            score = max(0.0, min(1.0, score / count))

        return score


class CrossEncoderRanker(RAGRanker):
    """Ranker using cross-encoder for more accurate scoring."""

    async def rank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        user_id: str | None = None,
        context: dict[str, Any] | None = None,
        method: str = "hybrid",
    ) -> list[dict[str, Any]]:
        """Rank using cross-encoder scoring.

        Args:
            query: User query
            documents: Documents to rank
            user_id: Optional user ID
            context: Optional context
            method: Ranking method

        Returns:
            Ranked documents
        """
        # For now, use parent ranking
        # In production, would use a cross-encoder model
        return await super().rank(query, documents, user_id, context, method)


# Global instances
rag_ranker = RAGRanker()
personalized_rag_ranker = PersonalizedRAGRanker()
cross_encoder_ranker = CrossEncoderRanker()


def get_rag_ranker() -> RAGRanker:
    """Get RAG ranker instance.

    Returns:
        RAG ranker instance
    """
    return rag_ranker


def get_personalized_rag_ranker() -> PersonalizedRAGRanker:
    """Get personalized RAG ranker instance.

    Returns:
        Personalized RAG ranker instance
    """
    return personalized_rag_ranker


def get_cross_encoder_ranker() -> CrossEncoderRanker:
    """Get cross-encoder ranker instance.

    Returns:
        Cross-encoder ranker instance
    """
    return cross_encoder_ranker
