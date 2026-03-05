"""Social data collector for gathering travel insights from social platforms."""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterable
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class SocialPost:
    """Represents a social media post."""

    def __init__(
        self,
        platform: str,
        post_id: str,
        content: str,
        author: str,
        timestamp: datetime,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Initialize social post.

        Args:
            platform: Platform name
            post_id: Post ID
            content: Post content
            author: Author username
            timestamp: Post timestamp
            metadata: Optional metadata
        """
        self.platform = platform
        self.post_id = post_id
        self.content = content
        self.author = author
        self.timestamp = timestamp
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "platform": self.platform,
            "post_id": self.post_id,
            "content": self.content,
            "author": self.author,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class BaseSocialCollector(ABC):
    """Base class for social media collectors."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = 30,
    ) -> None:
        """Initialize collector.

        Args:
            api_key: Optional API key
            timeout: Request timeout
        """
        self.api_key = api_key
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    @abstractmethod
    async def search(
        self,
        query: str,
        location: str | None = None,
        limit: int = 100,
    ) -> list[SocialPost]:
        """Search for posts.

        Args:
            query: Search query
            location: Optional location filter
            limit: Maximum results

        Returns:
            List of social posts
        """
        pass

    @abstractmethod
    async def get_trending(
        self,
        location: str | None = None,
        limit: int = 50,
    ) -> list[SocialPost]:
        """Get trending posts.

        Args:
            location: Optional location filter
            limit: Maximum results

        Returns:
            List of trending posts
        """
        pass


class RedditCollector(BaseSocialCollector):
    """Collector for Reddit travel-related content."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = 30,
    ) -> None:
        """Initialize Reddit collector.

        Args:
            api_key: Reddit API key (app credentials)
            timeout: Request timeout
        """
        super().__init__(api_key, timeout)
        self.base_url = "https://www.reddit.com"

    async def search(
        self,
        query: str,
        location: str | None = None,
        limit: int = 100,
    ) -> list[SocialPost]:
        """Search Reddit for travel content.

        Args:
            query: Search query
            location: Optional location
            limit: Maximum results

        Returns:
            List of posts
        """
        posts = []

        try:
            # Search in travel subreddits
            subreddits = [
                "travel",
                "travel",
                "solotravel",
                "budget_travel",
                "backpacking",
            ]

            search_query = query
            if location:
                search_query = f"{query} {location}"

            for subreddit in subreddits:
                try:
                    url = f"{self.base_url}/r/{subreddit}/search.json"
                    params = {
                        "q": search_query,
                        "restrict_sr": "1",
                        "limit": min(limit // len(subreddits) + 10, 100),
                    }

                    response = await self.client.get(url, params=params)
                    response.raise_for_status()

                    data = response.json()

                    for child in data.get("data", {}).get("children", []):
                        post_data = child.get("data", {})

                        post = SocialPost(
                            platform="reddit",
                            post_id=post_data.get("id", ""),
                            content=post_data.get("selftext", post_data.get("title", "")),
                            author=post_data.get("author", ""),
                            timestamp=datetime.fromtimestamp(
                                post_data.get("created_utc", 0),
                                tz=timezone.utc,
                            ),
                            metadata={
                                "subreddit": subreddit,
                                "title": post_data.get("title", ""),
                                "score": post_data.get("score", 0),
                                "num_comments": post_data.get("num_comments", 0),
                                "url": f"{self.base_url}{post_data.get('permalink', '')}",
                            },
                        )

                        posts.append(post)

                except Exception as e:
                    logger.warning(f"Failed to search r/{subreddit}: {e}")
                    continue

            # Sort by score
            posts.sort(key=lambda p: p.metadata.get("score", 0), reverse=True)

        except Exception as e:
            logger.error(f"Reddit search failed: {e}")

        return posts[:limit]

    async def get_trending(
        self,
        location: str | None = None,
        limit: int = 50,
    ) -> list[SocialPost]:
        """Get trending travel posts.

        Args:
            location: Optional location
            limit: Maximum results

        Returns:
            List of trending posts
        """
        posts = []

        try:
            subreddits = ["travel", "solotravel", "budget_travel"]

            for subreddit in subreddits:
                try:
                    url = f"{self.base_url}/r/{subreddit}/hot.json"
                    params = {"limit": limit // len(subreddits) + 10}

                    response = await self.client.get(url, params=params)
                    response.raise_for_status()

                    data = response.json()

                    for child in data.get("data", {}).get("children", []):
                        post_data = child.get("data", {})

                        # Filter by location if specified
                        if location:
                            title = post_data.get("title", "").lower()
                            content = post_data.get("selftext", "").lower()
                            if location.lower() not in title and location.lower() not in content:
                                continue

                        post = SocialPost(
                            platform="reddit",
                            post_id=post_data.get("id", ""),
                            content=post_data.get("selftext", post_data.get("title", "")),
                            author=post_data.get("author", ""),
                            timestamp=datetime.fromtimestamp(
                                post_data.get("created_utc", 0),
                                tz=timezone.utc,
                            ),
                            metadata={
                                "subreddit": subreddit,
                                "title": post_data.get("title", ""),
                                "score": post_data.get("score", 0),
                                "num_comments": post_data.get("num_comments", 0),
                                "url": f"{self.base_url}{post_data.get('permalink', '')}",
                            },
                        )

                        posts.append(post)

                except Exception as e:
                    logger.warning(f"Failed to get hot posts from r/{subreddit}: {e}")
                    continue

            posts.sort(key=lambda p: p.metadata.get("score", 0), reverse=True)

        except Exception as e:
            logger.error(f"Reddit trending failed: {e}")

        return posts[:limit]


class GoogleMapsCollector(BaseSocialCollector):
    """Collector for Google Maps reviews."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = 30,
    ) -> None:
        """Initialize Google Maps collector.

        Args:
            api_key: Google Places API key
            timeout: Request timeout
        """
        super().__init__(api_key, timeout)
        self.base_url = "https://maps.googleapis.com/maps/api/place"

    async def search(
        self,
        query: str,
        location: str | None = None,
        limit: int = 100,
    ) -> list[SocialPost]:
        """Search Google Maps for reviews.

        Args:
            query: Search query
            location: Optional location (lat,lng)
            limit: Maximum results

        Returns:
            List of reviews as posts
        """
        posts = []

        if not self.api_key:
            logger.warning("Google Maps API key not provided")
            return posts

        try:
            # Search for places
            search_url = f"{self.base_url}/textsearch/json"
            params = {
                "query": query,
                "key": self.api_key,
            }

            if location:
                params["location"] = location
                params["radius"] = 10000

            response = await self.client.get(search_url, params=params)
            response.raise_for_status()

            data = response.json()

            for place in data.get("results", [])[:limit]:
                place_id = place.get("place_id")

                if place_id:
                    # Get reviews for this place
                    reviews = await self._get_place_reviews(place_id)

                    for review in reviews:
                        post = SocialPost(
                            platform="google_maps",
                            post_id=place_id,
                            content=review.get("text", ""),
                            author=review.get("author_name", ""),
                            timestamp=datetime.fromtimestamp(
                                review.get("time", 0),
                                tz=timezone.utc,
                            ),
                            metadata={
                                "place_name": place.get("name"),
                                "rating": review.get("rating"),
                                "place_id": place_id,
                                "rating_type": "review",
                            },
                        )

                        posts.append(post)

        except Exception as e:
            logger.error(f"Google Maps search failed: {e}")

        return posts[:limit]

    async def _get_place_reviews(self, place_id: str) -> list[dict[str, Any]]:
        """Get reviews for a place.

        Args:
            place_id: Place ID

        Returns:
            List of reviews
        """
        try:
            url = f"{self.base_url}/details/json"
            params = {
                "place_id": place_id,
                "fields": "review",
                "key": self.api_key,
            }

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            return data.get("result", {}).get("reviews", [])

        except Exception as e:
            logger.error(f"Failed to get reviews for place {place_id}: {e}")
            return []

    async def get_trending(
        self,
        location: str | None = None,
        limit: int = 50,
    ) -> list[SocialPost]:
        """Get trending reviews.

        Args:
            location: Optional location
            limit: Maximum results

        Returns:
            List of trending reviews
        """
        # For Google Maps, trending = highly rated recent reviews
        query = "popular attractions restaurants" if location else "popular places"

        posts = await self.search(query, location, limit)

        # Sort by rating and recency
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)

        recent_posts = [
            p for p in posts
            if p.timestamp > week_ago
        ]

        recent_posts.sort(
            key=lambda p: (
                p.metadata.get("rating", 0),
                p.timestamp,
            ),
            reverse=True,
        )

        return recent_posts[:limit]


