"""Context-aware content delivery for guided tours."""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ContentType(str, Enum):
    """Types of tour content."""

    AUDIO_NARRATION = "audio_narration"
    TEXT_INFO = "text_info"
    IMAGE = "image"
    VIDEO = "video"
    QUIZ = "quiz"
    DIRECTION = "direction"
    WARNING = "warning"
    HISTORICAL_FACT = "historical_fact"
    CULTURAL_NOTE = "cultural_note"
    FUN_FACT = "fun_fact"


class DeliveryTrigger(str, Enum):
    """Content delivery triggers."""

    ON_APPROACH = "on_approach"  # When approaching POI
    ON_ARRIVAL = "on_arrival"  # When at POI
    ON_DEPARTURE = "on_departure"  # When leaving POI
    ON_REQUEST = "on_request"  # User asks for info
    TIME_BASED = "time_based"  # At specific time
    LOCATION_BASED = "location_based"  # At specific location
    PROXIMITY_BASED = "proximity_based"  # Within distance threshold


@dataclass
class ContentItem:
    """A piece of content for tour delivery."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    poi_id: str | None = None
    content_type: ContentType = ContentType.TEXT_INFO
    title: str | None = None
    body: str | None = None
    audio_url: str | None = None
    image_url: str | None = None
    duration_seconds: int | None = None  # For audio/video
    trigger: DeliveryTrigger = DeliveryTrigger.ON_ARRIVAL
    trigger_distance_meters: float | None = None  # For proximity triggers
    language: str = "en"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "id": self.id,
            "poi_id": self.poi_id,
            "content_type": self.content_type.value,
            "title": self.title,
            "body": self.body,
            "audio_url": self.audio_url,
            "image_url": self.image_url,
            "duration_seconds": self.duration_seconds,
            "trigger": self.trigger.value,
            "trigger_distance_meters": self.trigger_distance_meters,
            "language": self.language,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ContentContext:
    """Context for content generation."""

    user_id: uuid.UUID
    tour_id: str
    poi_id: str | None = None
    user_preferences: list[dict[str, Any]] = field(default_factory=list)
    current_location: dict[str, float] | None = None
    time_of_day: str | None = None  # morning, afternoon, evening
    weather_condition: str | None = None
    crowd_level: str | None = None  # low, medium, high
    language: str = "en"
    previous_content_ids: list[str] = field(default_factory=list)
    tour_progress: float = 0.0  # 0.0 to 1.0
    time_at_location_seconds: int = 0


class TourContentGenerator:
    """Generate context-aware content for tours."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
    ) -> None:
        """Initialize content generator.

        Args:
            llm_service: Optional LLM service
        """
        self.llm_service = llm_service or LLMService()
        self._content_cache: dict[str, ContentItem] = {}

    async def generate_poi_content(
        self,
        poi: dict[str, Any],
        context: ContentContext,
        content_type: ContentType = ContentType.AUDIO_NARRATION,
    ) -> ContentItem:
        """Generate content for a POI.

        Args:
            poi: POI data
            context: Content context
            content_type: Type of content to generate

        Returns:
            Generated content item
        """
        poi_id = poi.get("id", "")
        poi_name = poi.get("name", "Unknown")
        poi_description = poi.get("description", "")
        poi_category = poi.get("category", "attraction")

        # Build context for LLM
        context_parts = []

        if context.time_of_day:
            context_parts.append(f"Time of day: {context.time_of_day}")

        if context.weather_condition:
            context_parts.append(f"Weather: {context.weather_condition}")

        if context.crowd_level:
            context_parts.append(f"Crowd level: {context.crowd_level}")

        if context.tour_progress > 0:
            progress_pct = int(context.tour_progress * 100)
            context_parts.append(f"Tour progress: {progress_pct}%")

        context_str = "\n".join(context_parts) if context_parts else "No specific context"

        # Generate content based on type
        if content_type == ContentType.AUDIO_NARRATION:
            prompt = self._get_narration_prompt(
                poi_name,
                poi_description,
                poi_category,
                context_str,
                context.language,
            )
        elif content_type == ContentType.HISTORICAL_FACT:
            prompt = self._get_historical_fact_prompt(
                poi_name,
                poi_description,
                context_str,
                context.language,
            )
        elif content_type == ContentType.CULTURAL_NOTE:
            prompt = self._get_cultural_note_prompt(
                poi_name,
                poi_description,
                context_str,
                context.language,
            )
        elif content_type == ContentType.FUN_FACT:
            prompt = self._get_fun_fact_prompt(
                poi_name,
                poi_description,
                context_str,
                context.language,
            )
        else:
            prompt = self._get_general_info_prompt(
                poi_name,
                poi_description,
                poi_category,
                context_str,
                context.language,
            )

        try:
            response = await self.llm_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an engaging tour guide. Create informative, concise content that enhances the visitor experience.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.8,
                max_tokens=500,
            )

            content_text = response.get("content", "")

            # Parse response
            title = self._extract_title(content_text)
            body = self._extract_body(content_text)

        except Exception as e:
            logger.error(f"Failed to generate content for POI {poi_id}: {e}")
            # Fallback to basic content
            title = poi_name
            body = poi_description or f"Welcome to {poi_name}."

        # Create content item
        content_item = ContentItem(
            poi_id=poi_id,
            content_type=content_type,
            title=title,
            body=body,
            language=context.language,
            metadata={
                "poi_name": poi_name,
                "poi_category": poi_category,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Cache content
        self._content_cache[content_item.id] = content_item

        return content_item

    async def generate_direction_content(
        self,
        from_poi: dict[str, Any],
        to_poi: dict[str, Any],
        distance_meters: float,
        duration_minutes: int,
        context: ContentContext,
    ) -> ContentItem:
        """Generate direction content between POIs.

        Args:
            from_poi: Starting POI
            to_poi: Destination POI
            distance_meters: Distance in meters
            duration_minutes: Walking time in minutes
            context: Content context

        Returns:
            Direction content item
        """
        from_name = from_poi.get("name", "Current location")
        to_name = to_poi.get("name", "Next destination")
        to_category = to_poi.get("category", "attraction")

        prompt = f"""Create brief, friendly directions for walking from {from_name} to {to_name}.

Distance: {distance_meters:.0f} meters
Walking time: {duration_minutes} minutes
Destination type: {to_category}
{f"Context: {context.time_of_day}" if context.time_of_day else ""}

Provide:
1. A friendly heading
2. Brief directions (1-2 sentences)
3. A helpful tip for the walk

Keep it conversational and encouraging."""

        try:
            response = await self.llm_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful tour guide providing walking directions.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.7,
                max_tokens=300,
            )

            content_text = response.get("content", "")
            title = self._extract_title(content_text) or f"Head to {to_name}"
            body = self._extract_body(content_text) or f"Walk {duration_minutes} minutes to reach {to_name}."

        except Exception as e:
            logger.error(f"Failed to generate directions: {e}")
            title = f"Head to {to_name}"
            body = f"It's a {duration_minutes}-minute walk to {to_name}. Enjoy the stroll!"

        content_item = ContentItem(
            content_type=ContentType.DIRECTION,
            title=title,
            body=body,
            language=context.language,
            metadata={
                "from_poi": from_name,
                "to_poi": to_name,
                "distance_meters": distance_meters,
                "duration_minutes": duration_minutes,
            },
        )

        self._content_cache[content_item.id] = content_item

        return content_item

    async def generate_quiz_content(
        self,
        poi: dict[str, Any],
        context: ContentContext,
        difficulty: str = "easy",
    ) -> ContentItem:
        """Generate a quiz question about a POI.

        Args:
            poi: POI data
            difficulty: Quiz difficulty (easy, medium, hard)
            context: Content context

        Returns:
            Quiz content item
        """
        poi_name = poi.get("name", "Unknown")
        poi_description = poi.get("description", "")

        prompt = f"""Create an {difficulty} quiz question about {poi_name}.

Description: {poi_description}

Create a multiple-choice question with:
1. Question text
2. 4 possible answers (A, B, C, D)
3. Correct answer

Make it educational and engaging for tourists."""

        try:
            response = await self.llm_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You create educational quiz questions for tourists.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.8,
                max_tokens=400,
            )

            content_text = response.get("content", "")
            title = f"Quiz: {poi_name}"
            body = content_text

        except Exception as e:
            logger.error(f"Failed to generate quiz: {e}")
            title = f"Quiz: {poi_name}"
            body = "What is this location famous for? (Discuss with your tour guide!)"

        content_item = ContentItem(
            poi_id=poi.get("id"),
            content_type=ContentType.QUIZ,
            title=title,
            body=body,
            language=context.language,
            metadata={
                "poi_name": poi_name,
                "difficulty": difficulty,
            },
        )

        self._content_cache[content_item.id] = content_item

        return content_item

    async def personalize_content(
        self,
        content: ContentItem,
        user_preferences: list[dict[str, Any]],
    ) -> ContentItem:
        """Personalize content based on user preferences.

        Args:
            content: Original content
            user_preferences: User preferences

        Returns:
            Personalized content
        """
        # Extract relevant preferences
        interests = [
            p.get("value")
            for p in user_preferences
            if p.get("preference_type") == "like"
            and p.get("category") == "interest"
        ]

        if not interests:
            return content

        # For now, just add interest tags to metadata
        # In a full implementation, you might regenerate content
        personalized = ContentItem(
            **{k: v for k, v in content.to_dict().items() if k != "metadata"},
            metadata={
                **content.metadata,
                "personalized_interests": interests,
            },
        )

        return personalized

    def get_content(self, content_id: str) -> ContentItem | None:
        """Get cached content by ID.

        Args:
            content_id: Content ID

        Returns:
            Content item or None
        """
        return self._content_cache.get(content_id)

    def _get_narration_prompt(
        self,
        poi_name: str,
        description: str,
        category: str,
        context: str,
        language: str,
    ) -> str:
        """Generate prompt for audio narration.

        Args:
            poi_name: POI name
            description: POI description
            category: POI category
            context: Context information
            language: Content language

        Returns:
            Prompt string
        """
        lang_note = f"Respond in {language}" if language != "en" else ""

        return f"""Create an engaging audio narration (2-3 minutes speaking time) for: {poi_name}

Category: {category}
Description: {description}

Context:
{context}

{lang_note}

Provide:
1. An attention-grabbing opening line
2. 2-3 paragraphs of interesting information
3. A thoughtful closing

Make it conversational and vivid. Include sensory details."""

    def _get_historical_fact_prompt(
        self,
        poi_name: str,
        description: str,
        context: str,
        language: str,
    ) -> str:
        """Generate prompt for historical fact.

        Args:
            poi_name: POI name
            description: POI description
            context: Context information
            language: Content language

        Returns:
            Prompt string
        """
        return f"""Share an interesting historical fact about {poi_name}.

Description: {description}

Keep it to 1-2 sentences. Make it surprising or little-known."""

    def _get_cultural_note_prompt(
        self,
        poi_name: str,
        description: str,
        context: str,
        language: str,
    ) -> str:
        """Generate prompt for cultural note.

        Args:
            poi_name: POI name
            description: POI description
            context: Context information
            language: Content language

        Returns:
            Prompt string
        """
        return f"""Share a cultural insight about {poi_name}.

Description: {description}

Explain local customs, traditions, or cultural significance in 1-2 sentences."""

    def _get_fun_fact_prompt(
        self,
        poi_name: str,
        description: str,
        context: str,
        language: str,
    ) -> str:
        """Generate prompt for fun fact.

        Args:
            poi_name: POI name
            description: POI description
            context: Context information
            language: Content language

        Returns:
            Prompt string
        """
        return f"""Share a fun or surprising fact about {poi_name}.

Description: {description}

Make it entertaining and memorable in 1-2 sentences."""

    def _get_general_info_prompt(
        self,
        poi_name: str,
        description: str,
        category: str,
        context: str,
        language: str,
    ) -> str:
        """Generate prompt for general information.

        Args:
            poi_name: POI name
            description: POI description
            category: POI category
            context: Context information
            language: Content language

        Returns:
            Prompt string
        """
        return f"""Provide brief information about {poi_name}.

Category: {category}
Description: {description}

Keep it to 2-3 sentences."""

    def _extract_title(self, text: str) -> str | None:
        """Extract title from generated content.

        Args:
            text: Generated text

        Returns:
            Extracted title or None
        """
        lines = text.strip().split("\n")
        for line in lines[:3]:
            line = line.strip()
            if line and not line.startswith(("Question:", "A)", "B)", "C)", "D)")):
                # Remove markdown formatting
                line = line.lstrip("#*").strip()
                if line:
                    return line
        return None

    def _extract_body(self, text: str) -> str:
        """Extract body from generated content.

        Args:
            text: Generated text

        Returns:
            Extracted body
        """
        lines = text.strip().split("\n")
        # Skip title line
        if len(lines) > 1:
            return "\n".join(lines[1:]).strip()
        return text


