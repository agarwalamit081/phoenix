"""Regression tests for voice runtime reliability fixes."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.llm_service import LLMService
from src.voice import voice_agent_worker
from src.voice.livekit_service import LiveKitService
from src.workflows.voice_interaction import VoiceInteractionWorkflow


def test_livekit_list_rooms_uses_response_rooms() -> None:
    """list_rooms should parse ListRoomsResponse.rooms and return mapped dicts."""
    service = LiveKitService(api_key="key", api_secret="secret", url="wss://example.livekit")
    room = SimpleNamespace(
        sid="RM_1",
        name="voice-room-1",
        num_participants=2,
        max_participants=5,
        empty_timeout=300,
        creation_time=123456789,
    )
    room_service = AsyncMock()
    room_service.list_rooms.return_value = SimpleNamespace(rooms=[room])
    service._room_service = room_service

    result = asyncio.run(service.list_rooms())

    assert result == [
        {
            "sid": "RM_1",
            "name": "voice-room-1",
            "num_participants": 2,
            "max_participants": 5,
        }
    ]
    assert len(room_service.list_rooms.await_args.args) == 1


def test_livekit_delete_room_passes_single_request_argument() -> None:
    """delete_room should call SDK with only DeleteRoomRequest argument."""
    from livekit.api.room_service import DeleteRoomRequest

    service = LiveKitService(api_key="key", api_secret="secret", url="wss://example.livekit")
    room_service = AsyncMock()
    room_service.delete_room.return_value = SimpleNamespace()
    service._room_service = room_service

    result = asyncio.run(service.delete_room("voice-room-1"))

    assert result is True
    assert len(room_service.delete_room.await_args.args) == 1
    assert isinstance(room_service.delete_room.await_args.args[0], DeleteRoomRequest)


def test_livekit_remove_participant_uses_room_participant_identity() -> None:
    """remove_participant should use RoomParticipantIdentity request type."""
    from livekit.api.room_service import RoomParticipantIdentity

    service = LiveKitService(api_key="key", api_secret="secret", url="wss://example.livekit")
    room_service = AsyncMock()
    room_service.remove_participant.return_value = SimpleNamespace()
    service._room_service = room_service

    result = asyncio.run(service.remove_participant("voice-room-1", "user-1"))

    assert result is True
    assert len(room_service.remove_participant.await_args.args) == 1
    assert isinstance(room_service.remove_participant.await_args.args[0], RoomParticipantIdentity)
    assert room_service.remove_participant.await_args.args[0].room == "voice-room-1"
    assert room_service.remove_participant.await_args.args[0].identity == "user-1"


def test_voice_workflow_passes_explicit_intents_to_classifier() -> None:
    """Voice workflow should pass transcript and supported intents to classify_intent."""
    mock_llm = AsyncMock()
    mock_llm.classify_intent.return_value = {"intent": "route_planning", "confidence": 0.93}
    workflow = VoiceInteractionWorkflow(llm_service=mock_llm, voice_service=MagicMock())

    state = {
        "session_id": "session-1",
        "translated_input": "Plan my route",
        "steps_completed": [],
    }

    updated = asyncio.run(workflow._classify_intent(state))

    assert updated["intent"] == "route_planning"
    assert updated["intent_confidence"] == 0.93
    assert mock_llm.classify_intent.await_args.args[0] == "Plan my route"
    assert mock_llm.classify_intent.await_args.args[1] == [
        "general",
        "preference_collection",
        "route_planning",
    ]


def test_llm_classify_intent_defaults_when_intents_not_provided() -> None:
    """LLM classify_intent should be backward compatible with optional intents."""
    llm_service = LLMService()
    llm_service.generate_with_functions = AsyncMock(return_value={})

    result = asyncio.run(llm_service.classify_intent("hello there"))

    assert result["intent"] == "general"
    assert result["confidence"] == 0.0


def test_llm_classify_intent_falls_back_on_invalid_model_intent() -> None:
    """Invalid intent from model output should fallback to default intent."""
    llm_service = LLMService()
    llm_service.generate_with_functions = AsyncMock(
        return_value={
            "function_call": {
                "arguments": '{"intent": "invalid_intent", "confidence": 0.9}',
            }
        }
    )

    result = asyncio.run(llm_service.classify_intent("hello"))

    assert result["intent"] == "general"
    assert result["confidence"] == 0.0


def test_request_function_accepts_voice_and_tour_rooms() -> None:
    """Worker request filter should accept both voice-* and tour-* rooms."""
    voice_req = SimpleNamespace(
        room=SimpleNamespace(name="voice-abc"),
        accept=AsyncMock(),
        reject=AsyncMock(),
    )
    tour_req = SimpleNamespace(
        room=SimpleNamespace(name="tour-123"),
        accept=AsyncMock(),
        reject=AsyncMock(),
    )
    other_req = SimpleNamespace(
        room=SimpleNamespace(name="chat-123"),
        accept=AsyncMock(),
        reject=AsyncMock(),
    )

    asyncio.run(voice_agent_worker.request_fnc(voice_req))
    asyncio.run(voice_agent_worker.request_fnc(tour_req))
    asyncio.run(voice_agent_worker.request_fnc(other_req))

    voice_req.accept.assert_awaited_once()
    voice_req.reject.assert_not_awaited()
    tour_req.accept.assert_awaited_once()
    tour_req.reject.assert_not_awaited()
    other_req.reject.assert_awaited_once()
    other_req.accept.assert_not_awaited()


def test_speechmatics_ws_url_prefers_new_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """SPEECHMATICS_WS_URL should override legacy SPEECHMATICS_RT_URL."""
    monkeypatch.setenv("SPEECHMATICS_WS_URL", "wss://new.example/v2")
    monkeypatch.setenv("SPEECHMATICS_RT_URL", "wss://legacy.example/v2")

    result = voice_agent_worker._get_speechmatics_ws_url()

    assert result == "wss://new.example/v2"


def test_build_stt_config_falls_back_to_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    """When Speechmatics is unavailable, worker should fallback to OpenAI STT."""
    from livekit.plugins import openai

    monkeypatch.setattr(voice_agent_worker, "SPEECHMATICS_AVAILABLE", False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    stt_config = voice_agent_worker._build_stt_config(language="en")

    assert isinstance(stt_config, openai.stt.STT)


def test_build_stt_config_raises_when_no_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """If no STT provider is available, worker should fail clearly."""
    monkeypatch.setattr(voice_agent_worker, "SPEECHMATICS_AVAILABLE", False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SPEECHMATICS_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="No STT provider configured"):
        voice_agent_worker._build_stt_config(language="en")
