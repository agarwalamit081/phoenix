"""Unit tests for social intelligence modules."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.social.collector import SocialPost, RedditCollector, GoogleMapsCollector
from src.social.analyzer import SentimentAnalyzer, TrendAnalyzer, SocialInsightExtractor
from src.social.cache import SocialCache, SocialSearchCache


@pytest.fixture
def sample_posts():
    """Create sample social posts."""
    return [
        SocialPost(
            platform="reddit",
            post_id="post_1",
            content="Central Park is amazing! Best place in NYC.",
            author="traveler123",
            timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
            metadata={"subreddit": "travel", "score": 100},
        ),
        SocialPost(
            platform="reddit",
            post_id="post_2",
            content="Avoid Times Square, too crowded and expensive.",
            author="local_nyc",
            timestamp=datetime.now(timezone.utc) - timedelta(hours=5),
            metadata={"subreddit": "travel", "score": 50},
        ),
        SocialPost(
            platform="google_maps",
            post_id="review_1",
            content="Great food at this restaurant!",
            author="foodie456",
            timestamp=datetime.now(timezone.utc) - timedelta(hours=1),
            metadata={"place_name": "Joe's Pizza", "rating": 5},
        ),
    ]


class TestSocialPost:
    """Test SocialPost."""

    def test_to_dict(self):
        """Test converting to dictionary."""
        post = SocialPost(
            platform="reddit",
            post_id="test_1",
            content="Test content",
            author="test_user",
            timestamp=datetime.now(timezone.utc),
        )

        post_dict = post.to_dict()

        assert post_dict["platform"] == "reddit"
        assert post_dict["post_id"] == "test_1"
        assert post_dict["content"] == "Test content"


class TestSentimentAnalyzer:
    """Test sentiment analyzer."""

    @pytest.mark.asyncio
    async def test_analyze_sentiment(self):
        """Test sentiment analysis."""
        analyzer = SentimentAnalyzer()

        with patch.object(analyzer.llm_service, 'chat_completion', return_value={"content": '{"sentiment": "positive", "confidence": 0.8, "key_topics": ["food", "service"], "emotional_tone": "enthusiastic"}'}):
            result = await analyzer.analyze_sentiment("I love this place! Amazing food!")

            assert result["sentiment"] == "positive"
            assert result["confidence"] == 0.8

    @pytest.mark.asyncio
    async def test_fallback_sentiment_analysis(self):
        """Test fallback sentiment analysis."""
        analyzer = SentimentAnalyzer()

        result = analyzer._fallback_sentiment_analysis("This place is terrible and awful")

        assert result["sentiment"] == "negative"

    @pytest.mark.asyncio
    async def test_analyze_batch(self, sample_posts):
        """Test batch sentiment analysis."""
        analyzer = SentimentAnalyzer()

        with patch.object(analyzer, 'analyze_sentiment', return_value={"sentiment": "positive", "confidence": 0.7}):
            results = await analyzer.analyze_batch(sample_posts)

            assert len(results) == len(sample_posts)


class TestTrendAnalyzer:
    """Test trend analyzer."""

    def test_extract_trending_topics(self, sample_posts):
        """Test extracting trending topics."""
        analyzer = TrendAnalyzer()

        trending = analyzer.extract_trending_topics(sample_posts, top_n=5)

        assert isinstance(trending, list)
        assert len(trending) <= 5

    def test_detect_emerging_trends(self, sample_posts):
        """Test detecting emerging trends."""
        analyzer = TrendAnalyzer()

        emerging = analyzer.detect_emerging_trends(sample_posts, days=1)

        assert isinstance(emerging, list)


class TestSocialInsightExtractor:
    """Test social insight extractor."""

    @pytest.mark.asyncio
    async def test_extract_insights(self, sample_posts):
        """Test extracting insights."""
        extractor = SocialInsightExtractor()

        with patch.object(extractor.sentiment_analyzer, 'analyze_batch', return_value=[
            {"sentiment": "positive", "confidence": 0.8},
            {"sentiment": "negative", "confidence": 0.6},
            {"sentiment": "positive", "confidence": 0.9},
        ]):
            insights = await extractor.extract_insights(
                posts=sample_posts,
                location="NYC",
            )

            assert "total_posts" in insights
            assert "sentiment_summary" in insights
            assert "trending_topics" in insights

    @pytest.mark.asyncio
    async def test_extract_insights_empty(self):
        """Test extracting insights with no posts."""
        extractor = SocialInsightExtractor()

        insights = await extractor.extract_insights([])

        assert insights["total_posts"] == 0


class TestSocialCache:
    """Test social cache."""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Test setting and getting cache values."""
        cache = SocialCache()

        await cache.set("test_key", {"data": "test_value"})

        result = await cache.get("test_key")

        assert result is not None
        assert result["data"] == "test_value"

    @pytest.mark.asyncio
    async def test_cache_expiration(self):
        """Test cache entry expiration."""
        cache = SocialCache(default_ttl_seconds=1)

        await cache.set("test_key", {"data": "test_value"})

        # Should be available immediately
        result = await cache.get("test_key")
        assert result is not None

        # Wait for expiration
        import asyncio
        await asyncio.sleep(2)

        # Should be expired
        result = await cache.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test deleting cache entry."""
        cache = SocialCache()

        await cache.set("test_key", {"data": "test_value"})

        deleted = await cache.delete("test_key")

        assert deleted is True

        result = await cache.get("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cleanup_expired(self):
        """Test cleaning up expired entries."""
        cache = SocialCache(default_ttl_seconds=1)

        await cache.set("key1", {"data": "value1"})
        await cache.set("key2", {"data": "value2"})

        import asyncio
        await asyncio.sleep(2)

        removed = await cache.cleanup_expired()

        assert removed == 2

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting cache statistics."""
        cache = SocialCache()

        await cache.set("key1", {"data": "value1"})
        await cache.set("key2", {"data": "value2"})

        # Get value to increment hits
        await cache.get("key1")

        stats = await cache.get_stats()

        assert stats["total_entries"] == 2
        assert stats["total_hits"] == 1


