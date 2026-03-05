"""LangGraph workflow for guided tour management."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, TypedDict, Literal

from langgraph.graph import StateGraph, END

from src.core.exceptions import PhoenixException
from src.services.llm_service import LLMService
from src.tour.orchestrator import TourOrchestrator, TourStatus
from src.tour.content import ContentContext, ContentType
from src.tour.adaptive import AdaptiveLearningEngine

logger = logging.getLogger(__name__)


class TourWorkflowState(TypedDict):
    """State for tour workflow."""

    # Input
    user_id: str
    route_id: str
    action: str
    language: str

    # Tour state
    tour_id: str | None
    status: str
    current_poi_id: str | None
    location: dict[str, float] | None

    # Content
    content_to_deliver: list[dict[str, Any]]
    content_delivered: list[str]

    # Feedback
    feedback_type: str | None
    feedback_rating: int | None

    # Response
    response: str | None
    next_action: str | None
    error: str | None

    # Metadata
    metadata: dict[str, Any]


class TourWorkflowAgent:
    """Agent for managing tour workflows."""

    def __init__(
        self,
        orchestrator: TourOrchestrator | None = None,
        learning_engine: AdaptiveLearningEngine | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        """Initialize tour workflow agent.

        Args:
            orchestrator: Optional tour orchestrator
            learning_engine: Optional adaptive learning engine
            llm_service: Optional LLM service
        """
        self.orchestrator = orchestrator or TourOrchestrator()
        self.learning_engine = learning_engine or AdaptiveLearningEngine()
        self.llm_service = llm_service or LLMService()

        self._build_workflow()

    def _build_workflow(self) -> None:
        """Build the tour workflow graph."""
        self.workflow = StateGraph(TourWorkflowState)

        # Add nodes
        self.workflow.add_node("parse_input", self._parse_input)
        self.workflow.add_node("validate_action", self._validate_action)
        self.workflow.add_node("execute_tour_action", self._execute_tour_action)
        self.workflow.add_node("generate_content", self._generate_content)
        self.workflow.add_node("process_feedback", self._process_feedback)
        self.workflow.add_node("generate_response", self._generate_response)
        self.workflow.add_node("handle_error", self._handle_error)

        # Set entry point
        self.workflow.set_entry_point("parse_input")

        # Add conditional edges
        self.workflow.add_conditional_edges(
            "parse_input",
            self._route_parse_input,
            {
                "validate": "validate_action",
                "error": "handle_error",
            },
        )

        self.workflow.add_conditional_edges(
            "validate_action",
            self._route_validate_action,
            {
                "start_tour": "execute_tour_action",
                "pause_tour": "execute_tour_action",
                "resume_tour": "execute_tour_action",
                "complete_tour": "execute_tour_action",
                "cancel_tour": "execute_tour_action",
                "update_location": "execute_tour_action",
                "skip_poi": "execute_tour_action",
                "submit_feedback": "process_feedback",
                "get_status": "generate_response",
                "error": "handle_error",
            },
        )

        self.workflow.add_conditional_edges(
            "execute_tour_action",
            self._route_execute_action,
            {
                "generate_content": "generate_content",
                "generate_response": "generate_response",
            },
        )

        self.workflow.add_edge("generate_content", "generate_response")
        self.workflow.add_edge("process_feedback", "generate_response")
        self.workflow.add_edge("generate_response", END)
        self.workflow.add_edge("handle_error", END)

        # Compile the workflow
        self.compiled_workflow = self.workflow.compile()

    async def run(
        self,
        user_id: str,
        route_id: str,
        action: str,
        language: str = "en",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run the tour workflow.

        Args:
            user_id: User ID
            route_id: Route ID
            action: Action to perform
            language: Content language
            **kwargs: Additional parameters

        Returns:
            Workflow result
        """
        initial_state: TourWorkflowState = {
            "user_id": user_id,
            "route_id": route_id,
            "action": action,
            "language": language,
            "tour_id": kwargs.get("tour_id"),
            "status": "unknown",
            "current_poi_id": kwargs.get("poi_id"),
            "location": kwargs.get("location"),
            "content_to_deliver": [],
            "content_delivered": [],
            "feedback_type": kwargs.get("feedback_type"),
            "feedback_rating": kwargs.get("rating"),
            "response": None,
            "next_action": None,
            "error": None,
            "metadata": kwargs.get("metadata", {}),
        }

        try:
            result = await self.compiled_workflow.ainvoke(initial_state)
            return result
        except Exception as e:
            logger.error(f"Tour workflow error: {e}")
            return {
                **initial_state,
                "error": str(e),
                "response": "I'm sorry, something went wrong with your tour.",
            }

    async def _parse_input(
        self,
        state: TourWorkflowState,
    ) -> TourWorkflowState:
        """Parse and validate input.

        Args:
            state: Current workflow state

        Returns:
            Updated state
        """
        try:
            # Validate UUIDs
            uuid.UUID(state["user_id"])

            # Normalize action
            state["action"] = state["action"].lower().replace("-", "_")

            # Set tour_id if provided
            if not state.get("tour_id") and state["action"] in (
                "pause_tour",
                "resume_tour",
                "complete_tour",
                "cancel_tour",
                "update_location",
                "skip_poi",
                "submit_feedback",
                "get_status",
            ):
                state["error"] = f"tour_id required for action {state['action']}"

            return state

        except ValueError:
            state["error"] = "Invalid user_id format"
            return state
        except Exception as e:
            state["error"] = f"Input parsing error: {e}"
            return state

    async def _validate_action(
        self,
        state: TourWorkflowState,
    ) -> TourWorkflowState:
        """Validate the requested action.

        Args:
            state: Current workflow state

        Returns:
            Updated state
        """
        valid_actions = {
            "start_tour",
            "pause_tour",
            "resume_tour",
            "complete_tour",
            "cancel_tour",
            "update_location",
            "skip_poi",
            "submit_feedback",
            "get_status",
        }

        if state["action"] not in valid_actions:
            state["error"] = f"Invalid action: {state['action']}"
            return state

        # Validate action-specific requirements
        if state["action"] == "update_location":
            location = state.get("location")
            if not location or "lat" not in location or "lng" not in location:
                state["error"] = "Location must include lat and lng"
                return state

        return state

    async def _execute_tour_action(
        self,
        state: TourWorkflowState,
    ) -> TourWorkflowState:
        """Execute the tour action.

        Args:
            state: Current workflow state

        Returns:
            Updated state
        """
        action = state["action"]
        user_id = uuid.UUID(state["user_id"])
        tour_id = state.get("tour_id")

        try:
            if action == "start_tour":
                result = await self.orchestrator.start_tour(
                    user_id=user_id,
                    route_id=state["route_id"],
                    pois=state["metadata"].get("pois", []),
                    metadata={"language": state["language"]},
                )
                state["tour_id"] = result.tour_id
                state["status"] = result.status.value

            elif action == "pause_tour":
                result = await self.orchestrator.pause_tour(tour_id)
                state["status"] = result.status.value

            elif action == "resume_tour":
                result = await self.orchestrator.resume_tour(tour_id)
                state["status"] = result.status.value

            elif action == "complete_tour":
                result = await self.orchestrator.complete_tour(tour_id)
                state["status"] = result.status.value

            elif action == "cancel_tour":
                result = await self.orchestrator.cancel_tour(
                    tour_id,
                    reason=state["metadata"].get("reason"),
                )
                state["status"] = result.status.value

            elif action == "update_location":
                location = state["location"]
                result, events = await self.orchestrator.update_location(
                    tour_id=tour_id,
                    location=location,
                    accuracy_meters=state["metadata"].get("accuracy"),
                )
                state["status"] = result.status.value
                state["metadata"]["triggered_events"] = events

            elif action == "skip_poi":
                poi_id = state.get("current_poi_id")
                result = await self.orchestrator.skip_poi(tour_id, poi_id)
                state["status"] = result.status.value

            elif action == "get_status":
                result = await self.orchestrator.get_tour_state(tour_id)
                state["status"] = result.status.value
                state["metadata"]["tour_details"] = result.to_dict()

        except Exception as e:
            state["error"] = f"Action execution error: {e}"
            logger.error(f"Error executing action {action}: {e}")

        return state

    async def _generate_content(
        self,
        state: TourWorkflowState,
    ) -> TourWorkflowState:
        """Generate content for delivery.

        Args:
            state: Current workflow state

        Returns:
            Updated state
        """
        # This would integrate with content generation
        # For now, just mark that content should be generated
        state["metadata"]["needs_content"] = True

        return state

    async def _process_feedback(
        self,
        state: TourWorkflowState,
    ) -> TourWorkflowState:
        """Process user feedback.

        Args:
            state: Current workflow state

        Returns:
            Updated state
        """
        from src.tour.adaptive import FeedbackType

        user_id = uuid.UUID(state["user_id"])
        tour_id = state.get("tour_id")
        feedback_type = state.get("feedback_type")
        rating = state.get("feedback_rating")
        poi_id = state.get("current_poi_id")

        try:
            if feedback_type:
                fb_type = FeedbackType(feedback_type)
                await self.learning_engine.record_feedback(
                    user_id=user_id,
                    feedback_type=fb_type,
                    tour_id=tour_id,
                    rating=rating,
                    poi_id=poi_id,
                )
                state["status"] = "feedback_recorded"
        except Exception as e:
            state["error"] = f"Feedback processing error: {e}"
            logger.error(f"Error processing feedback: {e}")

        return state

    async def _generate_response(
        self,
        state: TourWorkflowState,
    ) -> TourWorkflowState:
        """Generate natural language response.

        Args:
            state: Current workflow state

        Returns:
            Updated state
        """
        action = state["action"]
        status = state["status"]

        # Generate contextual response
        responses = {
            "start_tour": f"Your guided tour has started! Tour ID: {state.get('tour_id')}",
            "pause_tour": "Tour paused. Take your time!",
            "resume_tour": "Tour resumed. Let's continue!",
            "complete_tour": "Congratulations! You've completed your tour.",
            "cancel_tour": "Tour has been cancelled.",
            "update_location": "Location updated.",
            "skip_poi": f"Skipped {state.get('current_poi_id', 'POI')}.",
            "submit_feedback": "Thank you for your feedback!",
            "get_status": f"Tour status: {status}",
        }

        state["response"] = responses.get(action, "Action completed.")

        return state

    async def _handle_error(
        self,
        state: TourWorkflowState,
    ) -> TourWorkflowState:
        """Handle workflow errors.

        Args:
            state: Current workflow state

        Returns:
            Updated state
        """
        error = state.get("error", "An unknown error occurred")

        # Generate user-friendly error message
        if "Invalid action" in error:
            state["response"] = "I'm not sure what you want me to do. Please try again."
        elif "required for action" in error:
            state["response"] = "I need more information to do that."
        elif "Invalid user_id" in error:
            state["response"] = "There's a problem with your account. Please log in again."
        else:
            state["response"] = "Something went wrong. Please try again."

        return state

    def _route_parse_input(
        self,
        state: TourWorkflowState,
    ) -> Literal["validate", "error"]:
        """Route after parsing input.

        Args:
            state: Current workflow state

        Returns:
            Next node
        """
        if state.get("error"):
            return "error"
        return "validate"

    def _route_validate_action(
        self,
        state: TourWorkflowState,
    ) -> Literal[
        "start_tour",
        "pause_tour",
        "resume_tour",
        "complete_tour",
        "cancel_tour",
        "update_location",
        "skip_poi",
        "submit_feedback",
        "get_status",
        "error",
    ]:
        """Route after validating action.

        Args:
            state: Current workflow state

        Returns:
            Next node
        """
        if state.get("error"):
            return "error"
        return state["action"]  # type: ignore

    def _route_execute_action(
        self,
        state: TourWorkflowState,
    ) -> Literal["generate_content", "generate_response"]:
        """Route after executing action.

        Args:
            state: Current workflow state

        Returns:
            Next node
        """
        # If content was triggered, generate it
        if state["metadata"].get("triggered_events"):
            return "generate_content"
        return "generate_response"


# Global instance
tour_workflow_agent = TourWorkflowAgent()


def get_tour_workflow_agent() -> TourWorkflowAgent:
    """Get global tour workflow agent instance.

    Returns:
        Tour workflow agent instance
    """
    return tour_workflow_agent
