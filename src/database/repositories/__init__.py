"""Repository base class and common repository patterns."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel as PydanticBaseModel
from sqlalchemy import Select, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from src.config.logging import logger

T = TypeVar("T", bound=DeclarativeBase)


class BaseRepository(Generic[T]):
    """Base repository with common CRUD operations."""

    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        """Initialize the repository.

        Args:
            session: The database session
            model: The SQLAlchemy model class
        """
        self.session = session
        self.model = model

    async def get_by_id(self, id: str) -> T | None:
        """Get a record by ID.

        Args:
            id: The record ID

        Returns:
            The record if found, None otherwise
        """
        stmt = select(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all(
        self,
        offset: int = 0,
        limit: int = 100,
    ) -> list[T]:
        """Get all records with pagination.

        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of records
        """
        stmt = select(self.model).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, data: dict[str, Any]) -> T:
        """Create a new record.

        Args:
            data: Dictionary with field values

        Returns:
            The created record
        """
        record = self.model(**data)
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        logger.info(f"Created {self.model.__name__} with id={record.id}")
        return record

    async def update(self, id: str, data: dict[str, Any]) -> T | None:
        """Update a record by ID.

        Args:
            id: The record ID
            data: Dictionary with field values to update

        Returns:
            The updated record if found, None otherwise
        """
        stmt = (
            update(self.model)
            .where(self.model.id == id)
            .values(**data)
            .returning(self.model)
        )
        result = await self.session.execute(stmt)
        record = result.scalars().first()
        if record:
            logger.info(f"Updated {self.model.__name__} with id={id}")
        return record

    async def delete(self, id: str) -> bool:
        """Delete a record by ID.

        Args:
            id: The record ID

        Returns:
            True if deleted, False if not found
        """
        stmt = delete(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Deleted {self.model.__name__} with id={id}")
        return deleted

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """Count records matching optional filters.

        Args:
            filters: Optional dictionary of field filters

        Returns:
            Number of matching records
        """
        from sqlalchemy import func

        stmt = select(func.count(self.model.id))
        if filters:
            for key, value in filters.items():
                stmt = stmt.where(getattr(self.model, key) == value)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def exists(self, id: str) -> bool:
        """Check if a record exists by ID.

        Args:
            id: The record ID

        Returns:
            True if record exists, False otherwise
        """
        stmt = select(self.model.id).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalar() is not None

    async def bulk_create(self, items: list[dict[str, Any]]) -> list[T]:
        """Create multiple records in bulk.

        Args:
            items: List of dictionaries with field values

        Returns:
            List of created records
        """
        records = [self.model(**item) for item in items]
        self.session.add_all(records)
        await self.session.flush()
        for record in records:
            await self.session.refresh(record)
        logger.info(f"Bulk created {len(records)} {self.model.__name__} records")
        return records

    def build_select(
        self,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        order_desc: bool = False,
    ) -> Select[tuple[T]]:
        """Build a select statement with optional filters and ordering.

        Args:
            filters: Optional dictionary of field filters
            order_by: Optional field name to order by
            order_desc: Whether to order in descending order

        Returns:
            Select statement
        """
        stmt = select(self.model)

        if filters:
            for key, value in filters.items():
                if value is not None:
                    stmt = stmt.where(getattr(self.model, key) == value)

        if order_by:
            column = getattr(self.model, order_by, None)
            if column:
                if order_desc:
                    stmt = stmt.order_by(column.desc())
                else:
                    stmt = stmt.order_by(column.asc())

        return stmt
