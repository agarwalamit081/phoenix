"""Social service for social intelligence operations."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import settings
from src.social.analyzer import (
    SentimentAnalyzer,
    TrendAnalyzer,
    SocialInsightExtractor,
    get_sentiment_analyzer,
    get_trend_analyzer,
    get_insight_extractor,
)
from src.social.cache import (
    get_search_cache,
    get_sentiment_cache,
    get_insights_cache,
)
from src.social.collector import (
    SocialCollector,
    SocialPost,
    get_social_collector,
)

logger = logging.getLogger(__name__)


class SocialService:
    """Service for social intelligence operations."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        """Initialize social service.

        Args:
            session: Database session
        """
        self.session = session

        # Initialize collectors with API keys from settings
        self.collector = SocialCollector(
            reddit_api_key=settings.reddit_client_id,
            google_maps_api_key=settings.google_maps_api_key,
        )

        # Initialize analyzers
        self.sentiment_analyzer = get_sentiment_analyzer()
        self.trend_analyzer = get_trend_analyzer()
        self.insight_extractor = get_insight_extractor()

        # Initialize caches
        self.search_cache = get_search_cache()
        self.sentiment_cache = get_sentiment_cache()
        self.insights_cache = get_insights_cache()

    async def search_social(
        self,
        query: str,
        location: str | None = None,
        platform: str | None = None,
        use_cache: bool = True,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Search social media for travel content.

        Args:
            query: Search query
            location: Optional location filter
            platform: Optional platform filter
            use_cache: Whether to use cache
            limit: Maximum results

        Returns:
            Search results
        """
        # Check cache
        if use_cache:
            cached = await self.search_cache.get_search_results(query, location, platform)
            if cached:
                logger.info(f"Retrieved cached search results for query: {query}")
                return cached

        # Perform search
        if platform == "reddit":
            posts = await self.collector.reddit.search(query, location, limit)
        elif platform == "google_maps":
            posts = await self.collector.google_maps.search(query, location, limit)
        else:
            posts = await self.collector.search_all(query, location, limit)

        results = {
            "query": query,
            "location": location,
            "platform": platform,
            "posts": [post.to_dict() for post in posts],
            "total_found": len(posts),
            "searched_at": datetime.now(timezone.utc).isoformat(),
        }

        # Cache results
        if use_cache and posts:
            await self.search_cache.set_search_results(query, results, location, platform)

        return results

    async def get_trending(
        self,
        location: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Get trending travel content.

        Args:
            location: Optional location filter
            limit: Maximum results

        Returns:
            Trending content
        """
        posts = await self.collector.get_trending_all(location, limit)

        # Extract trending topics
        trending_topics = self.trend_analyzer.extract_trending_topics(posts, top_n=10)

        # Detect emerging trends
        emerging_trends = self.trend_analyzer.detect_emerging_trends(posts)

        return {
            "location": location,
            "posts": [post.to_dict() for post in posts[:limit]],
            "trending_topics": trending_topics,
            "emerging_trends": emerging_trends,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }

    async def analyze_sentiment(
        self,
        text: str,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Analyze sentiment of text.

        Args:
            text: Text to analyze
            use_cache: Whether to use cache

        Returns:
            Sentiment analysis
        """
        # Check cache
        if use_cache:
            cached = await self.sentiment_cache.get_sentiment(text)
            if cached:
                return cached

        # Analyze
        analysis = await self.sentiment_analyzer.analyze_sentiment(text)

        # Cache result
        if use_cache:
            await self.sentiment_cache.set_sentiment(text, analysis)

        return analysis

    async def extract_insights(
        self,
        query: str | None = None,
        location: str | None = None,
        days: int = 7,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Extract travel insights from social data.

        Args:
            query: Optional search query
            location: Optional location
            days: Number of days to look back
            use_cache: Whether to use cache

        Returns:
            Extracted insights
        """
        # Check cache
        if use_cache:
            cached = await self.insights_cache.get_insights(location, days)
            if cached:
                logger.info(f"Retrieved cached insights for location: {location}")
                return cached

        # Gather recent posts
        if query:
            posts = await self.collector.search_all(query, location, limit=200)
        else:
            posts = await self.collector.get_trending_all(location, limit=200)

        # Filter by date
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent_posts = [p for p in posts if p.timestamp >= cutoff]

        if not recent_posts:
            return {
                "location": location,
                "days": days,
                "total_posts": 0,
                "message": "No recent posts found for the specified criteria",
            }

        # Extract insights
        insights = await self.insight_extractor.extract_insights(
            recent_posts,
            location,
        )

        insights["query"] = query
        insights["days"] = days
        insights["extracted_at"] = datetime.now(timezone.utc).isoformat()

        # Cache insights
        if use_cache:
            await self.insights_cache.set_insights(insights, location, days)

        return insights

    async def get_location_insights(
        self,
        location: str,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get comprehensive insights for a location.

        Args:
            location: Location name
            days: Number of days

        Returns:
            Location insights
        """
        insights = await self.extract_insights(
            query=location,
            location=location,
            days=days,
        )

        # Get trending
        trending = await self.get_trending(location, limit=20)

        # Combine insights
        return {
            "location": location,
            "period_days": days,
            "sentiment": insights.get("sentiment_summary", {}),
            "trending_topics": insights.get("trending_topics", []),
            "emerging_trends": insights.get("emerging_trends", []),
            "top_recommendations": insights.get("top_recommendations", []),
            "warnings": insights.get("warnings", []),
            "trending_posts": trending.get("posts", [])[:10],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def compare_sentiment(
        self,
        locations: list[str],
    ) -> dict[str, Any]:
        """Compare sentiment across locations.

        Args:
            locations: List of locations to compare

        Returns:
            Sentiment comparison
        """
        comparisons = []

        for location in locations:
            try:
                insights = await self.extract_insights(
                    query=location,
                    location=location,
                    days=7,
                )

                sentiment_summary = insights.get("sentiment_summary", {})

                comparisons.append({
                    "location": location,
                    "total_posts": insights.get("total_posts", 0),
                    "positive_ratio": (
                        sentiment_summary.get("positive", 0) /
                        insights.get("total_posts", 1)
                        if insights.get("total_posts", 0) > 0 else 0
                    ),
                    "avg_confidence": sentiment_summary.get("avg_confidence", 0.5),
                })

            except Exception as e:
                logger.error(f"Failed to analyze {location}: {e}")
                comparisons.append({
                    "location": location,
                    "error": str(e),
                })

        # Sort by positive ratio
        comparisons.sort(
            key=lambda c: c.get("positive_ratio", 0),
            reverse=True,
        )

        return {
            "locations": locations,
            "comparisons": comparisons,
            "compared_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_recommendations_from_social(
        self,
        location: str,
        preferences: list[dict[str, Any]] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Get recommendations based on social data.

        Args:
            location: Location
            preferences: Optional user preferences
            limit: Maximum recommendations

        Returns:
            Recommendations
        """
        insights = await self.extract_insights(
            query=location,
            location=location,
            days=7,
        )

        # Get top recommendations from insights
        recommendations = insights.get("top_recommendations", [])[:limit]

        # Filter by preferences if provided
        if preferences:
            filtered = []

            liked_categories = [
                p["value"]
                for p in preferences
                if p.get("preference_type") == "like" and p.get("category") == "category"
            ]

            for rec in recommendations:
                content = rec.get("content", "").lower()

                # Check if recommendation matches preferences
                if any(
                    any(cat.lower() in content for cat in [liked] if isinstance(liked, str))
                    for liked in liked_categories
                ):
                    filtered.append(rec)

            recommendations = filtered

        return {
            "location": location,
            "recommendations": recommendations,
            "total_count": len(recommendations),
            "preferences_applied": preferences is not None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_warnings(
        self,
        location: str,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get warnings for a location from social data.

        Args:
            location: Location
            days: Number of days

        Returns:
            Warnings
        """
        insights = await self.extract_insights(
            query=location,
            location=location,
            days=days,
        )

        warnings = insights.get("warnings", [])

        return {
            "location": location,
            "warnings": warnings,
            "total_count": len(warnings),
            "period_days": days,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }

    async def cleanup_cache(self) -> dict[str, Any]:
        """Clean up expired cache entries.

        Returns:
            Cleanup results
        """
        search_expired = await self.search_cache.cleanup_expired()
        sentiment_expired = await self.sentiment_cache.cleanup_expired()
        insights_expired = await self.insights_cache.cleanup_expired()

        return {
            "search_entries_removed": search_expired,
            "sentiment_entries_removed": sentiment_expired,
            "insights_entries_removed": insights_expired,
            "cleaned_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache statistics
        """
        search_stats = await self.search_cache.get_stats()
        sentiment_stats = await self.sentiment_cache.get_stats()
        insights_stats = await self.insights_cache.get_stats()

        return {
            "search_cache": search_stats,
            "sentiment_cache": sentiment_stats,
            "insights_cache": insights_stats,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }

    async def close(self) -> None:
        """Close social collector."""
        await self.collector.close()


# Global instance factory
def get_social_service(session: AsyncSession) -> SocialService:
    """Get social service instance.

    Args:
        session: Database session

    Returns:
        Social service instance
    """
    return SocialService(session)
