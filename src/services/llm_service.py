"""LLM service for OpenAI integration."""

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

    def __init__(self) -> None:
        """Initialize the LLM service."""
        if not settings.openai_api_key:
            logger.warning("OpenAI API key not configured")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
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
            params = {
                "model": model or settings.openai_model_chat,
                "messages": messages,
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

            response = await self.client.chat.completions.create(**params)

            return {
                "content": response.choices[0].message.content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                "finish_reason": response.choices[0].finish_reason,
                "function_call": getattr(response.choices[0].message, "function_call", None),
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
        messages: list[dict[str, str]],
        schema: dict[str, Any],
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
        response = await self.chat_completion(
            messages=messages,
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
        entity_types: list[str],
    ) -> list[dict[str, Any]]:
        """Extract entities from text using LLM.

        Args:
            text: Text to extract entities from
            entity_types: Types of entities to extract

        Returns:
            List of extracted entities with type and value
        """
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

        if response.get("function_call"):
            function_args = json.loads(response["function_call"]["arguments"])
            return function_args.get("entities", [])

        return []

    async def classify_intent(
        self,
        text: str,
        intents: list[str],
    ) -> dict[str, Any]:
        """Classify the intent of user input.

        Args:
            text: User input text
            intents: List of possible intents

        Returns:
            Dictionary with intent and confidence
        """
        functions = [
            {
                "name": "classify_intent",
                "description": "Classify the user's intent",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "intent": {
                            "type": "string",
                            "enum": intents,
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
                "content": f"Classify the user's intent into one of: {', '.join(intents)}",
            },
            {"role": "user", "content": text},
        ]

        response = await self.generate_with_functions(messages, functions)

        if response.get("function_call"):
            function_args = json.loads(response["function_call"]["arguments"])
            return function_args

        return {"intent": intents[0], "confidence": 0.0, "reasoning": "Unknown"}

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
            response = await self.client.embeddings.create(
                input=texts,
                model=model or settings.openai_model_embedding,
            )

            return [item.embedding for item in response.data]

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
