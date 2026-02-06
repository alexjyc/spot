"""Pydantic schemas for Spot On agent outputs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RestaurantOutput(BaseModel):
    """Restaurant recommendation output schema."""

    id: str = Field(description="Unique identifier")
    name: str = Field(description="Restaurant name")
    cuisine: str = Field(description="Cuisine type (e.g., 'Italian', 'Korean BBQ')")
    area: str | None = Field(default=None, description="Neighborhood or district")
    price_range: str | None = Field(
        default=None, description="Price range (e.g., '$$', '$$$')"
    )
    url: str = Field(description="Source URL for enrichment")
    snippet: str = Field(description="Brief description from search")
    why_recommended: str = Field(
        description="1-2 sentence explanation of why this is recommended"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags like 'michelin-star', 'local-favorite', 'vegetarian-friendly'",
    )


class AttractionOutput(BaseModel):
    """Travel spot/attraction recommendation output schema."""

    id: str = Field(description="Unique identifier")
    name: str = Field(description="Attraction name")
    kind: str = Field(
        description="Type of attraction (e.g., 'museum', 'park', 'landmark', 'temple')"
    )
    area: str | None = Field(default=None, description="Neighborhood or district")
    url: str = Field(description="Source URL for enrichment")
    snippet: str = Field(description="Brief description from search")
    why_recommended: str = Field(
        description="1-2 sentence explanation of why this is recommended"
    )
    estimated_duration_min: int | None = Field(
        default=None, description="Typical visit duration in minutes"
    )
    time_of_day_fit: list[str] = Field(
        default_factory=list,
        description="Best times to visit (e.g., ['morning', 'afternoon'])",
    )


class HotelOutput(BaseModel):
    """Hotel recommendation output schema."""

    id: str = Field(description="Unique identifier")
    name: str = Field(description="Hotel name")
    area: str | None = Field(default=None, description="Neighborhood or district")
    price_per_night: str | None = Field(
        default=None, description="Per-night price (e.g., '$150', '₩180,000')"
    )
    url: str = Field(description="Source URL for enrichment")
    snippet: str = Field(description="Brief description from search")
    why_recommended: str = Field(
        description="1-2 sentence explanation of why this is recommended"
    )
    amenities: list[str] = Field(
        default_factory=list,
        description="Key amenities (e.g., 'wifi', 'pool', 'breakfast-included')",
    )


class CarRentalOutput(BaseModel):
    """Car rental recommendation output schema."""

    id: str = Field(description="Unique identifier")
    provider: str = Field(description="Rental company name (e.g., 'Hertz', 'Budget')")
    vehicle_class: str = Field(
        description="Vehicle type (e.g., 'compact', 'SUV', 'luxury')"
    )
    price_per_day: str | None = Field(
        default=None, description="Per-day rental price (e.g., '$45', '₩60,000')"
    )
    pickup_location: str | None = Field(
        default=None, description="Pickup location (e.g., 'Airport', 'Downtown')"
    )
    operating_hours: str | None = Field(
        default=None, description="Operating hours (e.g., 'Mon-Fri 9am-5pm')"
    )
    url: str = Field(description="Source URL for enrichment")
    why_recommended: str = Field(
        description="1-2 sentence explanation of why this is recommended"
    )


class FlightOutput(BaseModel):
    """Flight recommendation output schema."""

    id: str = Field(description="Unique identifier")
    airline: str | None = Field(default=None, description="Airline name if available")
    route: str = Field(description="Route description (e.g., 'Tokyo NRT -> Seoul ICN')")
    trip_type: Literal["one-way", "round-trip"] = Field(
        description="One-way or round-trip"
    )
    price_range: str | None = Field(
        default=None, description="Price range (e.g., '$200-$350')"
    )
    url: str = Field(description="Source URL for enrichment")
    snippet: str = Field(description="Brief description from search")
    why_recommended: str = Field(
        description="1-2 sentence explanation of why this is recommended"
    )


class EnrichedDetails(BaseModel):
    """Enriched details extracted from webpage content."""

    price_hint: str | None = Field(
        default=None, description="Additional price information if found"
    )
    hours_text: str | None = Field(
        default=None, description="Opening hours text (e.g., 'Mon-Fri 9am-5pm')"
    )
    address: str | None = Field(default=None, description="Full address")
    phone: str | None = Field(default=None, description="Phone number")
    reservation_required: bool | None = Field(
        default=None, description="Whether reservation is required"
    )


class ConstraintsOutput(BaseModel):
    """Parsed travel constraints from user prompt."""

    origin: str = Field(description="Origin city with airport code if available")
    destination: str = Field(
        description="Destination city with airport code if available"
    )
    departing_date: str = Field(description="Departure date in ISO format (YYYY-MM-DD)")
    returning_date: str | None = Field(
        default=None, description="Return date in ISO format, or None for one-way"
    )
    interests: list[str] = Field(
        default_factory=list,
        description="User interests (e.g., ['food', 'history', 'nature'])",
    )
    budget: str = Field(
        default="moderate", description="Budget level: 'budget', 'moderate', 'luxury'"
    )


# =========================================================================
# LLM Structured Output Wrapper Schemas
# =========================================================================
# These wrapper schemas are used with LangChain's structured output API
# to ensure the LLM returns properly formatted lists of domain objects.


class RestaurantList(BaseModel):
    """Wrapper for LLM structured output - list of restaurants."""

    restaurants: list[RestaurantOutput]


class AttractionList(BaseModel):
    """Wrapper for LLM structured output - list of attractions."""

    attractions: list[AttractionOutput]


class HotelList(BaseModel):
    """Wrapper for LLM structured output - list of hotels."""

    hotels: list[HotelOutput]


class CarRentalList(BaseModel):
    """Wrapper for LLM structured output - list of car rentals."""

    cars: list[CarRentalOutput]


class FlightList(BaseModel):
    """Wrapper for LLM structured output - list of flights."""

    flights: list[FlightOutput]
