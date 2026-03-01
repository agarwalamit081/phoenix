"""Social data analyzer for extracting insights from social media."""

import asyncio
import logging
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Any

from src.services.llm_service import LLMService
from src.social.collector import SocialPost

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Analyze sentiment of social posts."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
    ) -> None:
        """Initialize sentiment analyzer.

        Args:
            llm_service: Optional LLM service
        """
        self.llm_service = llm_service or LLMService()

    async def analyze_sentiment(
        self,
        text: str,
    ) -> dict[str, Any]:
        """Analyze sentiment of text.

        Args:
            text: Text to analyze

        Returns:
            Sentiment analysis results
        """
        try:
            prompt = f"""Analyze the sentiment of this travel-related text. Respond with a JSON object containing:

{{
  "sentiment": "positive" | "negative" | "neutral",
  "confidence": 0.0-1.0,
  "key_topics": ["topic1", "topic2"],
  "emotional_tone": "enthusiastic" | "critical" | "informative" | "cautious"
}}

Text to analyze:
{text}

Return only the JSON, no additional text."""

            response = await self.llm_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a sentiment analyzer. Always respond with valid JSON.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.3,
                max_tokens=200,
            )

            import json

            content = response.get("content", "{}")
            return json.loads(content)

        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")

            # Fallback: simple keyword-based analysis
            return self._fallback_sentiment_analysis(text)

    def _fallback_sentiment_analysis(self, text: str) -> dict[str, Any]:
        """Fallback sentiment analysis using keywords.

        Args:
            text: Text to analyze

        Returns:
            Sentiment analysis
        """
        text_lower = text.lower()

        positive_words = [
            "amazing", "great", "awesome", "beautiful", "love", "loved",
            "excellent", "wonderful", "fantastic", "recommended", "best",
        ]

        negative_words = [
            "terrible", "awful", "bad", "hate", "disappointed", "worst",
            "avoid", "poor", "dirty", "rude", "overpriced",
        ]

        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        if positive_count > negative_count:
            sentiment = "positive"
            confidence = min(0.7, positive_count / 10)
        elif negative_count > positive_count:
            sentiment = "negative"
            confidence = min(0.7, negative_count / 10)
        else:
            sentiment = "neutral"
            confidence = 0.5

        return {
            "sentiment": sentiment,
            "confidence": confidence,
            "key_topics": [],
            "emotional_tone": "informative",
        }

    async def analyze_batch(
        self,
        posts: list[SocialPost],
    ) -> list[dict[str, Any]]:
        """Analyze sentiment for multiple posts.

        Args:
            posts: List of social posts

        Returns:
            List of sentiment analyses
        """
        tasks = [self.analyze_sentiment(post.content) for post in posts]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        analyses = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Sentiment analysis failed for post {i}: {result}")
                analyses.append(self._fallback_sentiment_analysis(posts[i].content))
            else:
                analyses.append(result)

        return analyses


