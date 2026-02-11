"""Pydantic schemas for Spot On agent outputs."""

from __future__ import annotations

from datetime import date
import re
from typing import Literal

from pydantic import BaseModel, Field
from pydantic import field_validator, model_validator


class RestaurantOutput(BaseModel):
    """Restaurant recommendation output schema."""

    id: str = Field(description="Unique identifier")
    name: str = Field(description="Restaurant name")
    cuisine: str | None = Field(
        default=None,
        description="Cuisine type (e.g., 'Italian', 'Korean BBQ'). Null if not stated in sources.",
    )
    area: str | None = Field(default=None, description="Neighborhood or district")
    operating_hours: str | None = Field(
        default=None, description="Operating hours (e.g., 'Mon-Fri 9am-5pm')"
    )
    price_range: str | None = Field(
        default=None, description="Price range (e.g., '$$', '$$$')"
    )
    url: str = Field(description="Source URL for enrichment")
    menu_url: str | None = Field(
        default=None,
        description="Menu link URL if explicitly present on the page.",
    )
    reservation_url: str | None = Field(
        default=None,
        description="Reservation/booking link URL if explicitly present on the page.",
    )
    snippet: str = Field(description="Brief description from search")
    why_recommended: str = Field(
        description="1-2 sentence explanation of why this is recommended"
    )
    rating: float | None = Field(
        default=None,
        description="Rating score (e.g., 4.5 out of 5) from a review source. Null if not stated.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags like 'michelin-star', 'local-favorite', 'vegetarian-friendly'",
    )


class AttractionOutput(BaseModel):
    """Travel spot/attraction recommendation output schema."""

    id: str = Field(description="Unique identifier")
    name: str = Field(description="Attraction name")
    kind: str | None = Field(
        default=None,
        description=(
            "Type of attraction (e.g., 'museum', 'park', 'landmark', 'temple'). "
            "Null if not stated in sources."
        ),
    )
    area: str | None = Field(default=None, description="Neighborhood or district")
    operating_hours: str | None = Field(
        default=None, description="Operating hours (e.g., 'Mon-Fri 9am-5pm')"
    )
    url: str = Field(description="Source URL for enrichment")
    reservation_url: str | None = Field(
        default=None,
        description="Reservation/booking link URL if explicitly present on the page.",
    )
    admission_price: str | None = Field(
        default=None, description="Admission price (exchange to US Dollar)"
    )
    snippet: str = Field(description="Brief description from search")
    why_recommended: str = Field(
        description="1-2 sentence explanation of why this is recommended"
    )
    estimated_duration_min: int | None = Field(
        default=None, description="Typical visit duration in minutes"
    )


