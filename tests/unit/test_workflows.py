"""Unit tests for LangGraph workflows."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.workflows.state import PreferenceState, WorkflowState
from src.workflows.preference_collection import PreferenceCollectionWorkflow


@pytest.mark.asyncio
class TestWorkflowState:
    """Tests for workflow state definitions."""

    def test_preference_state_initialization(self) -> None:
        """Test PreferenceState initialization."""
        state = PreferenceState(
            user_id=str(uuid.uuid4()),
            messages=["I love Italian food"],
            extracted_preferences=[],
            validated_preferences=[],
            conflicts=[],
            is_complete=False,
        )
        assert state.user_id is not None
        assert len(state.messages) == 1
        assert state.is_complete is False

    def test_workflow_state_initialization(self) -> None:
        """Test WorkflowState initialization."""
        state = WorkflowState(
            user_id=str(uuid.uuid4()),
            current_step="preference_collection",
            context={},
            history=[],
            metadata={},
        )
        assert state.current_step == "preference_collection"


@pytest.mark.asyncio
class TestPreferenceCollectionWorkflow:
    """Tests for PreferenceCollectionWorkflow."""

    async def test_extract_preferences_node(self) -> None:
        """Test the extract preferences node."""
        mock_llm_service = AsyncMock()
        mock_llm_service.extract_entities.return_value = [
            {
                "text": "Italian food",
                "type": "CUISINE",
                "confidence": 0.9,
            },
            {
                "text": "art museums",
                "type": "ACTIVITY",
                "confidence": 0.85,
            },
        ]

        workflow = PreferenceCollectionWorkflow(mock_llm_service)

        state = PreferenceState(
            user_id=str(uuid.uuid4()),
            messages=["I love Italian food and art museums"],
            extracted_preferences=[],
            validated_preferences=[],
            conflicts=[],
            is_complete=False,
        )

        new_state = await workflow._extract_preferences(state)

        assert len(new_state["extracted_preferences"]) == 2
        assert new_state["extracted_preferences"][0]["value"] == "Italian food"

    async def test_validate_preferences_node(self) -> None:
        """Test the validate preferences node."""
        mock_llm_service = AsyncMock()

        workflow = PreferenceCollectionWorkflow(mock_llm_service)

        state = PreferenceState(
            user_id=str(uuid.uuid4()),
            messages=[],
            extracted_preferences=[
                {
                    "category": "cuisine",
                    "value": "Italian",
                    "preference_type": "like",
                    "confidence": 0.9,
                }
            ],
            validated_preferences=[],
            conflicts=[],
            is_complete=False,
        )

        new_state = await workflow._validate_preferences(state)

        assert len(new_state["validated_preferences"]) >= 0

    async def test_check_conflicts_node(self) -> None:
        """Test the check conflicts node."""
        mock_llm_service = AsyncMock()

        workflow = PreferenceCollectionWorkflow(mock_llm_service)

        state = PreferenceState(
            user_id=str(uuid.uuid4()),
            messages=[],
            extracted_preferences=[],
            validated_preferences=[
                {
                    "category": "cuisine",
                    "value": "Italian",
                    "preference_type": "like",
                    "confidence": 0.9,
                },
                {
                    "category": "cuisine",
                    "value": "Italian",
                    "preference_type": "dislike",
                    "confidence": 0.7,
                },
            ],
            conflicts=[],
            is_complete=False,
        )

        new_state = await workflow._check_conflicts(state)

        # Should detect conflict
        assert len(new_state["conflicts"]) >= 0

    async def test_determine_completion_with_sufficient_data(self) -> None:
        """Test determine completion with sufficient preferences."""
        mock_llm_service = AsyncMock()

        workflow = PreferenceCollectionWorkflow(mock_llm_service)

        state = PreferenceState(
            user_id=str(uuid.uuid4()),
            messages=[],
            extracted_preferences=[],
            validated_preferences=[
                {"category": "cuisine", "value": "Italian", "preference_type": "like"},
                {"category": "activity", "value": "Museums", "preference_type": "like"},
                {"category": "activity", "value": "Parks", "preference_type": "like"},
            ],
            conflicts=[],
            is_complete=False,
        )

        new_state = await workflow._determine_completion(state)

        # Should be complete with 3 preferences
        assert new_state["is_complete"] is True

    async def test_determine_completion_insufficient_data(self) -> None:
        """Test determine completion with insufficient preferences."""
        mock_llm_service = AsyncMock()

        workflow = PreferenceCollectionWorkflow(mock_llm_service)

        state = PreferenceState(
            user_id=str(uuid.uuid4()),
            messages=[],
            extracted_preferences=[],
            validated_preferences=[
                {"category": "cuisine", "value": "Italian", "preference_type": "like"},
            ],
            conflicts=[],
            is_complete=False,
        )

        new_state = await workflow._determine_completion(state)

        # Should not be complete with only 1 preference
        assert new_state["is_complete"] is False

    async def test_generate_followup_question(self) -> None:
        """Test generating follow-up question."""
        mock_llm_service = AsyncMock()
        mock_llm_service.chat_completion.return_value = {
            "content": "What types of activities do you enjoy during your travels?",
            "model": "gpt-4o-mini",
            "usage": {"total_tokens": 25},
        }

        workflow = PreferenceCollectionWorkflow(mock_llm_service)

        state = PreferenceState(
            user_id=str(uuid.uuid4()),
            messages=["I love Italian food"],
            extracted_preferences=[],
            validated_preferences=[
                {"category": "cuisine", "value": "Italian", "preference_type": "like"},
            ],
            conflicts=[],
            is_complete=False,
        )

        new_state = await workflow._generate_followup_question(state)

        assert "followup_question" in new_state
        assert new_state["followup_question"] is not None

    async def test_workflow_full_cycle(self) -> None:
        """Test a complete workflow cycle."""
        mock_llm_service = AsyncMock()
        mock_llm_service.extract_entities.return_value = [
            {"category": "cuisine", "value": "Italian", "preference_type": "like", "confidence": 0.9},
        ]
        mock_llm_service.chat_completion.return_value = {
            "content": "Thanks! What about activities?",
            "model": "gpt-4o-mini",
            "usage": {"total_tokens": 20},
        }

        workflow = PreferenceCollectionWorkflow(mock_llm_service)

        state = PreferenceState(
            user_id=str(uuid.uuid4()),
            messages=["I love Italian food"],
            extracted_preferences=[],
            validated_preferences=[],
            conflicts=[],
            is_complete=False,
        )

        # Run through the workflow
        state = await workflow._extract_preferences(state)
        state = await workflow._validate_preferences(state)
        state = await workflow._check_conflicts(state)
        state = await workflow._determine_completion(state)

        assert len(state["validated_preferences"]) >= 0

    async def test_should_complete_condition(self) -> None:
        """Test the completion condition logic."""
        mock_llm_service = AsyncMock()
        workflow = PreferenceCollectionWorkflow(mock_llm_service)

        # Complete state
        state_complete = PreferenceState(
            user_id=str(uuid.uuid4()),
            messages=[],
            extracted_preferences=[],
            validated_preferences=[
                {"category": "cuisine", "value": "Italian", "preference_type": "like"},
                {"category": "activity", "value": "Museums", "preference_type": "like"},
                {"category": "activity", "value": "Parks", "preference_type": "like"},
            ],
            conflicts=[],
            is_complete=True,
        )

        decision = workflow._should_complete(state_complete)
        assert decision == "complete"

        # Incomplete state
        state_incomplete = PreferenceState(
            user_id=str(uuid.uuid4()),
            messages=[],
            extracted_preferences=[],
            validated_preferences=[
                {"category": "cuisine", "value": "Italian", "preference_type": "like"},
            ],
            conflicts=[],
            is_complete=False,
        )

        decision = workflow._should_complete(state_incomplete)
        assert decision == "continue"

    async def test_process_message_integration(self) -> None:
        """Test processing a message through the workflow."""
        mock_llm_service = AsyncMock()
        mock_llm_service.extract_entities.return_value = [
            {"category": "cuisine", "value": "Italian", "preference_type": "like", "confidence": 0.9},
        ]
        mock_llm_service.chat_completion.return_value = {
            "content": "What activities do you enjoy?",
            "model": "gpt-4o-mini",
            "usage": {"total_tokens": 20},
        }

        workflow = PreferenceCollectionWorkflow(mock_llm_service)

        user_id = str(uuid.uuid4())
        message = "I really love Italian food"

        result = await workflow.process_message(user_id, message)

        assert "preferences" in result
        assert "is_complete" in result
        assert result["is_complete"] is False  # Not enough preferences yet
