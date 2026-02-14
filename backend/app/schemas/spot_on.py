from datetime import date
import re
from typing import Literal

from pydantic import BaseModel, Field
from pydantic import field_validator, model_validator

_NULL_STRINGS = {"null", "none", "n/a", "na", "unknown", ""}


def _sanitize_nullable_str(v: str | None) -> str | None:
    if v is None or v.strip().lower() in _NULL_STRINGS:
        return None
    return v


class RestaurantOutput(BaseModel):
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

    @field_validator("cuisine", "area", "operating_hours", "price_range", "menu_url", "reservation_url", mode="before")
    @classmethod
    def _sanitize(cls, v: str | None) -> str | None:
        return _sanitize_nullable_str(v)


class AttractionOutput(BaseModel):
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
        default=None, description="Admission price in USD (numeric string)"
    )
    snippet: str = Field(description="Brief description from search")
    why_recommended: str = Field(
        description="1-2 sentence explanation of why this is recommended"
    )
    estimated_duration_min: int | None = Field(
        default=None, description="Typical visit duration in minutes"
    )

    @field_validator("kind", "area", "operating_hours", "reservation_url", "admission_price", mode="before")
    @classmethod
    def _sanitize(cls, v: str | None) -> str | None:
        return _sanitize_nullable_str(v)


class HotelOutput(BaseModel):
    id: str = Field(description="Unique identifier")
    name: str = Field(description="Hotel name")
    area: str | None = Field(default=None, description="Neighborhood or district")
    price_per_night: str | None = Field(
        default=None, description="Per-night price as a numeric string in USD (e.g., '150')"
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

    @field_validator("area", "price_per_night", mode="before")
    @classmethod
    def _sanitize(cls, v: str | None) -> str | None:
        return _sanitize_nullable_str(v)


class CarRentalOutput(BaseModel):
    id: str = Field(description="Unique identifier")
    provider: str = Field(description="Rental company name (e.g., 'Hertz', 'Budget')")
    vehicle_class: str | None = Field(
        default=None,
        description="Vehicle type (e.g., 'compact', 'SUV', 'luxury'). Null if not stated in sources.",
    )
    price_per_day: str | None = Field(
        default=None, description="Per-day rental price as a numeric string in USD (e.g., '45')"
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

    @field_validator("vehicle_class", "price_per_day", "pickup_location", "operating_hours", mode="before")
    @classmethod
    def _sanitize(cls, v: str | None) -> str | None:
        return _sanitize_nullable_str(v)


class FlightOutput(BaseModel):
    id: str = Field(description="Unique identifier")
    airline: str | None = Field(default=None, description="Airline name if available")
    route: str = Field(description="Route description (e.g., 'Tokyo NRT -> Seoul ICN')")
    trip_type: Literal["one-way", "round-trip"] = Field(
        description="One-way or round-trip"
    )
    price_range: str | None = Field(
        default=None,
        description="Flight price or range with currency as numeric string in USD (e.g., '450', '350-600')"
    )
    url: str = Field(description="Source URL for enrichment")
    snippet: str = Field(description="Brief description from search")
    why_recommended: str = Field(
        description="1-2 sentence explanation of why this is recommended"
    )

    @field_validator("airline", "price_range", mode="before")
    @classmethod
    def _sanitize(cls, v: str | None) -> str | None:
        return _sanitize_nullable_str(v)


def _parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except Exception as e:
        raise ValueError("Expected ISO date YYYY-MM-DD") from e


def _strip_airport_code(value: str) -> str:
    return (value or "").split("(", 1)[0].strip()


def _extract_airport_code(value: str) -> str | None:
    if not value:
        return None
    if "(" not in value or ")" not in value:
        return None
    code = value.split("(", 1)[1].split(")", 1)[0].strip().upper()
    if len(code) == 3 and code.isalpha():
        return code
    return None


class TravelConstraints(BaseModel):
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


class RestaurantList(BaseModel):
    restaurants: list[RestaurantOutput]

class AttractionList(BaseModel):
    attractions: list[AttractionOutput]

class HotelList(BaseModel):
    hotels: list[HotelOutput]

class CarRentalList(BaseModel):
    cars: list[CarRentalOutput]

class FlightList(BaseModel):
    flights: list[FlightOutput]


class RestaurantEnrichment(BaseModel):
    operating_hours: str | None = None
    menu_url: str | None = None
    reservation_url: str | None = None
    price_range: str | None = None
    cuisine: str | None = None
    rating: float | None = None

    @field_validator("operating_hours", "menu_url", "reservation_url", "price_range", "cuisine", mode="before")
    @classmethod
    def _sanitize(cls, v: str | None) -> str | None:
        return _sanitize_nullable_str(v)

class AttractionEnrichment(BaseModel):
    operating_hours: str | None = None
    admission_price: str | None = None
    reservation_url: str | None = None
    kind: str | None = None

    @field_validator("operating_hours", "admission_price", "reservation_url", "kind", mode="before")
    @classmethod
    def _sanitize(cls, v: str | None) -> str | None:
        return _sanitize_nullable_str(v)

class HotelEnrichment(BaseModel):
    price_per_night: str | None = None
    amenities: list[str] = Field(default_factory=list)

    @field_validator("price_per_night", mode="before")
    @classmethod
    def _sanitize(cls, v: str | None) -> str | None:
        return _sanitize_nullable_str(v)

class CarRentalEnrichment(BaseModel):
    price_per_day: str | None = None
    vehicle_class: str | None = None
    operating_hours: str | None = None

    @field_validator("price_per_day", "vehicle_class", "operating_hours", mode="before")
    @classmethod
    def _sanitize(cls, v: str | None) -> str | None:
        return _sanitize_nullable_str(v)

class FlightEnrichment(BaseModel):
    price_range: str | None = None

    @field_validator("price_range", mode="before")
    @classmethod
    def _sanitize(cls, v: str | None) -> str | None:
        return _sanitize_nullable_str(v)


class EnrichmentQuery(BaseModel):
    item_id: str = Field(description="ID of the item needing enrichment")
    query: str = Field(description="Targeted search query to find missing information")


class EnrichmentQueryList(BaseModel):
    queries: list[EnrichmentQuery]


class TravelReport(BaseModel):
    total_estimated_budget: str = Field(
        description="Total estimated budget for the trip"
    )


class DestinationRecommendation(BaseModel):
    destination: str = Field(description="Destination city with airport code, e.g. 'Tokyo (NRT)'")
    reasoning: str = Field(description="2-3 sentence explanation of why this destination fits the preferences")

class RecommendationResult(BaseModel):
    destination: DestinationRecommendation