class HotelOutput(BaseModel):
    """Hotel recommendation output schema."""

    id: str = Field(description="Unique identifier")
    name: str = Field(description="Hotel name")
    area: str | None = Field(default=None, description="Neighborhood or district")
    price_per_night: str | None = Field(
        default=None, description="Per-night price (exchange to US Dollar)"
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
    vehicle_class: str | None = Field(
        default=None,
        description="Vehicle type (e.g., 'compact', 'SUV', 'luxury'). Null if not stated in sources.",
    )
    price_per_day: str | None = Field(
        default=None, description="Per-day rental price (exchange to US Dollar)"
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
        default=None, description="Price range (exchange to US Dollar)"
    )
    url: str = Field(description="Source URL for enrichment")
    snippet: str = Field(description="Brief description from search")
    why_recommended: str = Field(
        description="1-2 sentence explanation of why this is recommended"
    )


def _parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except Exception as e:
        raise ValueError("Expected ISO date YYYY-MM-DD") from e


def _strip_airport_code(value: str) -> str:
    # "Paris (CDG)" -> "Paris"
    return (value or "").split("(", 1)[0].strip()


def _extract_airport_code(value: str) -> str | None:
    # "Paris (CDG)" -> "CDG"
    if not value:
        return None
    if "(" not in value or ")" not in value:
        return None
    code = value.split("(", 1)[1].split(")", 1)[0].strip().upper()
    if len(code) == 3 and code.isalpha():
        return code
    return None


class TravelConstraints(BaseModel):
    """Structured constraints (source-of-truth) provided by the UI/API."""

    origin: str = Field(description="Origin city with airport code if available")
    destination: str = Field(
        description="Destination city with airport code if available"
    )
    departing_date: str = Field(description="Departure date in ISO format (YYYY-MM-DD)")
    returning_date: str | None = Field(
        default=None, description="Return date in ISO format, or None for one-way"
    )

    model_config = {"extra": "ignore"}

    @field_validator("origin", "destination")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        v = (value or "").strip()
        if not v:
            raise ValueError("Must be non-empty")
        return v

    @field_validator("departing_date")
    @classmethod
    def _valid_departing_date(cls, value: str) -> str:
        _parse_iso_date(value)
        return value

    @field_validator("returning_date")
    @classmethod
    def _valid_returning_date(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return None
        _parse_iso_date(value)
        return value

    @model_validator(mode="after")
    def _validate_dates(self) -> "TravelConstraints":
        d0 = _parse_iso_date(self.departing_date)
        if self.returning_date:
            d1 = _parse_iso_date(self.returning_date)
            if d1 < d0:
                raise ValueError("returning_date must be on/after departing_date")
        if self.origin.strip().lower() == self.destination.strip().lower():
            raise ValueError("origin and destination must be different")
        return self


class QueryContext(BaseModel):
    """Derived, deterministic context for search queries."""

    origin: str
    destination: str
    origin_city: str
    destination_city: str
    origin_code: str | None = None
    destination_code: str | None = None
    departing_date: str
    returning_date: str | None = None
    trip_type: Literal["one-way", "round-trip"]
    depart_year: int
    stay_nights: int | None = None
    

    @classmethod
    def from_constraints_with_normalization(
        cls, constraints: TravelConstraints, norm: "LocationNormalization | None"
    ) -> "QueryContext":
        depart = _parse_iso_date(constraints.departing_date)
        ret = _parse_iso_date(constraints.returning_date) if constraints.returning_date else None
        stay_nights = (ret - depart).days if ret else None

        origin_from_constraints = constraints.origin
        dest_from_constraints = constraints.destination

        origin_city = _strip_airport_code(origin_from_constraints)
        dest_city = _strip_airport_code(dest_from_constraints)

        origin_code = _extract_airport_code(origin_from_constraints)
        dest_code = _extract_airport_code(dest_from_constraints)

        def _clean_city(value: str | None) -> str | None:
            if not value or not isinstance(value, str):
                return None
            v = " ".join(value.strip().split())
            if not v:
                return None
            return v.split("(", 1)[0].strip()

        def _clean_iata(value: str | None) -> str | None:
            if not value or not isinstance(value, str):
                return None
            v = value.strip().upper()
            return v if re.fullmatch(r"[A-Z]{3}", v) else None

        if norm and getattr(norm, "confidence", "medium") != "low":
            origin_city = _clean_city(getattr(norm, "origin_city", None)) or origin_city
            dest_city = _clean_city(getattr(norm, "destination_city", None)) or dest_city
            origin_code = origin_code or _clean_iata(getattr(norm, "origin_code", None))
            dest_code = dest_code or _clean_iata(getattr(norm, "destination_code", None))

        return cls(
            origin=origin_from_constraints,
            destination=dest_from_constraints,
            origin_city=origin_city,
            destination_city=dest_city,
            origin_code=origin_code,
            destination_code=dest_code,
            departing_date=constraints.departing_date,
            returning_date=constraints.returning_date,
            trip_type="round-trip" if constraints.returning_date else "one-way",
            depart_year=depart.year,
            stay_nights=stay_nights,
        )


class LocationNormalization(BaseModel):
    """LLM output for normalizing user-typed origin/destination."""

    origin_city: str | None = Field(
        default=None,
        description="Normalized origin city, e.g. 'San Francisco, CA' (no airport code suffix)",
    )
    destination_city: str | None = Field(
        default=None,
        description="Normalized destination city, e.g. 'Seoul' (no airport code suffix)",
    )
    origin_code: str | None = Field(
        default=None, description="Origin IATA airport code, e.g. 'SFO' (null if ambiguous)"
    )
    destination_code: str | None = Field(
        default=None,
        description="Destination IATA airport code, e.g. 'ICN' (null if ambiguous)",
    )
    confidence: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Overall confidence in the normalization",
    )

    model_config = {"extra": "ignore"}


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


# =========================================================================
# Enrichment Schemas (used by GapFiller for targeted LLM extraction)
# =========================================================================


class RestaurantEnrichment(BaseModel):
    """Fields the GapFiller can extract for a restaurant."""

    operating_hours: str | None = None
    menu_url: str | None = None
    reservation_url: str | None = None
    price_range: str | None = None
    cuisine: str | None = None
    rating: float | None = None


class AttractionEnrichment(BaseModel):
    """Fields the GapFiller can extract for an attraction."""

    operating_hours: str | None = None
    admission_price: str | None = None
    reservation_url: str | None = None
    kind: str | None = None


class HotelEnrichment(BaseModel):
    """Fields the GapFiller can extract for a hotel."""

    price_per_night: str | None = None
    amenities: list[str] = Field(default_factory=list)


class CarRentalEnrichment(BaseModel):
    """Fields the GapFiller can extract for a car rental."""

    price_per_day: str | None = None
    vehicle_class: str | None = None
    operating_hours: str | None = None


class FlightEnrichment(BaseModel):
    """Fields the GapFiller can extract for a flight."""
    price_range: str | None = None


# =========================================================================
# Enrichment Query Schemas (used by EnrichAgent for LLM-generated queries)
# =========================================================================


class EnrichmentQuery(BaseModel):
    """A targeted search query for a specific item's missing fields."""

    item_id: str = Field(description="ID of the item needing enrichment")
    query: str = Field(description="Targeted search query to find missing information")


class EnrichmentQueryList(BaseModel):
    """Wrapper for LLM structured output - list of enrichment queries."""

    queries: list[EnrichmentQuery]


# =========================================================================
# Report / Itinerary Schemas (used by ReportWriter)
# =========================================================================


class ItinerarySlot(BaseModel):
    """A single time slot in a day's itinerary."""

    time_of_day: Literal["morning", "afternoon", "evening"] = Field(
        description="Time of day for this activity"
    )
    activity: str = Field(description="Description of the activity")
    item_name: str = Field(description="Name of the place/service")
    item_type: Literal["restaurant", "attraction", "hotel", "transport"] = Field(
        description="Category of the item"
    )
    estimated_cost: str | None = Field(
        default=None, description="Estimated cost for this activity"
    )


class ItineraryDay(BaseModel):
    """A single day in the travel itinerary."""

    day_number: int = Field(description="Day number (1, 2, 3)")
    date: str = Field(description="Date in ISO format or descriptive label")
    slots: list[ItinerarySlot] = Field(description="Activities for this day")
    daily_total: str = Field(description="Estimated total spend for this day")


class FlightSummaryItem(BaseModel):
    name: str
    price: str
    route: str


class CarRentalSummaryItem(BaseModel):
    name: str
    price_per_day: str
    vehicle_class: str


class HotelSummaryItem(BaseModel):
    name: str
    price_per_night: str
    area: str


class AttractionSummaryItem(BaseModel):
    name: str
    admission_price: str
    kind: str


class RestaurantSummaryItem(BaseModel):
    name: str
    cuisine: str
    price_range: str


class TravelReport(BaseModel):
    """Complete travel report with summary tables and itinerary."""

    flight_summary: list[FlightSummaryItem] = Field(
        default_factory=list, description="Flight options summary"
    )
    car_rental_summary: list[CarRentalSummaryItem] = Field(
        default_factory=list, description="Car rental options summary"
    )
    hotel_summary: list[HotelSummaryItem] = Field(
        default_factory=list, description="Hotel options summary"
    )
    attraction_summary: list[AttractionSummaryItem] = Field(
        default_factory=list, description="Attraction options summary"
    )
    restaurant_summary: list[RestaurantSummaryItem] = Field(
        default_factory=list, description="Restaurant options summary"
    )
    itinerary: list[ItineraryDay] = Field(
        description="3-day itinerary with morning/afternoon/evening slots"
    )
    total_estimated_budget: str = Field(
        description="Total estimated budget for the trip"
    )
