"""Base SQLAlchemy model with common fields and methods."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    @declared_attr.directive
    def __tablename__(cls) -> str:
        """Generate table name from class name.

        Returns:
            str: Table name in snake_case
        """
        name = cls.__name__
        # Convert CamelCase to snake_case
        result = [name[0].lower()]
        for char in name[1:]:
            if char.isupper():
                result.extend(["_", char.lower()])
            else:
                result.append(char)
        return "".join(result) + "s"  # Pluralize

    def to_dict(self) -> dict[str, Any]:
        """Convert model instance to dictionary.

        Returns:
            dict: Dictionary representation of the model
        """
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, uuid.UUID):
                value = str(value)
            result[column.name] = value
        return result

    def update_from_dict(self, data: dict[str, Any]) -> None:
        """Update model instance from dictionary.

        Args:
            data: Dictionary with fields to update
        """
        for key, value in data.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)

    def __repr__(self) -> str:
        """String representation of the model.

        Returns:
            str: String representation
        """
        class_name = self.__class__.__name__
        attrs = []
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, str) and len(value) > 20:
                value = value[:17] + "..."
            attrs.append(f"{column.name}={value!r}")
        return f"{class_name}({', '.join(attrs)})"


class TimestampMixin:
    """Mixin for adding timestamp fields to models."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""

    is_deleted: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, nullable=True
    )

    def soft_delete(self) -> None:
        """Mark the record as deleted."""
        self.is_deleted = True
        self.deleted_at = datetime.now()

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None


class BaseModel(Base, TimestampMixin):
    """Base model with ID and timestamps."""

    __abstract__ = True  # Prevent table creation for this base class

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    def __str__(self) -> str:
        """String representation of the model.

        Returns:
            str: String representation with ID
        """
        return f"{self.__class__.__name__}(id={self.id})"
