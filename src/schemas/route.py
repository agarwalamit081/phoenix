"""Pydantic schemas for route planning operations."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class Location(BaseModel):
    """Location schema."""

    latitude: Decimal = Field(..., ge=-90, le=90, description="Latitude")
    longitude: Decimal = Field(..., ge=-180, le=180, description="Longitude")
    address: str | None = Field(None, description="Address string")
    city: str | None = Field(None, description="City name")
    country: str | None = Field(None, description="Country name")


class POIBrief(BaseModel):
    """Brief POI information for routes."""

    id: uuid.UUID = Field(..., description="POI ID")
    name: str = Field(..., description="POI name")
    categories: list[str] = Field(..., description="POI categories")
    latitude: Decimal = Field(..., description="POI latitude")
    longitude: Decimal = Field(..., description="POI longitude")
    rating: float | None = Field(None, description="POI rating")
    price_level: int | None = Field(None, description="POI price level")
    estimated_duration_minutes: int | None = Field(None, description="Suggested visit duration")


class RouteGenerateRequest(BaseModel):
    """Request schema for route generation."""

    start_location: Location = Field(..., description="Starting location")
    end_location: Location | None = Field(None, description="Ending location (optional for round trips)")
    start_time: datetime | None = Field(None, description="Route start time")
    end_time: datetime | None = Field(None, description="Route end time")
    max_duration_minutes: int | None = Field(None, ge=30, le=480, description="Maximum route duration")
    max_distance_km: float | None = Field(None, ge=1, le=200, description="Maximum route distance")
    preferred_categories: list[str] | None = Field(None, description="Preferred POI categories")
    excluded_categories: list[str] | None = Field(None, description="Excluded POI categories")
    transport_mode: str = Field("walking", pattern="^(walking|driving|transit|cycling)$", description="Transport mode")
    include_pois: list[uuid.UUID] | None = Field(None, description="Specific POIs to include")
    exclude_pois: list[uuid.UUID] | None = Field(None, description="Specific POIs to exclude")
    optimize_for: str = Field(
        "satisfaction",
        pattern="^(time|distance|satisfaction|variety)$",
        description="Optimization criteria"
    )


class RouteStop(BaseModel):
    """Single stop in a route."""

    sequence_order: int = Field(..., ge=1, description="Stop sequence number")
    poi: POIBrief = Field(..., description="POI information")
    estimated_arrival_time: datetime | None = Field(None, description="Estimated arrival")
    estimated_departure_time: datetime | None = Field(None, description="Estimated departure")
    estimated_duration_minutes: int | None = Field(None, description="Visit duration")
    distance_from_previous_km: float | None = Field(None, description="Distance from previous stop")
    travel_time_minutes: int | None = Field(None, description="Travel time from previous stop")
    transport_mode: str | None = Field(None, description="Transport mode to this stop")


class RouteResponse(BaseModel):
    """Response schema for generated route."""

    id: uuid.UUID = Field(..., description="Route ID")
    title: str | None = Field(None, description="Route title")
    description: str | None = Field(None, description="Route description")
    status: str = Field(..., description="Route status")
    stops: list[RouteStop] = Field(..., description="Route stops")
    total_distance_km: float | None = Field(None, description="Total route distance")
    total_duration_minutes: int | None = Field(None, description="Total route duration")
    estimated_start_time: datetime | None = Field(None, description="Estimated start time")
    estimated_end_time: datetime | None = Field(None, description="Estimated end time")
    satisfaction_score: float | None = Field(None, ge=0, le=1, description="Predicted satisfaction score")
    optimization_version: int | None = Field(None, description="Optimization algorithm version")
    created_at: datetime = Field(..., description="Creation time")

    model_config = {"from_attributes": True}


class RouteModifyRequest(BaseModel):
    """Request schema for modifying a route."""

    add_pois: list[uuid.UUID] | None = Field(None, description="POIs to add to route")
    remove_pois: list[uuid.UUID] | None = Field(None, description="POIs to remove from route")
    reorder_stops: list[uuid.UUID] | None = Field(None, description="New stop order")
    change_start_time: datetime | None = Field(None, description="New start time")
    change_transport_mode: str | None = Field(None, pattern="^(walking|driving|transit|cycling)$", description="New transport mode")


class RouteOptimizationRequest(BaseModel):
    """Request schema for re-optimizing a route."""

    optimize_for: str = Field(
        ...,
        pattern="^(time|distance|satisfaction|variety)$",
        description="Optimization criteria"
    )
    current_location: Location | None = Field(None, description="Current user location")
    visited_stops: list[uuid.UUID] | None = Field(None, description="Already visited stops")
    skip_stops: list[uuid.UUID] | None = Field(None, description="Stops to skip")


class RouteListResponse(BaseModel):
    """Response schema for listing user routes."""

    routes: list[RouteResponse] = Field(..., description="List of routes")
    total: int = Field(..., description="Total number of routes")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")


class RouteAnalytics(BaseModel):
    """Analytics for a route."""

    total_distance_km: float = Field(..., description="Total distance")
    total_duration_minutes: int = Field(..., description="Total duration")
    average_poi_rating: float | None = Field(None, description="Average POI rating")
    category_breakdown: dict[str, int] = Field(..., description="Count by category")
    estimated_cost: dict[str, float] | None = Field(None, description="Estimated costs by category")
    weather_impact: dict[str, Any] | None = Field(None, description="Weather-related information")