class ContentDeliveryManager:
    """Manages content delivery based on context and triggers."""

    def __init__(
        self,
        generator: TourContentGenerator | None = None,
    ) -> None:
        """Initialize content delivery manager.

        Args:
            generator: Optional content generator
        """
        self.generator = generator or TourContentGenerator()
        self._pending_content: dict[str, list[ContentItem]] = {}  # tour_id -> content items

    async def get_content_for_trigger(
        self,
        tour_id: str,
        poi_id: str,
        trigger: DeliveryTrigger,
        context: ContentContext,
        distance_meters: float | None = None,
    ) -> list[ContentItem]:
        """Get content items that should be delivered for a trigger.

        Args:
            tour_id: Tour ID
            poi_id: POI ID
            trigger: Delivery trigger
            context: Content context
            distance_meters: Distance for proximity triggers

        Returns:
            List of content items to deliver
        """
        pending = self._pending_content.get(tour_id, [])
        to_deliver = []

        for content in pending:
            # Check if content matches trigger
            if content.trigger != trigger:
                continue

            if content.poi_id and content.poi_id != poi_id:
                continue

            # Check proximity distance
            if trigger == DeliveryTrigger.PROXIMITY_BASED:
                if content.trigger_distance_meters is None:
                    continue
                if distance_meters is None:
                    continue
                if distance_meters > content.trigger_distance_meters:
                    continue

            to_deliver.append(content)

        # Remove delivered content from pending
        self._pending_content[tour_id] = [
            c for c in pending
            if c not in to_deliver
        ]

        return to_deliver

    async def queue_content(
        self,
        tour_id: str,
        content: ContentItem,
    ) -> None:
        """Queue content for delivery.

        Args:
            tour_id: Tour ID
            content: Content to queue
        """
        if tour_id not in self._pending_content:
            self._pending_content[tour_id] = []

        self._pending_content[tour_id].append(content)

        logger.debug(
            f"Queued content {content.id} for tour {tour_id}, "
            f"trigger={content.trigger.value}"
        )

    def clear_tour_content(self, tour_id: str) -> None:
        """Clear all pending content for a tour.

        Args:
            tour_id: Tour ID
        """
        if tour_id in self._pending_content:
            del self._pending_content[tour_id]

    def get_pending_count(self, tour_id: str) -> int:
        """Get count of pending content items.

        Args:
            tour_id: Tour ID

        Returns:
            Number of pending items
        """
        return len(self._pending_content.get(tour_id, []))


# Global instances
content_generator = TourContentGenerator()
delivery_manager = ContentDeliveryManager(content_generator)


def get_content_generator() -> TourContentGenerator:
    """Get global content generator instance.

    Returns:
        Content generator instance
    """
    return content_generator


def get_delivery_manager() -> ContentDeliveryManager:
    """Get global delivery manager instance.

    Returns:
        Delivery manager instance
    """
    return delivery_manager
