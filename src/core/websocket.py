"""WebSocket connection manager for real-time communication."""

import logging
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


def _get_timestamp() -> str:
    """Get current ISO timestamp."""
    return datetime.now(timezone.utc).isoformat()


class ConnectionManager:
    """WebSocket connection manager for managing active connections."""

    def __init__(self) -> None:
        """Initialize connection manager."""
        self.active_connections: dict[str, dict[str, WebSocket]] = defaultdict(dict)
        self.user_connections: dict[uuid.UUID, set[str]] = defaultdict(set)
        self.connection_handlers: dict[str, list[Callable]] = defaultdict(list)

    async def connect(
        self,
        websocket: WebSocket,
        room_id: str,
        user_id: uuid.UUID,
    ) -> str:
        """Connect a client to a room.

        Args:
            websocket: WebSocket connection (must already be accepted)
            room_id: Room identifier
            user_id: User ID

        Returns:
            Connection ID
        """
        # Note: WebSocket should already be accepted by the caller
        connection_id = str(uuid.uuid4())
        self.active_connections[room_id][connection_id] = websocket
        self.user_connections[user_id].add(connection_id)

        logger.info(
            f"WebSocket connected: user={user_id}, room={room_id}, conn={connection_id}"
        )

        await self._emit("connected", {"connection_id": connection_id}, room_id, connection_id)

        return connection_id

    async def disconnect(
        self,
        connection_id: str,
        room_id: str,
        user_id: uuid.UUID,
    ) -> None:
        """Disconnect a client from a room.

        Args:
            connection_id: Connection ID
            room_id: Room identifier
            user_id: User ID
        """
        if connection_id in self.active_connections[room_id]:
            del self.active_connections[room_id][connection_id]

        if connection_id in self.user_connections[user_id]:
            self.user_connections[user_id].discard(connection_id)

        if not self.user_connections[user_id]:
            del self.user_connections[user_id]

        logger.info(
            f"WebSocket disconnected: user={user_id}, room={room_id}, conn={connection_id}"
        )

        await self._emit("disconnected", {"connection_id": connection_id}, room_id, connection_id)

    async def send_personal_message(
        self,
        message: dict[str, Any],
        room_id: str,
        connection_id: str,
    ) -> bool:
        """Send a message to a specific connection.

        Args:
            message: Message payload
            room_id: Room identifier
            connection_id: Connection ID

        Returns:
            True if message was sent successfully
        """
        websocket = self.active_connections[room_id].get(connection_id)
        if websocket:
            try:
                await websocket.send_json(message)
                return True
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                return False
        return False

    async def broadcast(
        self,
        message: dict[str, Any],
        room_id: str,
        exclude_connection_id: str | None = None,
    ) -> int:
        """Broadcast a message to all connections in a room.

        Args:
            message: Message payload
            room_id: Room identifier
            exclude_connection_id: Optional connection to exclude

        Returns:
            Number of clients the message was sent to
        """
        if room_id not in self.active_connections:
            return 0

        sent_count = 0
        for conn_id, websocket in self.active_connections[room_id].items():
            if exclude_connection_id and conn_id == exclude_connection_id:
                continue

            try:
                await websocket.send_json(message)
                sent_count += 1
            except Exception as e:
                logger.error(f"Error broadcasting to {conn_id}: {e}")

        return sent_count

    async def send_to_user(
        self,
        message: dict[str, Any],
        user_id: uuid.UUID,
    ) -> int:
        """Send a message to all connections for a user.

        Args:
            message: Message payload
            user_id: User ID

        Returns:
            Number of clients the message was sent to
        """
        sent_count = 0
        connection_ids = self.user_connections.get(user_id, set())

        for conn_id in connection_ids:
            for room_id, connections in self.active_connections.items():
                if conn_id in connections:
                    if await self.send_personal_message(message, room_id, conn_id):
                        sent_count += 1

        return sent_count

    async def _emit(
        self,
        event_type: str,
        data: dict[str, Any],
        room_id: str,
        connection_id: str | None = None,
    ) -> None:
        """Emit an event to connections.

        Args:
            event_type: Type of event
            data: Event data
            room_id: Room identifier
            connection_id: Optional specific connection
        """
        message = {
            "type": event_type,
            "data": data,
            "timestamp": _get_timestamp(),
        }

        if connection_id:
            await self.send_personal_message(message, room_id, connection_id)
        else:
            await self.broadcast(message, room_id)

    def get_room_connections(self, room_id: str) -> list[str]:
        """Get all connection IDs in a room.

        Args:
            room_id: Room identifier

        Returns:
            List of connection IDs
        """
        return list(self.active_connections.get(room_id, {}).keys())

    def get_user_rooms(self, user_id: uuid.UUID) -> set[str]:
        """Get all rooms a user is connected to.

        Args:
            user_id: User ID

        Returns:
            Set of room IDs
        """
        rooms = set()
        connection_ids = self.user_connections.get(user_id, set())

        for room_id, connections in self.active_connections.items():
            for conn_id in connection_ids:
                if conn_id in connection_ids:
                    rooms.add(room_id)

        return rooms

    def get_connection_count(self, room_id: str) -> int:
        """Get the number of active connections in a room.

        Args:
            room_id: Room identifier

        Returns:
            Number of connections
        """
        return len(self.active_connections.get(room_id, {}))

    def is_user_connected(self, user_id: uuid.UUID) -> bool:
        """Check if a user has any active connections.

        Args:
            user_id: User ID

        Returns:
            True if user is connected
        """
        return bool(self.user_connections.get(user_id))

    async def close_all_connections(self, room_id: str) -> None:
        """Close all connections in a room.

        Args:
            room_id: Room identifier
        """
        if room_id in self.active_connections:
            for conn_id, websocket in list(self.active_connections[room_id].items()):
                try:
                    await websocket.close()
                except Exception:
                    pass

            del self.active_connections[room_id]

    def register_handler(self, event_type: str, handler: Callable) -> None:
        """Register an event handler.

        Args:
            event_type: Event type to handle
            handler: Handler function
        """
        self.connection_handlers[event_type].append(handler)

    async def handle_message(
        self,
        connection_id: str,
        room_id: str,
        message: dict[str, Any],
    ) -> None:
        """Handle an incoming message.

        Args:
            connection_id: Connection ID
            room_id: Room identifier
            message: Message payload
        """
        event_type = message.get("type", "unknown")
        handlers = self.connection_handlers.get(event_type, [])

        for handler in handlers:
            try:
                await handler(connection_id, room_id, message)
            except Exception as e:
                logger.error(f"Error in handler for {event_type}: {e}")