class TestSocialSearchCache:
    """Test search cache."""

    @pytest.mark.asyncio
    async def test_search_cache_operations(self):
        """Test search cache specific operations."""
        cache = SocialSearchCache()

        results = {"posts": ["post1", "post2"]}

        await cache.set_search_results(
            query="NYC attractions",
            results=results,
            location="NYC",
        )

        retrieved = await cache.get_search_results(
            query="NYC attractions",
            location="NYC",
        )

        assert retrieved is not None
        assert retrieved["posts"] == ["post1", "post2"]


class TestRedditCollector:
    """Test Reddit collector."""

    @pytest.mark.asyncio
    async def test_search(self):
        """Test Reddit search."""
        collector = RedditCollector(api_key="test_key")

        with patch.object(collector.client, 'get', return_value=MagicMock(
            raise_for_status=MagicMock(),
            json=lambda: {"data": {"children": [
                {"data": {
                    "id": "test_1",
                    "selftext": "Great place!",
                    "author": "user1",
                    "created_utc": 1609459200,
                    "title": "Test Post",
                    "score": 100,
                    "num_comments": 10,
                    "permalink": "/r/test/comments/test_1",
                }}
            ]}}
        )):
            results = await collector.search("NYC travel", limit=10)

            assert isinstance(results, list)


class TestGoogleMapsCollector:
    """Test Google Maps collector."""

    @pytest.mark.asyncio
    async def test_search(self):
        """Test Google Maps search."""
        collector = GoogleMapsCollector(api_key="test_key")

        with patch.object(collector.client, 'get', return_value=MagicMock(
            raise_for_status=MagicMock(),
            json=lambda: {"results": [
                {"place_id": "test_1", "name": "Test Place"}
            ]}
        )):
            results = await collector.search("restaurants", limit=10)

            assert isinstance(results, list)
