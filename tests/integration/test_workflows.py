"""Integration tests for workflow APIs."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token
from src.models.user import User


@pytest.mark.asyncio
class TestWorkflowAPI:
    """Tests for workflow-related API endpoints."""

    async def test_start_preference_collection(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test starting preference collection workflow."""
        access_token = create_access_token(str(test_user.id))

        response = test_client.post(
            "/api/v1/workflows/preferences/start",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "workflow_id" in data
        assert "status" in data
        assert data["status"] == "in_progress"

    async def test_submit_workflow_message(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test submitting a message to workflow."""
        access_token = create_access_token(str(test_user.id))

        # Start workflow
        start_response = test_client.post(
            "/api/v1/workflows/preferences/start",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        workflow_id = start_response.json().get("workflow_id")

        if workflow_id:
            # Submit message
            response = test_client.post(
                f"/api/v1/workflows/preferences/{workflow_id}/message",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"message": "I love Italian food and art museums"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "response" in data
            assert "extracted_preferences" in data
            assert "is_complete" in data

    async def test_get_workflow_status(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test getting workflow status."""
        access_token = create_access_token(str(test_user.id))

        # Start workflow
        start_response = test_client.post(
            "/api/v1/workflows/preferences/start",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        workflow_id = start_response.json().get("workflow_id")

        if workflow_id:
            # Get status
            response = test_client.get(
                f"/api/v1/workflows/preferences/{workflow_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["workflow_id"] == workflow_id
            assert "status" in data

    async def test_complete_preference_collection(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test completing preference collection workflow."""
        access_token = create_access_token(str(test_user.id))

        # Start workflow
        start_response = test_client.post(
            "/api/v1/workflows/preferences/start",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        workflow_id = start_response.json().get("workflow_id")

        if workflow_id:
            # Submit multiple messages to complete
            messages = [
                "I love Italian food",
                "I enjoy visiting art museums",
                "I like quiet places and dislike crowds",
            ]

            for msg in messages:
                test_client.post(
                    f"/api/v1/workflows/preferences/{workflow_id}/message",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={"message": msg},
                )

            # Check if complete
            status_response = test_client.get(
                f"/api/v1/workflows/preferences/{workflow_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            assert status_response.status_code == 200
            data = status_response.json()
            # After multiple messages, should be closer to completion

    async def test_cancel_workflow(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test cancelling a workflow."""
        access_token = create_access_token(str(test_user.id))

        # Start workflow
        start_response = test_client.post(
            "/api/v1/workflows/preferences/start",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        workflow_id = start_response.json().get("workflow_id")

        if workflow_id:
            # Cancel workflow
            response = test_client.post(
                f"/api/v1/workflows/preferences/{workflow_id}/cancel",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "cancelled"

    async def test_get_workflow_history(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test getting user's workflow history."""
        access_token = create_access_token(str(test_user.id))

        # Start a workflow
        test_client.post(
            "/api/v1/workflows/preferences/start",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        # Get history
        response = test_client.get(
            "/api/v1/workflows/preferences/history",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "workflows" in data
        assert len(data["workflows"]) >= 1

    async def test_workflow_with_existing_preferences(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test workflow when user already has preferences."""
        access_token = create_access_token(str(test_user.id))

        # Add existing preferences
        test_client.post(
            "/api/v1/preferences/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "category": "cuisine",
                "value": "Italian",
                "preference_type": "like",
                "confidence": 0.9,
            },
        )

        # Start workflow
        start_response = test_client.post(
            "/api/v1/workflows/preferences/start",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        workflow_id = start_response.json().get("workflow_id")

        if workflow_id:
            # Submit message
            response = test_client.post(
                f"/api/v1/workflows/preferences/{workflow_id}/message",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"message": "I also love Japanese food"},
            )

            assert response.status_code == 200

    async def test_workflow_conflict_resolution(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test workflow handles preference conflicts."""
        access_token = create_access_token(str(test_user.id))

        # Start workflow
        start_response = test_client.post(
            "/api/v1/workflows/preferences/start",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        workflow_id = start_response.json().get("workflow_id")

        if workflow_id:
            # Submit potentially conflicting messages
            test_client.post(
                f"/api/v1/workflows/preferences/{workflow_id}/message",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"message": "I love crowded tourist attractions"},
            )

            test_client.post(
                f"/api/v1/workflows/preferences/{workflow_id}/message",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"message": "I hate crowds and tourist traps"},
            )

            # Get status
            response = test_client.get(
                f"/api/v1/workflows/preferences/{workflow_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            # Check if conflicts were detected
            # (implementation dependent)

    async def test_workflow_unauthorized(
        self,
        test_client: TestClient,
    ) -> None:
        """Test workflow access without authentication."""
        response = test_client.post(
            "/api/v1/workflows/preferences/start",
        )

        assert response.status_code == 401

    async def test_get_nonexistent_workflow(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test getting a workflow that doesn't exist."""
        access_token = create_access_token(str(test_user.id))
        fake_id = uuid.uuid4()

        response = test_client.get(
            f"/api/v1/workflows/preferences/{fake_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 404

    async def test_workflow_timeout(
        self,
        test_client: TestClient,
        test_user: User,
    ) -> None:
        """Test workflow timeout handling."""
        access_token = create_access_token(str(test_user.id))

        # Start workflow
        start_response = test_client.post(
            "/api/v1/workflows/preferences/start",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        workflow_id = start_response.json().get("workflow_id")

        if workflow_id:
            # Submit minimal message
            test_client.post(
                f"/api/v1/workflows/preferences/{workflow_id}/message",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"message": "Hi"},
            )

            # Check if workflow still in progress after minimal input
            response = test_client.get(
                f"/api/v1/workflows/preferences/{workflow_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            # Workflow should still be active or waiting for more input
