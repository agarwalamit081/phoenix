"""Itinerary repository for database operations."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config.logging import logger
from src.database.repositories import BaseRepository
from src.models.itinerary import (
    Itinerary,
    ItineraryItem,
    ItineraryNote,
)


class ItineraryRepository(BaseRepository[Itinerary]):
    """Repository for Itinerary model operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the itinerary repository.

        Args:
            session: The database session
        """
        super().__init__(session, Itinerary)

    async def get_user_itineraries(
        self,
        user_id: uuid.UUID,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Itinerary]:
        """Get itineraries for a user.

        Args:
            user_id: The user ID
            status: Optional status filter
            offset: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of itineraries
        """
        stmt = (
            select(Itinerary)
            .where(Itinerary.user_id == user_id)
            .options(selectinload(Itinerary.items))
        )

        if status:
            stmt = stmt.where(Itinerary.status == status)

        stmt = stmt.order_by(Itinerary.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_itineraries(self, user_id: uuid.UUID) -> list[Itinerary]:
        """Get active itineraries for a user.

        Args:
            user_id: The user ID

        Returns:
            List of active itineraries
        """
        return await self.get_user_itineraries(user_id, status="active")

    async def get_upcoming_itineraries(self, user_id: uuid.UUID) -> list[Itinerary]:
        """Get upcoming itineraries for a user.

        Args:
            user_id: The user ID

        Returns:
            List of upcoming itineraries
        """
        stmt = (
            select(Itinerary)
            .where(
                Itinerary.user_id == user_id,
                Itinerary.status == "confirmed",
                Itinerary.start_time > datetime.now(),
            )
            .options(selectinload(Itinerary.items))
            .order_by(Itinerary.start_time.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_with_items(self, itinerary_id: uuid.UUID) -> Itinerary | None:
        """Get an itinerary with all items loaded.

        Args:
            itinerary_id: The itinerary ID

        Returns:
            The itinerary with items, or None if not found
        """
        stmt = (
            select(Itinerary)
            .where(Itinerary.id == itinerary_id)
            .options(selectinload(Itinerary.items))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_status(
        self,
        itinerary_id: uuid.UUID,
        status: str,
    ) -> Itinerary | None:
        """Update the status of an itinerary.

        Args:
            itinerary_id: The itinerary ID
            status: New status

        Returns:
            The updated itinerary, or None if not found
        """
        stmt = (
            update(Itinerary)
            .where(Itinerary.id == itinerary_id)
            .values(status=status)
            .returning(Itinerary)
        )
        result = await self.session.execute(stmt)
        itinerary = result.scalars().first()
        if itinerary:
            logger.info(f"Updated itinerary {itinerary_id} status to {status}")
        return itinerary

    async def delete_user_itinerary(
        self,
        user_id: uuid.UUID,
        itinerary_id: uuid.UUID,
    ) -> bool:
        """Delete an itinerary if it belongs to the user.

        Args:
            user_id: The user ID
            itinerary_id: The itinerary ID

        Returns:
            True if deleted, False otherwise
        """
        stmt = delete(Itinerary).where(
            Itinerary.id == itinerary_id,
            Itinerary.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Deleted itinerary {itinerary_id} for user {user_id}")
        return deleted


class ItineraryItemRepository(BaseRepository[ItineraryItem]):
    """Repository for ItineraryItem model operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the itinerary item repository.

        Args:
            session: The database session
        """
        super().__init__(session, ItineraryItem)

    async def get_itinerary_items(
        self,
        itinerary_id: uuid.UUID,
    ) -> list[ItineraryItem]:
        """Get all items for an itinerary.

        Args:
            itinerary_id: The itinerary ID

        Returns:
            List of itinerary items in sequence order
        """
        stmt = select(ItineraryItem).where(
            ItineraryItem.itinerary_id == itinerary_id,
        ).order_by(ItineraryItem.sequence_order.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_item_by_sequence(
        self,
        itinerary_id: uuid.UUID,
        sequence_order: int,
    ) -> ItineraryItem | None:
        """Get an item by its sequence order.

        Args:
            itinerary_id: The itinerary ID
            sequence_order: The sequence order

        Returns:
            The itinerary item, or None if not found
        """
        stmt = select(ItineraryItem).where(
            ItineraryItem.itinerary_id == itinerary_id,
            ItineraryItem.sequence_order == sequence_order,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_items(
        self,
        itinerary_id: uuid.UUID,
        items: list[dict[str, Any]],
    ) -> list[ItineraryItem]:
        """Create multiple items for an itinerary.

        Args:
            itinerary_id: The itinerary ID
            items: List of item dictionaries

        Returns:
            List of created items
        """
        for item in items:
            item["itinerary_id"] = itinerary_id
        return await self.bulk_create(items)

    async def update_item_status(
        self,
        item_id: uuid.UUID,
        status: str,
        actual_arrival: datetime | None = None,
        actual_departure: datetime | None = None,
    ) -> ItineraryItem | None:
        """Update the status and actual times of an itinerary item.

        Args:
            item_id: The item ID
            status: New status
            actual_arrival: Actual arrival time
            actual_departure: Actual departure time

        Returns:
            The updated item, or None if not found
        """
        values: dict[str, Any] = {"status": status}
        if actual_arrival is not None:
            values["actual_arrival_time"] = actual_arrival
        if actual_departure is not None:
            values["actual_departure_time"] = actual_departure

        stmt = (
            update(ItineraryItem)
            .where(ItineraryItem.id == item_id)
            .values(**values)
            .returning(ItineraryItem)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def delete_itinerary_items(
        self,
        itinerary_id: uuid.UUID,
    ) -> int:
        """Delete all items for an itinerary.

        Args:
            itinerary_id: The itinerary ID

        Returns:
            Number of items deleted
        """
        stmt = delete(ItineraryItem).where(
            ItineraryItem.itinerary_id == itinerary_id,
        )
        result = await self.session.execute(stmt)
        count = result.rowcount
        logger.info(f"Deleted {count} items for itinerary {itinerary_id}")
        return count

    async def reorder_items(
        self,
        itinerary_id: uuid.UUID,
        item_orders: list[tuple[uuid.UUID, int]],
    ) -> bool:
        """Reorder items in an itinerary.

        Args:
            itinerary_id: The itinerary ID
            item_orders: List of (item_id, new_sequence_order) tuples

        Returns:
            True if successful, False otherwise
        """
        for item_id, sequence_order in item_orders:
            stmt = (
                update(ItineraryItem)
                .where(
                    ItineraryItem.id == item_id,
                    ItineraryItem.itinerary_id == itinerary_id,
                )
                .values(sequence_order=sequence_order)
            )
            await self.session.execute(stmt)
        logger.info(f"Reordered {len(item_orders)} items for itinerary {itinerary_id}")
        return True


class ItineraryNoteRepository(BaseRepository[ItineraryNote]):
    """Repository for ItineraryNote model operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the itinerary note repository.

        Args:
            session: The database session
        """
        super().__init__(session, ItineraryNote)

    async def get_itinerary_notes(
        self,
        itinerary_id: uuid.UUID,
    ) -> list[ItineraryNote]:
        """Get all notes for an itinerary.

        Args:
            itinerary_id: The itinerary ID

        Returns:
            List of itinerary notes
        """
        stmt = select(ItineraryNote).where(
            ItineraryNote.itinerary_id == itinerary_id,
        ).order_by(ItineraryNote.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_user_notes(
        self,
        user_id: uuid.UUID,
        note_type: str | None = None,
        limit: int = 50,
    ) -> list[ItineraryNote]:
        """Get notes created by a user.

        Args:
            user_id: The user ID
            note_type: Optional note type filter
            limit: Maximum number of results

        Returns:
            List of notes
        """
        stmt = select(ItineraryNote).where(ItineraryNote.user_id == user_id)

        if note_type:
            stmt = stmt.where(ItineraryNote.note_type == note_type)

        stmt = stmt.order_by(ItineraryNote.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_itinerary_notes(
        self,
        itinerary_id: uuid.UUID,
    ) -> int:
        """Delete all notes for an itinerary.

        Args:
            itinerary_id: The itinerary ID

        Returns:
            Number of notes deleted
        """
        stmt = delete(ItineraryNote).where(
            ItineraryNote.itinerary_id == itinerary_id,
        )
        result = await self.session.execute(stmt)
        count = result.rowcount
        logger.info(f"Deleted {count} notes for itinerary {itinerary_id}")
        return count
