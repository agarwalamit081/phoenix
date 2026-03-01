"""LiveKit service for real-time voice room management."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import aiohttp
from livekit import rtc
from livekit.api import AccessToken, VideoGrants
from livekit.api.room_service import RoomService

from src.config.settings import settings
from src.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class LiveKitService:
    """Service for managing LiveKit rooms and tokens."""

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        url: str | None = None,
    ) -> None:
        """Initialize LiveKit service.

        Args:
            api_key: LiveKit API key (defaults to settings)
            api_secret: LiveKit API secret (defaults to settings)
            url: LiveKit server URL (defaults to settings)
        """
        self.api_key = api_key or settings.livekit_api_key
        self.api_secret = api_secret or settings.livekit_api_secret
        self.url = url or settings.livekit_url

        if not all([self.api_key, self.api_secret, self.url]):
            logger.warning("LiveKit credentials not fully configured")

        self._room_service: RoomService | None = None
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session.

        Returns:
            aiohttp ClientSession
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    @property
    def room_service(self) -> RoomService:
        """Get or create room service.

        Returns:
            RoomService instance

        Raises:
            RuntimeError: If LiveKit credentials are not configured
        """
        if not self._room_service:
            if not all([self.api_key, self.api_secret, self.url]):
                raise RuntimeError("LiveKit credentials not configured")

            # Create RoomService without session - it will create its own
            self._room_service = RoomService(
                None,  # RoomService will create its own aiohttp session
                self.url,
                self.api_key,
                self.api_secret,
            )

        return self._room_service

    async def close(self) -> None:
        """Close the LiveKit service and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def is_configured(self) -> bool:
        """Check if LiveKit is properly configured.

        Returns:
            True if credentials are set
        """
        return bool(
            self.api_key
            and self.api_secret
            and self.url
        )

    async def create_room(
        self,
        room_name: str | None = None,
        empty_timeout: int = 300,
        max_participants: int = 10,
    ) -> dict[str, Any]:
        """Create a new LiveKit room.

        Args:
            room_name: Optional room name (defaults to auto-generated)
            empty_timeout: Seconds before room is deleted when empty
            max_participants: Maximum number of participants

        Returns:
            Room creation response
        """
        if not self.is_configured():
            raise RuntimeError("LiveKit is not configured")

        if not room_name:
            room_name = f"voice-room-{uuid.uuid4()}"

        try:
            from livekit.api import CreateRoomRequest
            from livekit.api.room_service import RoomService

            # Get or create HTTP session
            session = await self._get_session()

            # Create RoomService with proper session
            room_service = RoomService(
                session,
                self.url,
                self.api_key,
                self.api_secret,
            )

            request = CreateRoomRequest(
                name=room_name,
                empty_timeout=empty_timeout,
                max_participants=max_participants,
            )

            room = await room_service.create_room(request)

            logger.info(f"Created LiveKit room: {room_name}")

            return {
                "sid": room.sid,
                "name": room.name,
                "empty_timeout": room.empty_timeout,
                "max_participants": room.max_participants,
                "creation_time": room.creation_time,
                "url": self.url,
            }

        except Exception as e:
            logger.error(f"Failed to create LiveKit room: {e}")
            raise

    async def get_room(self, room_name: str) -> dict[str, Any] | None:
        """Get room information.

        Args:
            room_name: Room name

        Returns:
            Room information or None if not found
        """
        if not self.is_configured():
            return None

        try:
            from livekit.api.room_service import ListRoomsRequest

            session = await self._get_session()
            # Use list_rooms and filter by name since get_room might not exist
            rooms = await self.room_service.list_rooms(session, ListRoomsRequest())

            for room in rooms:
                if room.name == room_name:
                    return {
                        "sid": room.sid,
                        "name": room.name,
                        "empty_timeout": room.empty_timeout,
                        "max_participants": room.max_participants,
                        "creation_time": room.creation_time,
                        "num_participants": room.num_participants,
                    }

            return None

        except Exception as e:
            logger.error(f"Failed to get room {room_name}: {e}")
            return None

    async def list_rooms(self) -> list[dict[str, Any]]:
        """List all active rooms.

        Returns:
            List of room information
        """
        if not self.is_configured():
            return []

        try:
            from livekit.api.room_service import ListRoomsRequest

            session = await self._get_session()
            rooms = await self.room_service.list_rooms(session, ListRoomsRequest())

            return [
                {
                    "sid": room.sid,
                    "name": room.name,
                    "num_participants": room.num_participants,
                    "max_participants": room.max_participants,
                }
                for room in rooms
            ]

        except Exception as e:
            logger.error(f"Failed to list rooms: {e}")
            return []

    async def delete_room(self, room_name: str) -> bool:
        """Delete a room.

        Args:
            room_name: Room name

        Returns:
            True if deleted successfully
        """
        if not self.is_configured():
            return False

        try:
            from livekit.api.room_service import DeleteRoomRequest

            session = await self._get_session()
            await self.room_service.delete_room(session, DeleteRoomRequest(room=room_name))
            logger.info(f"Deleted LiveKit room: {room_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete room {room_name}: {e}")
            return False

    def create_access_token(
        self,
        room_name: str,
        participant_id: str | None = None,
        participant_name: str | None = None,
        metadata: str | None = None,
        can_publish: bool = True,
        can_subscribe: bool = True,
        can_publish_data: bool = True,
        ttl: int = 3600,
    ) -> str:
        """Create an access token for a participant.

        Args:
            room_name: Room name
            participant_id: Optional participant ID
            participant_name: Optional participant display name
            metadata: Optional participant metadata
            can_publish: Whether participant can publish audio/video
            can_subscribe: Whether participant can subscribe
            can_publish_data: Whether participant can publish data
            ttl: Token time-to-live in seconds

        Returns:
            JWT access token
        """
        if not self.is_configured():
            raise RuntimeError("LiveKit is not configured")

        if not participant_id:
            participant_id = str(uuid.uuid4())

        grants = VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=can_publish,
            can_subscribe=can_subscribe,
            can_publish_data=can_publish_data,
        )

        token = AccessToken(self.api_key, self.api_secret)
        token.with_identity(participant_id)
        token.with_name(participant_name or participant_id)
        token.with_grants(grants)
        token.with_metadata(metadata or "")
        # Convert TTL (int seconds) to timedelta
        import datetime
        token.with_ttl(datetime.timedelta(seconds=ttl))

        jwt = token.to_jwt()

        logger.debug(f"Created access token for {participant_id} in room {room_name}")

        return jwt

    async def remove_participant(
        self,
        room_name: str,
        participant_id: str,
    ) -> bool:
        """Remove a participant from a room.

        Args:
            room_name: Room name
            participant_id: Participant ID

        Returns:
            True if removed successfully
        """
        if not self.is_configured():
            return False

        try:
            from livekit.api.room_service import RemoveParticipantRequest

            session = await self._get_session()
            await self.room_service.remove_participant(
                session, RemoveParticipantRequest(room=room_name, identity=participant_id)
            )
            logger.info(f"Removed participant {participant_id} from room {room_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to remove participant: {e}")
            return False

    async def get_room_participants(
        self,
        room_name: str,
    ) -> list[dict[str, Any]]:
        """Get all participants in a room.

        Args:
            room_name: Room name

        Returns:
            List of participant information
        """
        if not self.is_configured():
            return []

        try:
            # LiveKit doesn't have a direct API for this
            # We would need to track participants ourselves
            # or use room service to get room info
            room_info = await self.get_room(room_name)
            if room_info:
                return [
                    {
                        "sid": participant_id,
                        "identity": participant_id,
                    }
                    for participant_id in []  # Would need actual participant tracking
                ]

            return []

        except Exception as e:
            logger.error(f"Failed to get room participants: {e}")
            return []


