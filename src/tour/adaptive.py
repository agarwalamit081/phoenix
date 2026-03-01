"""Adaptive learning module for optimizing tour experiences."""

import asyncio
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """Types of user feedback."""

    CONTENT_HELPFUL = "content_helpful"
    CONTENT_TOO_LONG = "content_too_long"
    CONTENT_TOO_SHORT = "content_too_short"
    CONTENT_BORING = "content_boring"
    PACE_TOO_FAST = "pace_too_fast"
    PACE_TOO_SLOW = "pace_too_slow"
    ROUTE_TOO_LONG = "route_too_long"
    ROUTE_TOO_SHORT = "route_too_short"
    WANT_MORE_INFO = "want_more_info"
    WANT_LESS_INFO = "want_less_info"


class EngagementLevel(str, Enum):
    """User engagement levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class UserBehavior:
    """Recorded user behavior during tour."""

    behavior_type: str
    timestamp: datetime
    tour_id: str
    poi_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class UserFeedback:
    """User feedback on tour experience."""

    feedback_type: FeedbackType
    rating: int | None = None  # 1-5 scale
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tour_id: str = ""
    poi_id: str | None = None
    content_id: str | None = None
    comment: str | None = None


@dataclass
class AdaptiveParameters:
    """Adaptive parameters for tour customization."""

    preferred_content_length: str = "medium"  # short, medium, long
    preferred_pace: str = "medium"  # slow, medium, fast
    preferred_content_depth: str = "medium"  # basic, detailed, expert
    interests: list[str] = field(default_factory=list)
    avoided_topics: list[str] = field(default_factory=list)
    preferred_stop_duration_minutes: int = 30
    flexibility_score: float = 0.5  # 0.0 = strict, 1.0 = flexible
    social_preference: str = "neutral"  # solo, small_group, large_group, neutral
    learning_style: str = "visual"  # visual, auditory, kinesthetic, mixed

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "preferred_content_length": self.preferred_content_length,
            "preferred_pace": self.preferred_pace,
            "preferred_content_depth": self.preferred_content_depth,
            "interests": self.interests,
            "avoided_topics": self.avoided_topics,
            "preferred_stop_duration_minutes": self.preferred_stop_duration_minutes,
            "flexibility_score": self.flexibility_score,
            "social_preference": self.social_preference,
            "learning_style": self.learning_style,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AdaptiveParameters":
        """Create from dictionary.

        Args:
            data: Dictionary data

        Returns:
            Adaptive parameters instance
        """
        return cls(
            preferred_content_length=data.get("preferred_content_length", "medium"),
            preferred_pace=data.get("preferred_pace", "medium"),
            preferred_content_depth=data.get("preferred_content_depth", "medium"),
            interests=data.get("interests", []),
            avoided_topics=data.get("avoided_topics", []),
            preferred_stop_duration_minutes=data.get("preferred_stop_duration_minutes", 30),
            flexibility_score=data.get("flexibility_score", 0.5),
            social_preference=data.get("social_preference", "neutral"),
            learning_style=data.get("learning_style", "visual"),
        )


class AdaptiveLearningEngine:
    """Learn from user behavior to optimize tour experience."""

    def __init__(self) -> None:
        """Initialize adaptive learning engine."""
        self._behaviors: dict[uuid.UUID, list[UserBehavior]] = defaultdict(list)
        self._feedback: dict[uuid.UUID, list[UserFeedback]] = defaultdict(list)
        self._parameters: dict[uuid.UUID, AdaptiveParameters] = {}

    async def record_behavior(
        self,
        user_id: uuid.UUID,
        behavior_type: str,
        tour_id: str,
        poi_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Record user behavior.

        Args:
            user_id: User ID
            behavior_type: Type of behavior
            tour_id: Tour ID
            poi_id: Optional POI ID
            data: Additional behavior data
        """
        behavior = UserBehavior(
            behavior_type=behavior_type,
            timestamp=datetime.now(timezone.utc),
            tour_id=tour_id,
            poi_id=poi_id,
            data=data or {},
        )

        self._behaviors[user_id].append(behavior)

        # Keep only recent behaviors (last 100)
        if len(self._behaviors[user_id]) > 100:
            self._behaviors[user_id] = self._behaviors[user_id][-100:]

        logger.debug(f"Recorded behavior {behavior_type} for user {user_id}")

    async def record_feedback(
        self,
        user_id: uuid.UUID,
        feedback_type: FeedbackType,
        tour_id: str,
        rating: int | None = None,
        poi_id: str | None = None,
        content_id: str | None = None,
        comment: str | None = None,
    ) -> None:
        """Record user feedback.

        Args:
            user_id: User ID
            feedback_type: Type of feedback
            tour_id: Tour ID
            rating: Optional rating (1-5)
            poi_id: Optional POI ID
            content_id: Optional content ID
            comment: Optional comment
        """
        feedback = UserFeedback(
            feedback_type=feedback_type,
            rating=rating,
            timestamp=datetime.now(timezone.utc),
            tour_id=tour_id,
            poi_id=poi_id,
            content_id=content_id,
            comment=comment,
        )

        self._feedback[user_id].append(feedback)

        # Trigger parameter update
        await self._update_parameters(user_id)

        logger.debug(f"Recorded feedback {feedback_type} for user {user_id}")

    async def get_user_parameters(
        self,
        user_id: uuid.UUID,
    ) -> AdaptiveParameters:
        """Get adaptive parameters for a user.

        Args:
            user_id: User ID

        Returns:
            Adaptive parameters
        """
        if user_id not in self._parameters:
            # Initialize with defaults
            self._parameters[user_id] = AdaptiveParameters()

        return self._parameters[user_id]

    async def calculate_engagement_level(
        self,
        user_id: uuid.UUID,
        tour_id: str,
    ) -> EngagementLevel:
        """Calculate user engagement level.

        Args:
            user_id: User ID
            tour_id: Tour ID

        Returns:
            Engagement level
        """
        behaviors = self._behaviors.get(user_id, [])

        # Filter for this tour
        tour_behaviors = [
            b for b in behaviors
            if b.tour_id == tour_id
        ]

        if not tour_behaviors:
            return EngagementLevel.MEDIUM

        # Count positive and negative engagement signals
        positive_signals = 0
        negative_signals = 0

        for behavior in tour_behaviors:
            if behavior.behavior_type in (
                "content_completed",
                "poi_reached",
                "photo_taken",
                "question_asked",
                "content_shared",
            ):
                positive_signals += 1
            elif behavior.behavior_type in (
                "content_skipped",
                "tour_paused",
                "poi_skipped",
                "left_early",
            ):
                negative_signals += 1

        total_signals = positive_signals + negative_signals
        if total_signals == 0:
            return EngagementLevel.MEDIUM

        engagement_ratio = positive_signals / total_signals

        if engagement_ratio > 0.7:
            return EngagementLevel.HIGH
        elif engagement_ratio < 0.3:
            return EngagementLevel.LOW
        else:
            return EngagementLevel.MEDIUM

    async def recommend_pace_adjustment(
        self,
        user_id: uuid.UUID,
        current_pace: str,
    ) -> tuple[str, float]:
        """Recommend pace adjustment.

        Args:
            user_id: User ID
            current_pace: Current pace setting

        Returns:
            Tuple of (recommended_pace, confidence)
        """
        behaviors = self._behaviors.get(user_id, [])
        feedback = self._feedback.get(user_id, [])

        # Count pace-related signals
        pace_too_fast = sum(
            1 for f in feedback
            if f.feedback_type == FeedbackType.PACE_TOO_FAST
        )
        pace_too_slow = sum(
            1 for f in feedback
            if f.feedback_type == FeedbackType.PACE_TOO_SLOW
        )

        # Analyze time spent at POIs
        time_behaviors = [
            b for b in behaviors
            if b.behavior_type == "poi_duration" and b.data.get("duration_seconds")
        ]

        if time_behaviors:
            avg_duration = sum(
                b.data["duration_seconds"] for b in time_behaviors
            ) / len(time_behaviors)

            # If user spends more than 45 minutes per POI, prefer slower pace
            if avg_duration > 2700:
                pace_too_slow += 1
            # If user spends less than 15 minutes per POI, prefer faster pace
            elif avg_duration < 900:
                pace_too_fast += 1

        if pace_too_fast > pace_too_slow:
            return "slow", min(0.9, 0.5 + pace_too_fast * 0.1)
        elif pace_too_slow > pace_too_fast:
            return "fast", min(0.9, 0.5 + pace_too_slow * 0.1)

        return current_pace, 0.5

    async def recommend_content_length(
        self,
        user_id: uuid.UUID,
        poi_category: str | None = None,
    ) -> str:
        """Recommend content length for user.

        Args:
            user_id: User ID
            poi_category: Optional POI category

        Returns:
            Recommended content length
        """
        feedback = self._feedback.get(user_id, [])

        too_long = sum(
            1 for f in feedback
            if f.feedback_type == FeedbackType.CONTENT_TOO_LONG
        )
        too_short = sum(
            1 for f in feedback
            if f.feedback_type == FeedbackType.CONTENT_TOO_SHORT
        )
        boring = sum(
            1 for f in feedback
            if f.feedback_type == FeedbackType.CONTENT_BORING
        )

        if too_long > boring + too_short:
            return "short"
        elif too_short + boring > too_long:
            return "long"

        return "medium"

    async def extract_interests(
        self,
        user_id: uuid.UUID,
    ) -> list[str]:
        """Extract user interests from behavior and feedback.

        Args:
            user_id: User ID

        Returns:
            List of interests
        """
        behaviors = self._behaviors.get(user_id, [])
        feedback = self._feedback.get(user_id, [])

        interests = []

        # Extract from behaviors
        for behavior in behaviors:
            if behavior.behavior_type == "photo_taken":
                category = behavior.data.get("poi_category")
                if category and category not in interests:
                    interests.append(category)
            elif behavior.behavior_type == "question_asked":
                topic = behavior.data.get("topic")
                if topic and topic not in interests:
                    interests.append(topic)

        # Extract from positive feedback
        for fb in feedback:
            if fb.rating and fb.rating >= 4:
                poi_category = fb.data.get("poi_category") if hasattr(fb, "data") else None
                if poi_category and poi_category not in interests:
                    interests.append(poi_category)

        return interests[:10]  # Limit to top 10

    async def should_suggest_alternative(
        self,
        user_id: uuid.UUID,
        tour_id: str,
    ) -> tuple[bool, str | None]:
        """Determine if should suggest alternative route.

        Args:
            user_id: User ID
            tour_id: Tour ID

        Returns:
            Tuple of (should_suggest, reason)
        """
        behaviors = self._behaviors.get(user_id, [])
        feedback = self._feedback.get(user_id, [])

        # Check for signs of dissatisfaction
        skipped_pois = sum(
            1 for b in behaviors
            if b.behavior_type == "poi_skipped" and b.tour_id == tour_id
        )

        left_early = any(
            b.behavior_type == "left_early" and b.tour_id == tour_id
            for b in behaviors
        )

        negative_feedback = sum(
            1 for f in feedback
            if f.tour_id == tour_id and f.rating and f.rating <= 2
        )

        if skipped_pois >= 2:
            return True, "You've skipped several points of interest"

        if left_early:
            return True, "You left the tour early last time"

        if negative_feedback >= 2:
            return True, "Your feedback suggests this wasn't the right fit"

        return False, None

    async def get_personalization_insights(
        self,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Get insights about user for personalization.

        Args:
            user_id: User ID

        Returns:
            Personalization insights
        """
        parameters = await self.get_user_parameters(user_id)
        engagement = await self.calculate_engagement_level(user_id, "")
        recommended_pace, pace_confidence = await self.recommend_pace_adjustment(
            user_id,
            parameters.preferred_pace,
        )
        content_length = await self.recommend_content_length(user_id)
        interests = await self.extract_interests(user_id)

        return {
            "parameters": parameters.to_dict(),
            "engagement_level": engagement.value,
            "recommended_pace": recommended_pace,
            "pace_confidence": pace_confidence,
            "recommended_content_length": content_length,
            "interests": interests,
            "total_behaviors": len(self._behaviors.get(user_id, [])),
            "total_feedback": len(self._feedback.get(user_id, [])),
        }

    async def _update_parameters(self, user_id: uuid.UUID) -> None:
        """Update adaptive parameters based on feedback.

        Args:
            user_id: User ID
        """
        feedback_list = self._feedback.get(user_id, [])

        if user_id not in self._parameters:
            self._parameters[user_id] = AdaptiveParameters()

        params = self._parameters[user_id]

        # Update content length preference
        too_long = sum(
            1 for f in feedback_list[-20:]  # Last 20 feedbacks
            if f.feedback_type == FeedbackType.CONTENT_TOO_LONG
        )
        too_short = sum(
            1 for f in feedback_list[-20:]
            if f.feedback_type == FeedbackType.CONTENT_TOO_SHORT
        )

        if too_long > too_short + 2:
            params.preferred_content_length = "short"
        elif too_short > too_long + 2:
            params.preferred_content_length = "long"

        # Update pace preference
        pace_fast = sum(
            1 for f in feedback_list[-20:]
            if f.feedback_type == FeedbackType.PACE_TOO_FAST
        )
        pace_slow = sum(
            1 for f in feedback_list[-20:]
            if f.feedback_type == FeedbackType.PACE_TOO_SLOW
        )

        if pace_fast > pace_slow + 2:
            params.preferred_pace = "slow"
        elif pace_slow > pace_fast + 2:
            params.preferred_pace = "fast"

        # Update interests
        params.interests = await self.extract_interests(user_id)

    async def reset_user_data(self, user_id: uuid.UUID) -> None:
        """Reset all learning data for a user.

        Args:
            user_id: User ID
        """
        if user_id in self._behaviors:
            del self._behaviors[user_id]

        if user_id in self._feedback:
            del self._feedback[user_id]

        if user_id in self._parameters:
            del self._parameters[user_id]

        logger.info(f"Reset learning data for user {user_id}")


# Global instance
learning_engine = AdaptiveLearningEngine()


def get_learning_engine() -> AdaptiveLearningEngine:
    """Get global adaptive learning engine instance.

    Returns:
        Adaptive learning engine instance
    """
    return learning_engine
