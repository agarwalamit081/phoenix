"""Chat service for managing conversations and messages."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.logging import logger
from src.core.exceptions import NotFoundError
from src.database.repositories.preference import UserPreferenceRepository
from src.database.repositories.user import UserRepository
from src.services.llm_service import LLMService
from src.services.preference_service import PreferenceService
from src.schemas.chat import (
    ChatMessage,
    ChatResponse,
    ConversationHistory,
    PreferenceExtraction,
)


class ChatService:
    """Service for managing chat conversations."""

    _conversations_store: dict[uuid.UUID, list[ChatMessage]] = {}
    _user_conversations: dict[uuid.UUID, list[uuid.UUID]] = {}

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the chat service.

        Args:
            session: Database session
        """
        self.session = session
        self.llm_service = LLMService()
        self.preference_service = PreferenceService(session)
        self.user_repo = UserRepository(session)
        self.preference_repo = UserPreferenceRepository(session)

        # In-memory conversation storage shared across service instances.
        # In production, this should be persisted to a database.
        self._conversations = ChatService._conversations_store

    async def send_message(
        self,
        user_id: uuid.UUID,
        message: str,
        conversation_id: uuid.UUID | None = None,
        language: str = "en",
        include_preferences: bool = True,
    ) -> ChatResponse:
        """Send a chat message and get a response.

        Args:
            user_id: User ID
            message: User message
            conversation_id: Optional conversation ID for context
            language: Message language
            include_preferences: Whether to include user preferences in context

        Returns:
            Chat response
        """
        # Get user
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", str(user_id))

        # Get or create conversation
        if conversation_id is None:
            conversation_id = uuid.uuid4()
            self._conversations[conversation_id] = []
            ChatService._user_conversations.setdefault(user_id, []).append(conversation_id)

        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []
        if conversation_id not in ChatService._user_conversations.get(user_id, []):
            ChatService._user_conversations.setdefault(user_id, []).append(conversation_id)

        # Add user message to conversation
        user_message = ChatMessage(
            role="user",
            content=message,
            timestamp=datetime.now(),
        )
        self._conversations[conversation_id].append(user_message)

        # Build messages for LLM
        messages = await self._build_context(
            user,
            self._conversations[conversation_id],
            include_preferences,
            language,
        )

        # Generate response
        try:
            llm_response = await self.llm_service.chat_completion(
                messages=messages,
            )

            assistant_message = ChatMessage(
                role="assistant",
                content=llm_response["content"],
                timestamp=datetime.now(),
            )
            self._conversations[conversation_id].append(assistant_message)

            # Extract preferences from conversation
            preferences_detected = await self._extract_preferences_from_conversation(
                user_id,
                conversation_id,
            )

            # Generate suggested actions
            suggested_actions = await self._generate_suggested_actions(
                user_id,
                message,
            )

            response = ChatResponse(
                message_id=uuid.uuid4(),
                role="assistant",
                content=llm_response["content"],
                timestamp=datetime.now(),
                preferences_detected=preferences_detected,
                suggested_actions=suggested_actions,
            )

            logger.info(f"Generated response for user {user_id} in conversation {conversation_id}")
            return response

        except Exception as e:
            logger.error(f"Failed to generate chat response: {e}")
            raise

    async def get_conversation_history(
        self,
        conversation_id: uuid.UUID,
    ) -> ConversationHistory:
        """Get conversation history.

        Args:
            conversation_id: Conversation ID

        Returns:
            Conversation history

        Raises:
            NotFoundError: If conversation not found
        """
        if conversation_id not in self._conversations:
            raise NotFoundError("Conversation", str(conversation_id))

        messages = self._conversations[conversation_id]

        return ConversationHistory(
            conversation_id=conversation_id,
            messages=messages,
            created_at=messages[0].timestamp if messages else datetime.now(),
            updated_at=messages[-1].timestamp if messages else datetime.now(),
        )

    async def delete_conversation(
        self,
        conversation_id: uuid.UUID,
    ) -> None:
        """Delete a conversation.

        Args:
            conversation_id: Conversation ID
        """
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            for user_id, conversation_ids in ChatService._user_conversations.items():
                if conversation_id in conversation_ids:
                    ChatService._user_conversations[user_id] = [
                        cid for cid in conversation_ids if cid != conversation_id
                    ]
            logger.info(f"Deleted conversation {conversation_id}")

    async def get_user_history(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> ConversationHistory:
        """Get the most recent conversation history for a user."""
        conversation_ids = ChatService._user_conversations.get(user_id, [])
        if not conversation_ids:
            raise NotFoundError("Conversation", f"user:{user_id}")

        conversation_id = conversation_ids[-1]
        messages = self._conversations.get(conversation_id, [])
        paged_messages = messages[offset : offset + limit]

        return ConversationHistory(
            conversation_id=conversation_id,
            messages=paged_messages,
            created_at=messages[0].timestamp if messages else datetime.now(),
            updated_at=messages[-1].timestamp if messages else datetime.now(),
        )

    async def _build_context(
        self,
        user: Any,
        messages: list[ChatMessage],
        include_preferences: bool,
        language: str,
    ) -> list[dict[str, str]]:
        """Build context messages for LLM.

        Args:
            user: User object
            messages: Conversation messages
            include_preferences: Whether to include preferences
            language: Response language

        Returns:
            List of message dictionaries for LLM
        """
        # System prompt
        system_prompt = self._get_system_prompt(language)

        # Add user preferences to context if requested
        if include_preferences:
            preferences = await self.preference_repo.get_active_preferences(user.id)
            if preferences:
                pref_summary = self._summarize_preferences(preferences)
                system_prompt += f"\n\nUser Preferences:\n{pref_summary}"

        context_messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history
        for msg in messages[-10:]:  # Last 10 messages for context
            context_messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        return context_messages

    def _get_system_prompt(self, language: str) -> str:
        """Get the system prompt for the chat assistant.

        Args:
            language: Response language

        Returns:
            System prompt string
        """
        prompts = {
            "en": """You are Phoenix, an AI travel companion. Your role is to help travelers discover new destinations, plan personalized itineraries, and provide real-time guidance.

Key capabilities:
- Understanding and extracting travel preferences from casual conversation
- Suggesting personalized recommendations based on user interests
- Providing helpful information about destinations, attractions, and local culture
- Assisting with route planning and logistics

Be friendly, knowledgeable, and conversational. Ask follow-up questions to better understand the user's preferences.""",
            "zh": """你是Phoenix，一位AI旅行伴侣。你的角色是帮助旅行者发现新目的地、规划个性化行程并提供实时指导。

关键能力：
- 从随意对话中理解和提取旅行偏好
- 根据用户兴趣提供个性化推荐
- 提供有关目的地、景点和当地文化的有用信息
- 协助路线规划和后勤安排

要友好、知识渊博且善于对话。提出后续问题以更好地了解用户的偏好。""",
            "ja": """あなたはPhoenix、AIの旅行コンパニオンです。あなたの役割は、旅行者が新しい目的地を発見し、個人的な旅程を計画し、リアルタイムのガイダンスを提供することを助けることです。

主要な能力：
- カジュアルな会話から旅行の好みを理解して抽出する
- ユーザーの興味に基づいて個人的な推奨を提供する
- 目的地、観光地、地元の文化に関する有用な情報を提供する
- ルート計画とロジスティクスを支援する

親しみやすく、知識豊富で、会話上手であってください。ユーザーの好みをよりよく理解するために、フォローアップの質問をしてください。""",
            "ko": """당신은 Phoenix, AI 여행 동반자입니다. 당신의 역할은 여행자가 새로운 목적지를 발견하고, 개인화된 일정을 계획하며, 실시간 안내를 제공하는 것입니다.

핵심 역량:
- 캐주얼 대화에서 여행 선호도를 이해하고 추출
- 사용자 관심사를 기반으로 개인화된 추천 제공
- 목적지, 명소, 현지 문화에 대한 유용한 정보 제공
- 경로 계획 및 물류 지원

친절하고, 지식이 풍부하며, 대화를 잘하세요. 사용자의 선호도를 더 잘 이해하기 위해 후속 질문을 하세요.""",
            "hi": """आप Phoenix, एक AI यात्रा साथी हैं। आपकी भूमिका यात्रियों को नएं गंतव्यों की खोज करने, व्यक्तिगत यात्रा योजनाएं बनाने और वास्तविक समय मार्गदर्शन प्रदान करने में मदद करना है।

मुख्य क्षमताएं:
- आकस्मिक बातचीत से यात्रा प्राथमिकताएं समझना और निकालना
- उपयोगकर्ता की रुचियों के आधार पर व्यक्तिगत अनुशंसाएं प्रदान करना
- गंतव्यों, आकर्षणों और स्थानीय संस्कृति के बारे में उपयोगी जानकारी प्रदान करना
- मार्ग नियोजन और रसदारी में सहायता

मित्रवत, ज्ञानवान और बातचीत करने वाले बनें। उपयोगकर्ता की प्राथमिकताओं को बेहतर ढंग से समझने के लिए अनुवर्ती प्रश्न पूछें।""",
            "fr": """Vous êtes Phoenix, un compagnon de voyage IA. Votre rôle est d'aider les voyageurs à découvrir de nouvelles destinations, à planifier des itinéraires personnalisés et à fournir des conseils en temps réel.

Capacités clés :
- Comprendre et extraire les préférences de voyage d'une conversation décontractée
- Faire des recommandations personnalisées basées sur les intérêts de l'utilisateur
- Fournir des informations utiles sur les destinations, attractions et culture locale
- Aider à la planification d'itinéraire et à la logistique

Soyez amical, connaissable et conversationnel. Posez des questions de suivi pour mieux comprendre les préférences de l'utilisateur.""",
        }

        return prompts.get(language, prompts["en"])

    def _summarize_preferences(self, preferences: list[Any]) -> str:
        """Summarize user preferences for context.

        Args:
            preferences: List of user preferences

        Returns:
            Formatted preference summary
        """
        summary = []

        # Group by preference type
        likes = [p for p in preferences if p.preference_type == "like"]
        dislikes = [p for p in preferences if p.preference_type == "dislike"]

        if likes:
            summary.append(f"Likes: {', '.join([f'{p.category} ({p.value})' for p in likes[:5]])}")
        if dislikes:
            summary.append(f"Dislikes: {', '.join([f'{p.category} ({p.value})' for p in dislikes[:5]])}")

        return "\n".join(summary)

    async def _extract_preferences_from_conversation(
        self,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Extract preferences from the conversation.

        Args:
            user_id: User ID
            conversation_id: Conversation ID

        Returns:
            List of detected preferences
        """
        messages = self._conversations.get(conversation_id, [])
        if not messages:
            return []

        # Get last user message
        last_user_message = None
        for msg in reversed(messages):
            if msg.role == "user":
                last_user_message = msg.content
                break

        if not last_user_message:
            return []

        # Use LLM to extract preferences
        preferences = await self.preference_service.extract_from_text(
            user_id,
            last_user_message,
        )

        return [
            {
                "category": p.category,
                "value": p.value,
                "confidence": p.confidence_score,
                "preference_type": p.preference_type,
            }
            for p in preferences
        ]

    async def _generate_suggested_actions(
        self,
        user_id: uuid.UUID,
        message: str,
    ) -> list[str]:
        """Generate suggested follow-up actions.

        Args:
            user_id: User ID
            message: User's message

        Returns:
            List of suggested actions
        """
        # Classify intent to determine relevant actions
        intents = [
            "preference_sharing",
            "route_planning",
            "poi_inquiry",
            "general_question",
        ]

        try:
            intent_result = await self.llm_service.classify_intent(message, intents)
            intent = intent_result.get("intent", "general_question")

            actions_map = {
                "preference_sharing": [
                    "Generate a personalized itinerary",
                    "Find similar destinations",
                    "Update travel preferences",
                ],
                "route_planning": [
                    "Create a detailed route plan",
                    "Optimize for shortest distance",
                    "Add more stops to the route",
                ],
                "poi_inquiry": [
                    "Get more information about this place",
                    "Find nearby attractions",
                    "Check opening hours and tickets",
                ],
                "general_question": [
                    "Tell me more about travel options",
                    "Get travel tips and advice",
                    "Explore popular destinations",
                ],
            }

            return actions_map.get(intent, [])

        except Exception:
            return []

    async def stream_response(
        self,
        user_id: uuid.UUID,
        message: str,
        conversation_id: uuid.UUID | None = None,
    ):
        """Stream a chat response.

        Args:
            user_id: User ID
            message: User message
            conversation_id: Optional conversation ID

        Yields:
            Response chunks
        """
        # Get or create conversation
        if conversation_id is None:
            conversation_id = uuid.uuid4()

        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []

        # Add user message
        user_message = ChatMessage(
            role="user",
            content=message,
            timestamp=datetime.now(),
        )
        self._conversations[conversation_id].append(user_message)

        # Build context (simplified for streaming)
        context_messages = [
            {"role": "system", "content": self._get_system_prompt("en")},
            {"role": "user", "content": message},
        ]

        # Stream response
        stream = await self.llm_service.chat_completion(
            messages=context_messages,
            stream=True,
        )

        full_response = ""
        async for chunk in stream:
            full_response += chunk
            yield chunk

        # Add assistant message to conversation
        assistant_message = ChatMessage(
            role="assistant",
            content=full_response,
            timestamp=datetime.now(),
        )
        self._conversations[conversation_id].append(assistant_message)