class LiveKitRoomManager:
    """High-level manager for LiveKit voice rooms."""

    def __init__(self) -> None:
        """Initialize room manager."""
        self.service = LiveKitService()
        self._active_rooms: dict[str, dict[str, Any]] = {}

    async def create_voice_room(
        self,
        user_id: uuid.UUID,
        tour_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new voice room for a user.

        Args:
            user_id: User ID
            tour_id: Optional tour ID

        Returns:
            Room information with access token
        """
        room_name = self._generate_room_name(user_id, tour_id)

        try:
            room_info = await self.service.create_room(
                room_name=room_name,
                empty_timeout=300,
                max_participants=5,
            )

            # Try to dispatch agent job for CLI-based worker
            # The CLI worker will auto-register and receive jobs
            await self._dispatch_agent_job(room_name)

            # Create access token for the user
            access_token = self.service.create_access_token(
                room_name=room_name,
                participant_id=str(user_id),
                participant_name=f"User-{user_id}",
                metadata=f'{{"user_id": "{user_id}", "tour_id": "{tour_id or ""}"}}',
                ttl=3600,
            )

            self._active_rooms[room_name] = {
                "room_info": room_info,
                "user_id": user_id,
                "tour_id": tour_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "participants": [str(user_id)],
            }

            return {
                "room_name": room_name,
                "room_sid": room_info["sid"],
                "url": room_info["url"],
                "access_token": access_token,
                "participant_id": str(user_id),
                "ttl": 3600,
            }

        except Exception as e:
            logger.error(f"Failed to create voice room: {e}")
            raise

    async def _dispatch_agent_job(self, room_name: str) -> None:
        """Dispatch a job to the voice agent worker for a room via AgentDispatchService.

        Args:
            room_name: The room to dispatch the agent to
        """
        try:
            from livekit.api.agent_dispatch_service import AgentDispatchService, CreateAgentDispatchRequest

            # Get HTTP session from the service
            session = await self.service._get_session()

            # Create AgentDispatchService
            dispatch_service = AgentDispatchService(
                session,
                self.service.url.replace("wss://", "https://").replace("ws://", "http://"),
                self.service.api_key,
                self.service.api_secret,
            )

            # Create the dispatch request - room field expects a string, not Room object
            dispatch_request = CreateAgentDispatchRequest()
            dispatch_request.agent_name = "travel-voice-agent"
            dispatch_request.room = room_name
            dispatch_request.metadata = '{"source": "phoenix-voice-service"}'

            # Create the dispatch (this creates a job for the worker)
            dispatch = await dispatch_service.create_dispatch(dispatch_request)

            logger.info(f"Agent dispatch created for room {room_name}: {dispatch.id}")

        except Exception as e:
            import traceback
            logger.error(f"Failed to dispatch agent job for room {room_name}: {e}")
            logger.error(f"Dispatch error traceback: {traceback.format_exc()}")
            # Don't fail the room creation if dispatch fails
            # The room will still work, just without the agent
            pass

    async def join_voice_room(
        self,
        room_name: str,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Join an existing voice room.

        Args:
            room_name: Room name
            user_id: User ID

        Returns:
            Join information with access token
        """
        if room_name not in self._active_rooms:
            raise ValidationError(f"Room {room_name} not found")

        access_token = self.service.create_access_token(
            room_name=room_name,
            participant_id=str(user_id),
            participant_name=f"User-{user_id}",
            metadata=f'{{"user_id": "{user_id}"}}',
            ttl=3600,
        )

        # Add to participants if not already present
        user_str = str(user_id)
        if user_str not in self._active_rooms[room_name]["participants"]:
            self._active_rooms[room_name]["participants"].append(user_str)

        return {
            "room_name": room_name,
            "access_token": access_token,
            "participant_id": user_str,
            "ttl": 3600,
        }

    async def leave_voice_room(
        self,
        room_name: str,
        user_id: uuid.UUID,
    ) -> bool:
        """Leave a voice room.

        Args:
            room_name: Room name
            user_id: User ID

        Returns:
            True if left successfully
        """
        if room_name not in self._active_rooms:
            return False

        user_str = str(user_id)
        if user_str in self._active_rooms[room_name]["participants"]:
            self._active_rooms[room_name]["participants"].remove(user_str)

        # Remove participant from LiveKit room
        await self.service.remove_participant(room_name, user_str)

        # Clean up room if empty
        if not self._active_rooms[room_name]["participants"]:
            await self.service.delete_room(room_name)
            del self._active_rooms[room_name]

        return True

    def _generate_room_name(
        self,
        user_id: uuid.UUID,
        tour_id: str | None = None,
    ) -> str:
        """Generate a unique room name.

        Args:
            user_id: User ID
            tour_id: Optional tour ID

        Returns:
            Room name
        """
        if tour_id:
            return f"tour-{tour_id}"
        return f"voice-{user_id}-{uuid.uuid4().hex[:8]}"

    async def get_active_room(self, room_name: str) -> dict[str, Any] | None:
        """Get active room information.

        Args:
            room_name: Room name

        Returns:
            Room information or None
        """
        return self._active_rooms.get(room_name)

    async def cleanup_expired_rooms(self, max_age_seconds: int = 3600) -> int:
        """Clean up expired rooms.

        Args:
            max_age_seconds: Maximum room age in seconds

        Returns:
            Number of rooms cleaned up
        """
        now = datetime.now(timezone.utc)
        cleaned = 0

        for room_name, room_data in list(self._active_rooms.items()):
            created_at = datetime.fromisoformat(room_data["created_at"])
            age = (now - created_at).total_seconds()

            if age > max_age_seconds:
                await self.service.delete_room(room_name)
                del self._active_rooms[room_name]
                cleaned += 1

        return cleaned


# Global instance
livekit_manager = LiveKitRoomManager()
