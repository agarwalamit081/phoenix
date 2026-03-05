"""Point of Interest (POI) model for travel destinations."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DECIMAL, ForeignKey, String, Text, func, JSON
from sqlalchemy.dialects.postgresql import ARRAY, UUID, JSONB
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import BaseModel


class PointOfInterest(BaseModel):
    """Point of Interest model representing travel destinations."""

    __tablename__ = "points_of_interest"

    # External ID for linking to external services
    external_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )  # Google Maps Place ID, etc.

    # Basic information
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Categorization
    categories: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )  # ['museum', 'art', 'indoors', etc.]

    # Location
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    latitude: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 8),
        nullable=False,
    )
    longitude: Mapped[Decimal] = mapped_column(
        DECIMAL(11, 8),
        nullable=False,
    )

    # Semantic embedding for similarity search
    embedding: Mapped[bytes | None] = mapped_column(
        Vector(1536),
        nullable=True,
    )

    # Ratings and popularity
    rating: Mapped[Decimal | None] = mapped_column(
        DECIMAL(3, 2),
        nullable=True,
    )  # 0.00 to 5.00
    price_level: Mapped[int | None] = mapped_column(
        nullable=True,
    )  # 0 (free) to 4 (very expensive)
    review_count: Mapped[int | None] = mapped_column(
        nullable=True,
    )
    popularity_score: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    # Operating information
    opening_hours: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )  # JSONB stored as dict

    # Contact information
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Media
    images: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )  # JSONB array of image objects

    # Social signals (from Reddit, Twitter, etc.)
    social_signals: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )  # JSONB with trending status, mentions, sentiment

    # Quality flags
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Metadata
    source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )  # 'google', 'foursquare', 'manual', etc.
    last_verified_at: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True,
    )

    def to_summary_dict(self) -> dict:
        """Convert to summary dictionary (for list views).

        Returns:
            dict: Summary dictionary with essential information
        """
        return {
            "id": str(self.id),
            "name": self.name,
            "categories": self.categories,
            "city": self.city,
            "country": self.country,
            "latitude": float(self.latitude) if self.latitude else None,
            "longitude": float(self.longitude) if self.longitude else None,
            "rating": float(self.rating) if self.rating else None,
            "price_level": self.price_level,
            "is_verified": self.is_verified,
        }

    def to_detail_dict(self) -> dict:
        """Convert to detailed dictionary.

        Returns:
            dict: Full dictionary representation
        """
        return {
            "id": str(self.id),
            "external_id": self.external_id,
            "name": self.name,
            "description": self.description,
            "categories": self.categories,
            "address": self.address,
            "city": self.city,
            "country": self.country,
            "latitude": float(self.latitude) if self.latitude else None,
            "longitude": float(self.longitude) if self.longitude else None,
            "rating": float(self.rating) if self.rating else None,
            "price_level": self.price_level,
            "review_count": self.review_count,
            "popularity_score": self.popularity_score,
            "opening_hours": self.opening_hours,
            "phone": self.phone,
            "website": self.website,
            "email": self.email,
            "images": self.images,
            "social_signals": self.social_signals,
            "is_verified": self.is_verified,
            "is_active": self.is_active,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def is_trending(self) -> bool:
        """Check if POI is currently trending based on social signals.

        Returns:
            bool: True if POI is trending
        """
        return self.social_signals.get("is_trending", False)

    def get_trending_score(self) -> float:
        """Get the trending score from social signals.

        Returns:
            float: Trending score (0.0 to 1.0)
        """
        return self.social_signals.get("trending_score", 0.0)


class POISearchIndex(BaseModel):
    """Search index for POIs (managed by pgvector full-text search)."""

    __tablename__ = "poi_search_index"

    poi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("points_of_interest.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    search_vector: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )  # Concatenated text for full-text search
    category_vector: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )  # Category-specific search text
