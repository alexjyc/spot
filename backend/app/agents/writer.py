"""NormalizeAgent — normalizes raw search results into structured items."""

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

logger = logging.getLogger(__name__)


class NormalizeAgent(BaseAgent):
    """Runs 5 parallel LLM calls to normalize raw search results into structured output.

    Each category uses its own specialized prompt to preserve domain-specific
    guardrails (e.g. cuisine diversity for restaurants, per-night pricing for hotels).
    """

    TIMEOUT_SECONDS = 40

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
                "NormalizeAgent starting 5 parallel LLM normalizations",
                extra={
                    "run_id": state.get("runId"),
                    **{f"raw_{k}": len(v) for k, v in raw.items()},
                },
            )

            results = await asyncio.gather(
                self._normalize_restaurants(raw["restaurants"], qctx, run_id=state.get("runId")),
                self._normalize_attractions(raw["travel_spots"], qctx, run_id=state.get("runId")),
                self._normalize_hotels(raw["hotels"], qctx, run_id=state.get("runId")),
                self._normalize_cars(raw["car_rentals"], qctx, run_id=state.get("runId")),
                self._normalize_flights(raw["flights"], qctx, run_id=state.get("runId")),
                return_exceptions=True,
            )

            restaurants = results[0] if not isinstance(results[0], Exception) else []
            attractions = results[1] if not isinstance(results[1], Exception) else []
            hotels = results[2] if not isinstance(results[2], Exception) else []
            cars = results[3] if not isinstance(results[3], Exception) else []
            flights = results[4] if not isinstance(results[4], Exception) else []

            # Log any failures
            warnings: list[str] = []
            for name, res in zip(
                ["restaurants", "attractions", "hotels", "cars", "flights"],
                results,
            ):
                if isinstance(res, Exception):
                    self.logger.error(f"NormalizeAgent {name} normalization failed: {res}")
                    warnings.append(f"Writer: {name} normalization failed")

            self.logger.info(
                "NormalizeAgent completed",
                extra={
                    "run_id": state.get("runId"),
                    "restaurants": len(restaurants),
                    "attractions": len(attractions),
                    "hotels": len(hotels),
                    "cars": len(cars),
                    "flights": len(flights),
                },
            )

            result: dict[str, Any] = {
                "restaurants": [r.model_dump() for r in restaurants],
                "travel_spots": [a.model_dump() for a in attractions],
                "hotels": [h.model_dump() for h in hotels],
                "car_rentals": [c.model_dump() for c in cars],
                "flights": [f.model_dump() for f in flights],
                "references": [],
                "agent_statuses": {self.agent_id: "completed"},
            }

            if warnings:
                result["warnings"] = warnings

            return result

        except Exception as e:
            self.logger.error(
                f"NormalizeAgent failed: {e}",
                exc_info=True,
                extra={"run_id": state.get("runId")},
            )
            return self._failed_result(str(e))

    # ------------------------------------------------------------------
    # Normalization methods — one per category
    # ------------------------------------------------------------------

    async def _normalize_restaurants(
        self, items: list[dict[str, Any]], qctx: dict[str, Any], *, run_id: str | None
    ) -> list[RestaurantOutput]:
        if not items:
            return []

        deduped = self._dedup_by_url_and_title(items)
        search_text = self._format_search_text(deduped, raw_content_limit=0)
        destination = qctx.get("destination_city")

        system_prompt = build_restaurant_prompt(destination=destination)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, RestaurantList)
            self.logger.info(
                "%s normalize(restaurants): raw_in=%d deduped=%d llm_out=%d",
                self.agent_id,
                len(items),
                len(deduped),
                len(result.restaurants),
                extra={"run_id": run_id},
            )
            return result.restaurants
        except Exception as e:
            self.logger.error(f"Restaurant normalization failed: {e}", exc_info=True)
            return []

    async def _normalize_attractions(
        self, items: list[dict[str, Any]], qctx: dict[str, Any], *, run_id: str | None
    ) -> list[AttractionOutput]:
        if not items:
            return []

        deduped = self._dedup_by_url_and_title(items)
        search_text = self._format_search_text(deduped, raw_content_limit=0)
        destination = qctx.get("destination_city")

        system_prompt = build_attractions_prompt(destination=destination)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, AttractionList)
            self.logger.info(
                "%s normalize(attractions): raw_in=%d deduped=%d llm_out=%d",
                self.agent_id,
                len(items),
                len(deduped),
                len(result.attractions),
                extra={"run_id": run_id},
            )
            return result.attractions
        except Exception as e:
            self.logger.error(f"Attractions normalization failed: {e}", exc_info=True)
            return []

    async def _normalize_hotels(
        self, items: list[dict[str, Any]], qctx: dict[str, Any], *, run_id: str | None
    ) -> list[HotelOutput]:
        if not items:
            return []

        deduped = self._dedup_by_url_and_title(items)
        search_text = self._format_search_text(deduped, raw_content_limit=0)

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
            self.logger.info(
                "%s normalize(hotels): raw_in=%d deduped=%d llm_out=%d",
                self.agent_id,
                len(items),
                len(deduped),
                len(result.hotels),
                extra={"run_id": run_id},
            )
            return result.hotels
        except Exception as e:
            self.logger.error(f"Hotel normalization failed: {e}", exc_info=True)
            return []

    async def _normalize_cars(
        self, items: list[dict[str, Any]], qctx: dict[str, Any], *, run_id: str | None
    ) -> list[CarRentalOutput]:
        if not items:
            return []

        deduped = self._dedup_by_url_and_title(items)
        search_text = self._format_search_text(deduped, content_limit=400, raw_content_limit=0)
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
            self.logger.info(
                "%s normalize(cars): raw_in=%d deduped=%d llm_out=%d",
                self.agent_id,
                len(items),
                len(deduped),
                len(result.cars),
                extra={"run_id": run_id},
            )
            return result.cars
        except Exception as e:
            self.logger.error(f"Car rental normalization failed: {e}", exc_info=True)
            return []

    async def _normalize_flights(
        self, items: list[dict[str, Any]], qctx: dict[str, Any], *, run_id: str | None
    ) -> list[FlightOutput]:
        if not items:
            return []

        deduped = self._dedup_by_url_and_title(items)
        search_text = self._format_search_text(deduped, content_limit=400, raw_content_limit=0)
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
            self.logger.info(
                "%s normalize(flights): raw_in=%d deduped=%d llm_out=%d",
                self.agent_id,
                len(items),
                len(deduped),
                len(result.flights),
                extra={"run_id": run_id},
            )
            return result.flights
        except Exception as e:
            self.logger.error(f"Flight normalization failed: {e}", exc_info=True)
            return []
