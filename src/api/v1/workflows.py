"""Workflow API endpoints (compatibility implementation)."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.api.dependencies import CurrentUser

router = APIRouter()

_WORKFLOWS: dict[uuid.UUID, dict[str, Any]] = {}
_USER_WORKFLOWS: dict[uuid.UUID, list[uuid.UUID]] = {}


class WorkflowMessageRequest(BaseModel):
    """Request payload for submitting a workflow message."""

    message: str = Field(..., min_length=1, max_length=5000)


@router.post("/preferences/start", status_code=201)
async def start_preference_workflow(user: CurrentUser) -> dict[str, Any]:
    """Start a preference collection workflow."""
    workflow_id = uuid.uuid4()
    workflow = {
        "workflow_id": workflow_id,
        "user_id": user.id,
        "status": "in_progress",
        "messages": [],
        "extracted_preferences": [],
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    _WORKFLOWS[workflow_id] = workflow
    _USER_WORKFLOWS.setdefault(user.id, []).append(workflow_id)
    return {"workflow_id": str(workflow_id), "status": workflow["status"]}


@router.post("/preferences/{workflow_id}/message")
async def submit_preference_workflow_message(
    workflow_id: uuid.UUID,
    data: WorkflowMessageRequest,
    user: CurrentUser,
) -> dict[str, Any]:
    """Submit a message to a workflow."""
    workflow = _WORKFLOWS.get(workflow_id)
    if workflow is None or workflow["user_id"] != user.id:
        from src.core.exceptions import NotFoundError

        raise NotFoundError("Workflow", str(workflow_id))

    workflow["messages"].append(data.message)
    is_complete = len(workflow["messages"]) >= 3
    workflow["status"] = "completed" if is_complete else "in_progress"
    workflow["updated_at"] = datetime.now()

    return {
        "workflow_id": str(workflow_id),
        "response": "Preference noted.",
        "extracted_preferences": workflow["extracted_preferences"],
        "is_complete": is_complete,
        "status": workflow["status"],
    }


@router.get("/preferences/{workflow_id}")
async def get_preference_workflow(
    workflow_id: str,
    user: CurrentUser,
) -> dict[str, Any]:
    """Get workflow status."""
    if workflow_id == "history":
        return await list_preference_workflow_history(user)

    try:
        workflow_uuid = uuid.UUID(workflow_id)
    except ValueError:
        from src.core.exceptions import NotFoundError

        raise NotFoundError("Workflow", workflow_id)

    workflow = _WORKFLOWS.get(workflow_uuid)
    if workflow is None or workflow["user_id"] != user.id:
        from src.core.exceptions import NotFoundError

        raise NotFoundError("Workflow", workflow_id)

    return {
        "workflow_id": str(workflow_uuid),
        "status": workflow["status"],
        "messages_count": len(workflow["messages"]),
        "updated_at": workflow["updated_at"],
    }


@router.post("/preferences/{workflow_id}/cancel")
async def cancel_preference_workflow(
    workflow_id: uuid.UUID,
    user: CurrentUser,
) -> dict[str, Any]:
    """Cancel an active workflow."""
    workflow = _WORKFLOWS.get(workflow_id)
    if workflow is None or workflow["user_id"] != user.id:
        from src.core.exceptions import NotFoundError

        raise NotFoundError("Workflow", str(workflow_id))

    workflow["status"] = "cancelled"
    workflow["updated_at"] = datetime.now()
    return {"workflow_id": str(workflow_id), "status": "cancelled"}


@router.get("/preferences/history")
async def list_preference_workflow_history(user: CurrentUser) -> dict[str, Any]:
    """List workflow history for the current user."""
    workflow_ids = _USER_WORKFLOWS.get(user.id, [])
    workflows = [
        {
            "workflow_id": str(wid),
            "status": _WORKFLOWS[wid]["status"],
            "updated_at": _WORKFLOWS[wid]["updated_at"],
        }
        for wid in workflow_ids
        if wid in _WORKFLOWS
    ]
    return {"workflows": workflows, "total": len(workflows)}