class SocialCollector:
    """Unified social data collector."""

    def __init__(
        self,
        reddit_api_key: str | None = None,
        google_maps_api_key: str | None = None,
    ) -> None:
        """Initialize social collector.

        Args:
            reddit_api_key: Optional Reddit API key
            google_maps_api_key: Google Places API key
        """
        self.reddit = RedditCollector(reddit_api_key) if reddit_api_key else None
        self.google_maps = GoogleMapsCollector(google_maps_api_key) if google_maps_api_key else None

    async def search_all(
        self,
        query: str,
        location: str | None = None,
        limit: int = 100,
    ) -> list[SocialPost]:
        """Search all platforms.

        Args:
            query: Search query
            location: Optional location
            limit: Maximum results per platform

        Returns:
            Combined list of posts
        """
        results = []

        tasks = []

        if self.reddit:
            tasks.append(self.reddit.search(query, location, limit))

        if self.google_maps:
            tasks.append(self.google_maps.search(query, location, limit))

        if tasks:
            platform_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in platform_results:
                if isinstance(result, Exception):
                    logger.error(f"Platform search failed: {result}")
                elif result:
                    results.extend(result)

        # Sort by timestamp (most recent first)
        results.sort(key=lambda p: p.timestamp, reverse=True)

        return results

    async def get_trending_all(
        self,
        location: str | None = None,
        limit: int = 50,
    ) -> list[SocialPost]:
        """Get trending from all platforms.

        Args:
            location: Optional location
            limit: Maximum results per platform

        Returns:
            Combined trending posts
        """
        results = []

        tasks = []

        if self.reddit:
            tasks.append(self.reddit.get_trending(location, limit))

        if self.google_maps:
            tasks.append(self.google_maps.get_trending(location, limit))

        if tasks:
            platform_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in platform_results:
                if isinstance(result, Exception):
                    logger.error(f"Platform trending failed: {result}")
                elif result:
                    results.extend(result)

        # Sort by timestamp
        results.sort(key=lambda p: p.timestamp, reverse=True)

        return results

    async def close(self) -> None:
        """Close all collectors."""
        if self.reddit:
            await self.reddit.close()
        if self.google_maps:
            await self.google_maps.close()

    async def __aenter__(self) -> "SocialCollector":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()


# Global instance
social_collector = SocialCollector()


def get_social_collector() -> SocialCollector:
    """Get social collector instance.

    Returns:
        Social collector instance
    """
    return social_collector
