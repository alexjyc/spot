"""Writer agent — normalizes raw search results into structured picks."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.agents.prompt import (
    build_attractions_prompt,
    build_car_rental_prompt,
    build_flight_prompt,
    build_hotel_prompt,
    build_restaurant_prompt,
)
from app.schemas.spot_on import (
    AttractionList,
    AttractionOutput,
    CarRentalList,
    CarRentalOutput,
    FlightList,
    FlightOutput,
    HotelList,
    HotelOutput,
    RestaurantList,
    RestaurantOutput,
)
from app.utils.dedup import canonicalize_url, normalize_name

logger = logging.getLogger(__name__)


class WriterAgent(BaseAgent):
    """Runs 5 parallel LLM calls to normalize raw search results into top picks.

    Each category uses its own specialized prompt to preserve domain-specific
    guardrails (e.g. cuisine diversity for restaurants, per-night pricing for hotels).
    """

    TIMEOUT_SECONDS = 40

    RESTAURANT_TOP = 7
    ATTRACTION_TOP = 7
    HOTEL_TOP = 7
    CAR_TOP = 5
    FLIGHT_TOP = 5

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            qctx = state.get("query_context", {})

            raw = {
                "restaurants": state.get("raw_restaurants", []),
                "travel_spots": state.get("raw_travel_spots", []),
                "hotels": state.get("raw_hotels", []),
                "car_rentals": state.get("raw_car_rentals", []),
                "flights": state.get("raw_flights", []),
            }

            self.logger.info(
                "WriterAgent starting 5 parallel LLM normalizations",
                extra={
                    "run_id": state.get("runId"),
                    **{f"raw_{k}": len(v) for k, v in raw.items()},
                },
            )

            results = await asyncio.gather(
                self._normalize_restaurants(raw["restaurants"], qctx),
                self._normalize_attractions(raw["travel_spots"], qctx),
                self._normalize_hotels(raw["hotels"], qctx),
                self._normalize_cars(raw["car_rentals"], qctx),
                self._normalize_flights(raw["flights"], qctx),
                return_exceptions=True,
            )

            restaurants = results[0] if not isinstance(results[0], Exception) else []
            attractions = results[1] if not isinstance(results[1], Exception) else []
            hotels = results[2] if not isinstance(results[2], Exception) else []
            cars = results[3] if not isinstance(results[3], Exception) else []
            flights = results[4] if not isinstance(results[4], Exception) else []

            # Log any failures
            warnings: list[str] = []
            for i, (name, res) in enumerate(
                zip(
                    ["restaurants", "attractions", "hotels", "cars", "flights"],
                    results,
                )
            ):
                if isinstance(res, Exception):
                    self.logger.error(f"WriterAgent {name} normalization failed: {res}")
                    warnings.append(f"Writer: {name} normalization failed")

            # Compute references — raw items not selected as top picks
            selected_urls: set[str] = set()
            for group in [restaurants, attractions, hotels, cars, flights]:
                for item in group:
                    selected_urls.add(canonicalize_url(item.url))

            all_raw = [item for items in raw.values() for item in items]
            references = [
                r for r in all_raw if canonicalize_url(r.get("url", "")) not in selected_urls
            ]

            self.logger.info(
                "WriterAgent completed",
                extra={
                    "run_id": state.get("runId"),
                    "restaurants": len(restaurants),
                    "attractions": len(attractions),
                    "hotels": len(hotels),
                    "cars": len(cars),
                    "flights": len(flights),
                    "references": len(references),
                },
            )

            result: dict[str, Any] = {
                "restaurants": [r.model_dump() for r in restaurants],
                "travel_spots": [a.model_dump() for a in attractions],
                "hotels": [h.model_dump() for h in hotels],
                "car_rentals": [c.model_dump() for c in cars],
                "flights": [f.model_dump() for f in flights],
                "references": references,
                "agent_statuses": {self.agent_id: "completed"},
            }

            if warnings:
                result["warnings"] = warnings

            return result

        except Exception as e:
            self.logger.error(
                f"WriterAgent failed: {e}",
                exc_info=True,
                extra={"run_id": state.get("runId")},
            )
            return self._failed_result(str(e))

    # ------------------------------------------------------------------
    # Normalization methods — one per category
    # ------------------------------------------------------------------

    async def _normalize_restaurants(
        self, items: list[dict[str, Any]], qctx: dict[str, Any]
    ) -> list[RestaurantOutput]:
        unique = self._dedup_by_url(items)
        if not unique:
            return []

        top = self._top_by_score(unique, n=20)
        search_text = self._format_search_text(top)
        destination = qctx.get("destination_city")

        system_prompt = build_restaurant_prompt(destination=destination)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, RestaurantList)
            return self._dedup_by_name_and_url(result.restaurants, top_n=self.RESTAURANT_TOP)
        except Exception as e:
            self.logger.error(f"Restaurant normalization failed: {e}", exc_info=True)
            return []

    async def _normalize_attractions(
        self, items: list[dict[str, Any]], qctx: dict[str, Any]
    ) -> list[AttractionOutput]:
        unique = self._dedup_by_url(items)
        if not unique:
            return []

        top = self._top_by_score(unique, n=20)
        search_text = self._format_search_text(top)
        destination = qctx.get("destination_city")

        system_prompt = build_attractions_prompt(destination=destination)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, AttractionList)
            # Deduplicate by name
            seen_names: set[str] = set()
            deduped: list[AttractionOutput] = []
            for a in result.attractions:
                norm_name = normalize_name(a.name)
                if norm_name not in seen_names:
                    seen_names.add(norm_name)
                    deduped.append(a)
            return deduped[: self.ATTRACTION_TOP]
        except Exception as e:
            self.logger.error(f"Attractions normalization failed: {e}", exc_info=True)
            return []

    async def _normalize_hotels(
        self, items: list[dict[str, Any]], qctx: dict[str, Any]
    ) -> list[HotelOutput]:
        unique = self._dedup_by_url(items)
        if not unique:
            return []

        top = self._top_by_score(unique, n=20)
        search_text = self._format_search_text(top)

        destination = qctx.get("destination_city")
        departing_date = qctx.get("departing_date", "")
        returning_date = qctx.get("returning_date")
        stay_nights = qctx.get("stay_nights")

        system_prompt = build_hotel_prompt(
            destination=destination,
            departing_date=departing_date,
            returning_date=returning_date,
            stay_nights=stay_nights,
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, HotelList)
            return self._dedup_by_name_and_url(result.hotels, top_n=self.HOTEL_TOP)
        except Exception as e:
            self.logger.error(f"Hotel normalization failed: {e}", exc_info=True)
            return []

    async def _normalize_cars(
        self, items: list[dict[str, Any]], qctx: dict[str, Any]
    ) -> list[CarRentalOutput]:
        if not items:
            return []

        search_text = self._format_search_text(items, content_limit=400)
        destination = qctx.get("destination_city")
        departing_date = qctx.get("departing_date")

        system_prompt = build_car_rental_prompt(
            destination=destination, departing_date=departing_date
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, CarRentalList)
            return result.cars[: self.CAR_TOP]
        except Exception as e:
            self.logger.error(f"Car rental normalization failed: {e}", exc_info=True)
            return []

    async def _normalize_flights(
        self, items: list[dict[str, Any]], qctx: dict[str, Any]
    ) -> list[FlightOutput]:
        if not items:
            return []

        search_text = self._format_search_text(items, content_limit=400)
        origin = qctx.get("origin_code") if qctx.get("origin_code") else qctx.get("origin_city")
        destination = qctx.get("destination_code") if qctx.get("destination_code") else qctx.get("destination_city")
        departing_date = qctx.get("departing_date")
        returning_date = qctx.get("returning_date")
        trip_type = "round-trip" if returning_date else "one-way"

        system_prompt = build_flight_prompt(
            origin=origin,
            destination=destination,
            departing_date=departing_date,
            returning_date=returning_date,
            trip_type=trip_type,
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, FlightList)
            return result.flights[: self.FLIGHT_TOP]
        except Exception as e:
            self.logger.error(f"Flight normalization failed: {e}", exc_info=True)
            return []