class TrendAnalyzer:
    """Analyze trends in social travel data."""

    def __init__(self) -> None:
        """Initialize trend analyzer."""
        pass

    def extract_trending_topics(
        self,
        posts: list[SocialPost],
        top_n: int = 10,
    ) -> list[dict[str, Any]]:
        """Extract trending topics from posts.

        Args:
            posts: List of social posts
            top_n: Number of top topics

        Returns:
            List of trending topics
        """
        # Extract keywords from posts
        all_words = []

        for post in posts:
            words = self._extract_keywords(post.content)
            all_words.extend(words)

        # Count word frequency
        word_counts = Counter(all_words)

        # Filter common travel words and get top topics
        travel_stopwords = {
            "place", "go", "went", "see", "saw", "did", "get", "got",
            "one", "would", "could", "much", "really", "also", "even",
        }

        trending = []

        for word, count in word_counts.most_common(top_n * 3):
            word_lower = word.lower()

            if len(word) < 3 or word_lower in travel_stopwords:
                continue

            trending.append({
                "topic": word,
                "mentions": count,
                "recent_mentions": self._count_recent_mentions(posts, word),
            })

            if len(trending) >= top_n:
                break

        return trending

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords from text.

        Args:
            text: Text to extract from

        Returns:
            List of keywords
        """
        import re

        # Extract words
        words = re.findall(r"\b[A-Z][a-z]+\b", text)

        return words

    def _count_recent_mentions(
        self,
        posts: list[SocialPost],
        keyword: str,
        days: int = 7,
    ) -> int:
        """Count recent mentions of keyword.

        Args:
            posts: List of posts
            keyword: Keyword to count
            days: Number of days to look back

        Returns:
            Mention count
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        keyword_lower = keyword.lower()

        count = 0

        for post in posts:
            if post.timestamp < cutoff:
                continue

            if keyword_lower in post.content.lower():
                count += 1

        return count

    def detect_emerging_trends(
        self,
        posts: list[SocialPost],
        days: int = 3,
    ) -> list[dict[str, Any]]:
        """Detect emerging trends from recent posts.

        Args:
            posts: List of posts
            days: Number of days to analyze

        Returns:
            List of emerging trends
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        recent_posts = [p for p in posts if p.timestamp >= cutoff]

        if not recent_posts:
            return []

        # Get topics from recent posts
        recent_topics = self.extract_trending_topics(recent_posts, top_n=20)

        emerging = []

        for topic in recent_topics:
            # Compare with overall frequency
            overall_mentions = sum(
                1 for p in posts
                if topic["topic"].lower() in p.content.lower()
            )

            recent_ratio = (
                topic["recent_mentions"] / overall_mentions
                if overall_mentions > 0 else 0
            )

            # If recent mentions are disproportionately high, it's emerging
            if recent_ratio > 0.3 and topic["recent_mentions"] >= 3:
                emerging.append({
                    **topic,
                    "emergence_score": recent_ratio,
                })

        emerging.sort(key=lambda t: t["emergence_score"], reverse=True)

        return emerging[:10]


class SocialInsightExtractor:
    """Extract travel insights from social data."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
    ) -> None:
        """Initialize insight extractor.

        Args:
            llm_service: Optional LLM service
        """
        self.llm_service = llm_service or LLMService()
        self.sentiment_analyzer = SentimentAnalyzer(llm_service)
        self.trend_analyzer = TrendAnalyzer()

    async def extract_insights(
        self,
        posts: list[SocialPost],
        location: str | None = None,
    ) -> dict[str, Any]:
        """Extract insights from social posts.

        Args:
            posts: List of social posts
            location: Optional location context

        Returns:
            Extracted insights
        """
        insights = {
            "total_posts": len(posts),
            "platforms": self._count_by_platform(posts),
            "time_range": self._get_time_range(posts),
            "sentiment_summary": {},
            "trending_topics": [],
            "top_recommendations": [],
            "warnings": [],
            "location": location,
        }

        if not posts:
            return insights

        # Analyze sentiment
        sentiment_analyses = await self.sentiment_analyzer.analyze_batch(posts[:50])

        # Summarize sentiment
        sentiment_counts = Counter(
            a["sentiment"] for a in sentiment_analyses
        )

        insights["sentiment_summary"] = {
            "positive": sentiment_counts.get("positive", 0),
            "neutral": sentiment_counts.get("neutral", 0),
            "negative": sentiment_counts.get("negative", 0),
            "avg_confidence": sum(
                a.get("confidence", 0.5) for a in sentiment_analyses
            ) / len(sentiment_analyses) if sentiment_analyses else 0.5,
        }

        # Extract trending topics
        insights["trending_topics"] = self.trend_analyzer.extract_trending_topics(
            posts[:100],
            top_n=10,
        )

        # Detect emerging trends
        insights["emerging_trends"] = self.trend_analyzer.detect_emerging_trends(
            posts[:100],
        )

        # Extract top recommendations
        insights["top_recommendations"] = await self._extract_recommendations(
            posts,
            sentiment_analyses,
        )

        # Extract warnings
        insights["warnings"] = await self._extract_warnings(
            posts,
            sentiment_analyses,
        )

        return insights

    def _count_by_platform(self, posts: list[SocialPost]) -> dict[str, int]:
        """Count posts by platform.

        Args:
            posts: List of posts

        Returns:
            Platform counts
        """
        counts = Counter(p.platform for p in posts)
        return dict(counts)

    def _get_time_range(self, posts: list[SocialPost]) -> dict[str, str]:
        """Get time range of posts.

        Args:
            posts: List of posts

        Returns:
            Time range
        """
        if not posts:
            return {}

        timestamps = [p.timestamp for p in posts]

        return {
            "earliest": min(timestamps).isoformat(),
            "latest": max(timestamps).isoformat(),
        }

    async def _extract_recommendations(
        self,
        posts: list[SocialPost],
        sentiment_analyses: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract top recommendations.

        Args:
            posts: List of posts
            sentiment_analyses: Sentiment analyses

        Returns:
            Top recommendations
        """
        recommendations = []

        for post, analysis in zip(posts, sentiment_analyses):
            if analysis.get("sentiment") == "positive" and analysis.get("confidence", 0) > 0.6:
                recommendations.append({
                    "content": post.content[:200],
                    "source": post.platform,
                    "author": post.author,
                    "timestamp": post.timestamp.isoformat(),
                    "confidence": analysis.get("confidence", 0.5),
                    "url": post.metadata.get("url", ""),
                })

        recommendations.sort(key=lambda r: r["confidence"], reverse=True)

        return recommendations[:10]

    async def _extract_warnings(
        self,
        posts: list[SocialPost],
        sentiment_analyses: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract warnings from negative posts.

        Args:
            posts: List of posts
            sentiment_analyses: Sentiment analyses

        Returns:
            Warnings
        """
        warnings = []

        for post, analysis in zip(posts, sentiment_analyses):
            if analysis.get("sentiment") == "negative" and analysis.get("confidence", 0) > 0.5:
                warnings.append({
                    "content": post.content[:200],
                    "source": post.platform,
                    "author": post.author,
                    "timestamp": post.timestamp.isoformat(),
                    "url": post.metadata.get("url", ""),
                })

        warnings.sort(key=lambda w: w["timestamp"], reverse=True)

        return warnings[:5]


# Global instances
sentiment_analyzer = SentimentAnalyzer()
trend_analyzer = TrendAnalyzer()
insight_extractor = SocialInsightExtractor()


def get_sentiment_analyzer() -> SentimentAnalyzer:
    """Get sentiment analyzer instance.

    Returns:
        Sentiment analyzer instance
    """
    return sentiment_analyzer


def get_trend_analyzer() -> TrendAnalyzer:
    """Get trend analyzer instance.

    Returns:
        Trend analyzer instance
    """
    return trend_analyzer


def get_insight_extractor() -> SocialInsightExtractor:
    """Get insight extractor instance.

    Returns:
        Insight extractor instance
    """
    return insight_extractor