class VoiceConnectionManager(ConnectionManager):
    """Specialized connection manager for voice interactions."""

    def __init__(self) -> None:
        """Initialize voice connection manager."""
        super().__init__()
        self.active_sessions: dict[str, dict[str, Any]] = {}

    async def start_session(
        self,
        connection_id: str,
        room_id: str,
        user_id: uuid.UUID,
        language: str = "en",
    ) -> str:
        """Start a voice session.

        Args:
            connection_id: Connection ID
            room_id: Room identifier
            user_id: User ID
            language: Language code

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())

        self.active_sessions[session_id] = {
            "connection_id": connection_id,
            "room_id": room_id,
            "user_id": str(user_id),
            "language": language,
            "started_at": _get_timestamp(),
            "is_active": True,
            "transcripts": [],
        }

        await self._emit(
            "session_started",
            {
                "session_id": session_id,
                "language": language,
            },
            room_id,
            connection_id,
        )

        logger.info(f"Voice session started: {session_id} for user {user_id}")

        return session_id

    async def end_session(self, session_id: str) -> None:
        """End a voice session.

        Args:
            session_id: Session ID
        """
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["is_active"] = False
            self.active_sessions[session_id]["ended_at"] = _get_timestamp()

            room_id = self.active_sessions[session_id]["room_id"]
            connection_id = self.active_sessions[session_id]["connection_id"]

            await self._emit(
                "session_ended",
                {"session_id": session_id},
                room_id,
                connection_id,
            )

            logger.info(f"Voice session ended: {session_id}")

    async def add_transcript(
        self,
        session_id: str,
        text: str,
        is_final: bool = False,
    ) -> None:
        """Add a transcript to a session.

        Args:
            session_id: Session ID
            text: Transcript text
            is_final: Whether this is the final transcript
        """
        if session_id in self.active_sessions:
            transcript = {
                "text": text,
                "is_final": is_final,
                "timestamp": _get_timestamp(),
            }
            self.active_sessions[session_id]["transcripts"].append(transcript)

            room_id = self.active_sessions[session_id]["room_id"]
            connection_id = self.active_sessions[session_id]["connection_id"]

            await self._emit(
                "transcript",
                {
                    "session_id": session_id,
                    "text": text,
                    "is_final": is_final,
                },
                room_id,
                connection_id,
            )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session details.

        Args:
            session_id: Session ID

        Returns:
            Session data or None
        """
        return self.active_sessions.get(session_id)


