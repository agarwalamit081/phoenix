"""LLM service for OpenAI integration."""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI, OpenAIError

from src.config.logging import logger
from src.config.settings import settings
from src.core.exceptions import ExternalServiceError


@dataclass
class Message:
    """Message for chat completion."""

    role: str
    content: str
    name: str | None = None
    function_call: dict[str, Any] | None = None


@dataclass
class ChatCompletionResponse:
    """Response from chat completion."""

    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    function_call: dict[str, Any] | None = None


class LLMService:
    """Service for interacting with OpenAI's LLM API."""

    def __init__(self, client: Any | None = None, max_retries: int = 0) -> None:
        """Initialize the LLM service."""
        self.max_retries = max_retries
        if client is not None:
            self.client = client
        elif not settings.openai_api_key:
            logger.warning("OpenAI API key not configured")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def chat_completion(
        self,
        messages: list[dict[str, str]] | list[Message],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        functions: list[dict[str, Any]] | None = None,
        function_call: str | dict[str, str] | None = None,
        response_format: dict[str, str] | None = None,
        stream: bool = False,
    ) -> dict[str, Any] | Any:
        """Generate a chat completion.

        Args:
            messages: List of message dictionaries with role and content
            model: Model to use (defaults to settings.openai_model_chat)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            functions: Optional function definitions for function calling
            function_call: Function calling behavior
            response_format: Optional response format (e.g., {"type": "json_object"})
            stream: Whether to stream the response

        Returns:
            Response dictionary or async generator if streaming

        Raises:
            ExternalServiceError: If API call fails
        """
        if not self.client:
            raise ExternalServiceError(
                service="OpenAI",
                message="OpenAI client not configured",
            )

        try:
            prepared_messages = [
                {"role": msg.role, "content": msg.content}
                if isinstance(msg, Message)
                else msg
                for msg in messages
            ]

            params = {
                "model": model or settings.openai_model_chat,
                "messages": prepared_messages,
                "temperature": temperature if temperature is not None else settings.openai_temperature,
            }

            if max_tokens is not None:
                params["max_tokens"] = max_tokens
            else:
                params["max_tokens"] = settings.openai_max_tokens

            if functions:
                params["functions"] = functions
            if function_call:
                params["function_call"] = function_call
            if response_format:
                params["response_format"] = response_format

            if stream:
                return await self._stream_completion(**params)

            attempt = 0
            while True:
                try:
                    response = await self.client.chat.completions.create(**params)
                    break
                except Exception as e:
                    if attempt >= self.max_retries:
                        raise
                    attempt += 1
                    await asyncio.sleep(0.05 * attempt)

            tool_calls = []
            message_obj = response.choices[0].message
            for call in getattr(message_obj, "tool_calls", []) or []:
                function_obj = call.function
                fn_name = getattr(function_obj, "name", None)
                if not isinstance(fn_name, str):
                    fn_name = getattr(function_obj, "_mock_name", None) or str(fn_name)
                tool_calls.append(
                    {
                        "name": fn_name,
                        "arguments": getattr(function_obj, "arguments", None),
                    }
                )
            function_call_obj = getattr(message_obj, "function_call", None)
            if not (
                function_call_obj
                and isinstance(getattr(function_call_obj, "arguments", None), str)
            ):
                function_call_obj = None
            return {
                "content": message_obj.content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                "finish_reason": response.choices[0].finish_reason,
                "function_call": function_call_obj,
                "tool_calls": tool_calls,
            }

        except OpenAIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise ExternalServiceError(
                service="OpenAI",
                message=f"LLM request failed: {str(e)}",
            ) from e

    async def _stream_completion(self, **kwargs: Any) -> Any:
        """Stream a chat completion.

        Args:
            **kwargs: Arguments to pass to API

        Returns:
            Async generator of response chunks
        """
        stream = await self.client.chat.completions.create(**kwargs, stream=True)

        async def generate() -> Any:
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if hasattr(delta, "content") and delta.content:
                    yield delta.content

        return generate()

    async def generate_with_functions(
        self,
        messages: list[dict[str, str]],
        functions: list[dict[str, Any]],
        model: str | None = None,
    ) -> dict[str, Any]:
        """Generate a chat completion with function calling.

        Args:
            messages: List of message dictionaries
            functions: Function definitions
            model: Model to use

        Returns:
            Response with function call if triggered

        Raises:
            ExternalServiceError: If API call fails
        """
        return await self.chat_completion(
            messages=messages,
            functions=functions,
            function_call="auto",
            model=model,
        )

    async def generate_json(
        self,
        messages: list[dict[str, str]] | str,
        schema: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Generate a JSON response following a schema.

        Args:
            messages: List of message dictionaries
            schema: JSON schema for response
            model: Model to use

        Returns:
            Parsed JSON response

        Raises:
            ExternalServiceError: If API call fails
        """
        prepared_messages = (
            [{"role": "user", "content": messages}]
            if isinstance(messages, str)
            else messages
        )

        response = await self.chat_completion(
            messages=prepared_messages,
            response_format={"type": "json_object"},
            model=model,
        )

        try:
            content = response.get("content", "{}")
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise ExternalServiceError(
                service="OpenAI",
                message="Failed to parse JSON response",
            ) from e

    async def extract_entities(
        self,
        text: str,
        entity_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Extract entities from text using LLM.

        Args:
            text: Text to extract entities from
            entity_types: Types of entities to extract

        Returns:
            List of extracted entities with type and value
        """
        entity_types = entity_types or ["LOCATION", "POI", "DATE", "TIME", "TRANSPORT", "ACTIVITY"]

        functions = [
            {
                "name": "extract_entities",
                "description": "Extract entities from text",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": entity_types,
                                        "description": "Entity type",
                                    },
                                    "value": {
                                        "type": "string",
                                        "description": "Entity value",
                                    },
                                    "confidence": {
                                        "type": "number",
                                        "description": "Confidence score",
                                    },
                                },
                                "required": ["type", "value"],
                            },
                        },
                    },
                    "required": ["entities"],
                },
            }
        ]

        messages = [
            {
                "role": "system",
                "content": f"Extract entities of types: {', '.join(entity_types)} from the user's text.",
            },
            {"role": "user", "content": text},
        ]

        response = await self.generate_with_functions(messages, functions)

        # Prefer explicit tool/function call arguments when available.
        function_args_raw: Any = None
        tool_calls = response.get("tool_calls") or []
        if tool_calls and isinstance(tool_calls[0], dict):
            function_args_raw = tool_calls[0].get("arguments")
        if function_args_raw is None:
            function_call = response.get("function_call")
            if isinstance(function_call, dict):
                function_args_raw = function_call.get("arguments")
            elif function_call is not None:
                function_args_raw = getattr(function_call, "arguments", None)
        if isinstance(function_args_raw, str):
            function_args = json.loads(function_args_raw)
            return function_args.get("entities", [])

        content = response.get("content")
        if content:
            try:
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass

        return []

    async def classify_intent(
        self,
        text: str,
        intents: list[str] | None = None,
    ) -> dict[str, Any]:
        """Classify the intent of user input.

        Args:
            text: User input text
            intents: List of possible intents. Defaults to travel voice intents.

        Returns:
            Dictionary with intent and confidence
        """
        intent_options = intents or [
            "general",
            "preference_collection",
            "route_planning",
            "travel_planning",
        ]

        functions = [
            {
                "name": "classify_intent",
                "description": "Classify the user's intent",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "intent": {
                            "type": "string",
                            "enum": intent_options,
                            "description": "The classified intent",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score",
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Reasoning for classification",
                        },
                    },
                    "required": ["intent", "confidence"],
                },
            }
        ]

        messages = [
            {
                "role": "system",
                "content": f"Classify the user's intent into one of: {', '.join(intent_options)}",
            },
            {"role": "user", "content": text},
        ]

        response = await self.generate_with_functions(messages, functions)

        function_call = response.get("function_call")
        if function_call and isinstance(function_call.get("arguments"), str):
            function_args = json.loads(function_call["arguments"])
            intent = function_args.get("intent", intent_options[0])
            if intent not in intent_options:
                return {"intent": intent_options[0], "confidence": 0.0, "reasoning": "Unknown"}
            return function_args

        content = response.get("content")
        if content:
            try:
                parsed = json.loads(content)
                intent = parsed.get("intent", intent_options[0])
                if intent not in intent_options:
                    intent = intent_options[0]
                    parsed["confidence"] = 0.0
                parsed.setdefault("confidence", 0.0)
                return parsed
            except json.JSONDecodeError:
                pass

        return {"intent": intent_options[0], "confidence": 0.0, "reasoning": "Unknown"}

    async def summarize_conversation(self, messages: list[dict[str, str]] | list[Message]) -> str:
        """Summarize a conversation transcript."""
        response = await self.chat_completion(
            messages=[
                {"role": "system", "content": "Summarize the conversation in one concise paragraph."},
                {"role": "user", "content": str(messages)},
            ],
            temperature=0.2,
        )
        return response.get("content", "")

    async def generate_embedding(self, text: str, model: str | None = None) -> list[float]:
        """Generate a single embedding vector."""
        vectors = await self.generate_embeddings([text], model=model)
        return vectors[0] if vectors else []

    async def stream_chat(
        self,
        messages: list[dict[str, str]] | list[Message],
        model: str | None = None,
        temperature: float | None = None,
    ) -> Any:
        """Stream chat chunks as plain text."""
        stream = await self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            yield chunk

    async def generate_embeddings(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings for texts.

        Args:
            texts: List of texts to embed
            model: Model to use (defaults to settings.openai_model_embedding)

        Returns:
            List of embedding vectors

        Raises:
            ExternalServiceError: If API call fails
        """
        if not self.client:
            raise ExternalServiceError(
                service="OpenAI",
                message="OpenAI client not configured",
            )

        try:
            results: list[list[float]] = []
            for text in texts:
                response = await self.client.embeddings.create(
                    input=text,
                    model=model or settings.openai_model_embedding,
                )
                results.append(response.data[0].embedding)
            return results

        except OpenAIError as e:
            logger.error(f"OpenAI embedding error: {e}")
            raise ExternalServiceError(
                service="OpenAI",
                message=f"Embedding generation failed: {str(e)}",
            ) from e

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        # Rough estimate: ~4 characters per token for English
        return len(text) // 4

    async def validate_api_key(self) -> bool:
        """Validate the OpenAI API key.

        Returns:
            True if API key is valid, False otherwise
        """
        try:
            await self.chat_completion(
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
            )
            return True
        except Exception:
            return False
