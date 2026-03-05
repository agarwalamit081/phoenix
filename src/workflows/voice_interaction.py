"""Voice interaction workflow using LangGraph."""

import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any, Literal

from langgraph.graph import StateGraph, END

from src.services.llm_service import LLMService
from src.services.voice_service import VoiceService
from src.voice.translation_manager import BiDirectionalTranslator
from src.workflows.state import VoiceState

logger = logging.getLogger(__name__)


class VoiceInteractionWorkflow:
    """LangGraph workflow for voice interactions."""

    def __init__(
        self,
        llm_service: LLMService | None = None,
        voice_service: VoiceService | None = None,
    ) -> None:
        """Initialize voice interaction workflow.

        Args:
            llm_service: Optional LLM service
            voice_service: Optional voice service
        """
        self.llm_service = llm_service or LLMService()
        self.voice_service = voice_service or VoiceService()

        # Build workflow graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine.

        Returns:
            Compiled state graph
        """
        workflow = StateGraph(VoiceState)

        # Add nodes
        workflow.add_node("receive_audio", self._receive_audio)
        workflow.add_node("transcribe", self._transcribe)
        workflow.add_node("translate_input", self._translate_input)
        workflow.add_node("classify_intent", self._classify_intent)
        workflow.add_node("generate_response", self._generate_response)
        workflow.add_node("translate_output", self._translate_output)
        workflow.add_node("synthesize_speech", self._synthesize_speech)
        workflow.add_node("handle_error", self._handle_error)

        # Define edges
        workflow.set_entry_point("receive_audio")
        workflow.add_edge("receive_audio", "transcribe")
        workflow.add_edge("transcribe", "translate_input")
        workflow.add_edge("translate_input", "classify_intent")

        # Conditional routing based on intent
        workflow.add_conditional_edges(
            "classify_intent",
            self._route_by_intent,
            {
                "general": "generate_response",
                "preference_collection": "generate_response",
                "route_planning": "generate_response",
                "error": "handle_error",
            },
        )

        workflow.add_edge("generate_response", "translate_output")
        workflow.add_edge("translate_output", "synthesize_speech")
        workflow.add_edge("synthesize_speech", END)
        workflow.add_edge("handle_error", END)

        return workflow.compile()

    async def _receive_audio(self, state: VoiceState) -> VoiceState:
        """Receive audio input from user.

        Args:
            state: Current workflow state

        Returns:
            Updated state
        """
        logger.debug(f"Receiving audio for session: {state['session_id']}")

        state["status"] = "receiving_audio"
        state["steps_completed"].append("receive_audio")

        return state

    async def _transcribe(self, state: VoiceState) -> VoiceState:
        """Transcribe audio to text.

        Args:
            state: Current workflow state

        Returns:
            Updated state with transcription
        """
        logger.debug("Transcribing audio")

        state["status"] = "transcribing"
        state["steps_completed"].append("transcribe")

        # Audio is already transcribed by Speechmatics client
        # This node represents the workflow step
        if state.get("transcript"):
            logger.info(f"Transcript: {state['transcript']}")

        return state

    async def _translate_input(self, state: VoiceState) -> VoiceState:
        """Translate input to assistant language if needed.

        Args:
            state: Current workflow state

        Returns:
            Updated state with translated text
        """
        logger.debug("Translating input")

        state["status"] = "translating_input"
        state["steps_completed"].append("translate_input")

        source_lang = state.get("source_language", "en")
        target_lang = state.get("target_language", "en")

        # Skip if same language
        if source_lang == target_lang:
            state["translated_input"] = state.get("transcript", "")
            return state

        # Perform translation
        translator = BiDirectionalTranslator(
            primary_language=target_lang,
            secondary_language=source_lang,
        )

        try:
            translated = await translator.to_secondary(state.get("transcript", ""))
            state["translated_input"] = translated
            logger.info(f"Translated: {state['transcript']} -> {translated}")

        except Exception as e:
            logger.error(f"Translation failed: {e}")
            state["translated_input"] = state.get("transcript", "")

        return state

    async def _classify_intent(self, state: VoiceState) -> VoiceState:
        """Classify user intent from transcript.

        Args:
            state: Current workflow state

        Returns:
            Updated state with classified intent
        """
        logger.debug("Classifying intent")

        state["status"] = "classifying_intent"
        state["steps_completed"].append("classify_intent")

        transcript = state.get("translated_input", "")

        if not transcript:
            state["intent"] = "error"
            state["error"] = "No transcript available"
            return state

        try:
            intents = ["general", "preference_collection", "route_planning"]
            # Use LLM to classify intent
            result = await self.llm_service.classify_intent(transcript, intents)
            state["intent"] = result.get("intent", "general")
            state["intent_confidence"] = result.get("confidence", 0.0)

            logger.info(f"Intent: {state['intent']} (confidence: {state['intent_confidence']})")

        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            state["intent"] = "general"
            state["intent_confidence"] = 0.0

        return state

    def _route_by_intent(self, state: VoiceState) -> str:
        """Determine next step based on intent.

        Args:
            state: Current workflow state

        Returns:
            Next node name
        """
        intent = state.get("intent", "general")

        if intent == "error" or state.get("error"):
            return "error"

        return "general"

    async def _generate_response(self, state: VoiceState) -> VoiceState:
        """Generate AI response to user input.

        Args:
            state: Current workflow state

        Returns:
            Updated state with response
        """
        logger.debug("Generating response")

        state["status"] = "generating_response"
        state["steps_completed"].append("generate_response")

        user_input = state.get("translated_input", "")
        intent = state.get("intent", "general")

        # Build system prompt based on intent
        system_prompts = {
            "general": "You are a helpful AI travel assistant for Phoenix Travel Companion. Provide friendly, helpful responses.",
            "preference_collection": "You are helping collect travel preferences from a user. Ask relevant follow-up questions to understand their needs.",
            "route_planning": "You are helping plan a travel route. Focus on destinations, timing, and logistics.",
        }

        system_prompt = system_prompts.get(
            intent,
            system_prompts["general"],
        )

        try:
            response = await self.llm_service.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input},
                ],
                temperature=0.7,
            )

            state["response"] = response.get("content", "")
            state["model_used"] = response.get("model", "unknown")

            logger.info(f"Response generated: {state['response'][:100]}...")

        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            state["response"] = "I apologize, but I couldn't generate a response. Please try again."
            state["error"] = str(e)

        return state

    async def _translate_output(self, state: VoiceState) -> VoiceState:
        """Translate response to user language if needed.

        Args:
            state: Current workflow state

        Returns:
            Updated state with translated response
        """
        logger.debug("Translating output")

        state["status"] = "translating_output"
        state["steps_completed"].append("translate_output")

        source_lang = state.get("target_language", "en")
        target_lang = state.get("source_language", "en")

        # Skip if same language
        if source_lang == target_lang:
            state["translated_response"] = state.get("response", "")
            return state

        # Perform translation
        translator = BiDirectionalTranslator(
            primary_language=source_lang,
            secondary_language=target_lang,
        )

        try:
            translated = await translator.to_primary(state.get("response", ""))
            state["translated_response"] = translated

            logger.info(f"Response translated: {state['response'][:50]} -> {translated[:50]}")

        except Exception as e:
            logger.error(f"Translation failed: {e}")
            state["translated_response"] = state.get("response", "")

        return state

    async def _synthesize_speech(self, state: VoiceState) -> VoiceState:
        """Synthesize response to audio.

        Args:
            state: Current workflow state

        Returns:
            Updated state with audio data
        """
        logger.debug("Synthesizing speech")

        state["status"] = "synthesizing_speech"
        state["steps_completed"].append("synthesize_speech")

        response_text = state.get("translated_response", state.get("response", ""))

        if not response_text:
            state["audio_data"] = b""
            return state

        try:
            audio = await self.voice_service.text_to_speech(
                text=response_text,
                language=state.get("source_language", "en"),
            )

            state["audio_data"] = audio

        except Exception as e:
            logger.error(f"Speech synthesis failed: {e}")
            state["audio_data"] = b""

        state["completed_at"] = datetime.now(timezone.utc).isoformat()

        return state

    async def _handle_error(self, state: VoiceState) -> VoiceState:
        """Handle workflow errors.

        Args:
            state: Current workflow state

        Returns:
            Updated state with error handling
        """
        logger.error(f"Handling error: {state.get('error', 'Unknown error')}")

        state["status"] = "error"
        state["steps_completed"].append("handle_error")
        state["response"] = "I apologize, but something went wrong. Please try again."
        state["translated_response"] = state["response"]
        state["completed_at"] = datetime.now(timezone.utc).isoformat()

        return state

    async def process(
        self,
        session_id: str,
        transcript: str,
        source_language: str = "en",
        target_language: str = "en",
    ) -> dict[str, Any]:
        """Process voice interaction through workflow.

        Args:
            session_id: Voice session ID
            transcript: User transcript text
            source_language: User's language
            target_language: Assistant's language

        Returns:
            Processing result
        """
        # Initialize state
        initial_state: VoiceState = {
            "session_id": session_id,
            "transcript": transcript,
            "source_language": source_language,
            "target_language": target_language,
            "status": "initialized",
            "steps_completed": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Run workflow
        try:
            final_state = await self.graph.ainvoke(initial_state)
            return final_state

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return {
                **initial_state,
                "status": "error",
                "error": str(e),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }

    async def process_stream(
        self,
        session_id: str,
        audio_stream: AsyncGenerator[bytes, None],
        source_language: str = "en",
        target_language: str = "en",
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Process audio stream with real-time updates.

        Args:
            session_id: Voice session ID
            audio_stream: Audio data stream
            source_language: User's language
            target_language: Assistant's language

        Yields:
            Processing events
        """
        # This would integrate with SpeechmaticsClient for streaming
        # For now, it's a placeholder for future implementation
        yield {"type": "info", "message": "Stream processing not yet implemented"}


# Global instance
voice_workflow = VoiceInteractionWorkflow()