class TourConnectionManager(ConnectionManager):
    """Specialized connection manager for guided tours."""

    def __init__(self) -> None:
        """Initialize tour connection manager."""
        super().__init__()
        self.active_tours: dict[str, dict[str, Any]] = {}

    async def join_tour(
        self,
        connection_id: str,
        room_id: str,
        user_id: uuid.UUID,
        tour_id: str,
    ) -> None:
        """Join a guided tour.

        Args:
            connection_id: Connection ID
            room_id: Room identifier
            user_id: User ID
            tour_id: Tour ID
        """
        tour_room = f"tour:{tour_id}"

        if tour_id not in self.active_tours:
            self.active_tours[tour_id] = {
                "tour_id": tour_id,
                "participants": [],
                "started_at": _get_timestamp(),
            }

        self.active_tours[tour_id]["participants"].append(str(user_id))

        await self._emit(
            "tour_joined",
            {
                "tour_id": tour_id,
                "user_id": str(user_id),
            },
            tour_room,
            connection_id,
        )

        logger.info(f"User {user_id} joined tour {tour_id}")

    async def leave_tour(
        self,
        connection_id: str,
        user_id: uuid.UUID,
        tour_id: str,
    ) -> None:
        """Leave a guided tour.

        Args:
            connection_id: Connection ID
            user_id: User ID
            tour_id: Tour ID
        """
        tour_room = f"tour:{tour_id}"

        if tour_id in self.active_tours:
            user_str = str(user_id)
            if user_str in self.active_tours[tour_id]["participants"]:
                self.active_tours[tour_id]["participants"].remove(user_str)

        await self._emit(
            "tour_left",
            {
                "tour_id": tour_id,
                "user_id": user_str,
            },
            tour_room,
            connection_id,
        )

        logger.info(f"User {user_id} left tour {tour_id}")

    async def broadcast_location_update(
        self,
        tour_id: str,
        user_id: uuid.UUID,
        location: dict[str, float],
    ) -> None:
        """Broadcast location update to tour participants.

        Args:
            tour_id: Tour ID
            user_id: User ID
            location: Location coordinates
        """
        tour_room = f"tour:{tour_id}"

        await self.broadcast(
            {
                "type": "location_update",
                "data": {
                    "user_id": str(user_id),
                    "location": location,
                    "timestamp": _get_timestamp(),
                },
            },
            tour_room,
        )

    async def broadcast_tour_event(
        self,
        tour_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Broadcast a tour event to all participants.

        Args:
            tour_id: Tour ID
            event_type: Type of event
            data: Event data
        """
        tour_room = f"tour:{tour_id}"

        await self.broadcast(
            {
                "type": event_type,
                "data": data,
                "timestamp": _get_timestamp(),
            },
            tour_room,
        )


# Global instances
manager = ConnectionManager()
voice_manager = VoiceConnectionManager()
tour_manager = TourConnectionManager()
