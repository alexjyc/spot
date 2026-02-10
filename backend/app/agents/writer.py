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
from app.utils.dedup import canonicalize_url

logger = logging.getLogger(__name__)


class WriterAgent(BaseAgent):
    """Runs 5 parallel LLM calls to normalize raw search results into top picks.

    Each category uses its own specialized prompt to preserve domain-specific
    guardrails (e.g. cuisine diversity for restaurants, per-night pricing for hotels).
    """

    TIMEOUT_SECONDS = 40

    # Main pick caps (match prompt targets)
    RESTAURANT_TOP = 4
    ATTRACTION_TOP = 4
    HOTEL_TOP = 4
    CAR_TOP = 3
    FLIGHT_TOP = 3

    # LLM input sizes
    RESTAURANT_LLM_IN = 7
    ATTRACTION_LLM_IN = 7
    HOTEL_LLM_IN = 7
    CAR_LLM_IN = 5
    FLIGHT_LLM_IN = 5

    # Reference pool sizes
    RESTAURANT_REF_POOL = 10
    ATTRACTION_REF_POOL = 10
    HOTEL_REF_POOL = 10
    CAR_REF_POOL = 8
    FLIGHT_REF_POOL = 8

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
                self._normalize_restaurants(raw["restaurants"], qctx, run_id=state.get("runId")),
                self._normalize_attractions(raw["travel_spots"], qctx, run_id=state.get("runId")),
                self._normalize_hotels(raw["hotels"], qctx, run_id=state.get("runId")),
                self._normalize_cars(raw["car_rentals"], qctx, run_id=state.get("runId")),
                self._normalize_flights(raw["flights"], qctx, run_id=state.get("runId")),
                return_exceptions=True,
            )

            _empty: tuple[list, list[dict[str, Any]]] = ([], [])
            restaurants, rest_refs = results[0] if not isinstance(results[0], Exception) else _empty
            attractions, attr_refs = results[1] if not isinstance(results[1], Exception) else _empty
            hotels, hotel_refs = results[2] if not isinstance(results[2], Exception) else _empty
            cars, car_refs = results[3] if not isinstance(results[3], Exception) else _empty
            flights, flight_refs = results[4] if not isinstance(results[4], Exception) else _empty

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

            # Merge per-section references
            references: list[dict[str, Any]] = rest_refs + attr_refs + hotel_refs + car_refs + flight_refs

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
        self, items: list[dict[str, Any]], qctx: dict[str, Any], *, run_id: str | None
    ) -> tuple[list[RestaurantOutput], list[dict[str, Any]]]:
        if not items:
            return [], []

        ref_pool = self._top_by_score(items, n=self.RESTAURANT_REF_POOL)
        top = ref_pool[: self.RESTAURANT_LLM_IN]
        search_text = self._format_search_text(top, include_raw_content=True)
        destination = qctx.get("destination_city")

        system_prompt = build_restaurant_prompt(destination=destination)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, RestaurantList)
            picked = result.restaurants[:self.RESTAURANT_TOP]
            selected_urls = {canonicalize_url(r.url) for r in picked}
            refs = [
                {**r, "section": "restaurant"}
                for r in ref_pool
                if canonicalize_url(r.get("url", "")) not in selected_urls
            ]
            self.logger.info(
                "%s normalize(restaurants): raw_in=%d top_in=%d llm_out=%d post_dedup=%d refs=%d",
                self.agent_id,
                len(items),
                len(top),
                len(result.restaurants),
                len(picked),
                len(refs),
                extra={"run_id": run_id},
            )
            return picked, refs
        except Exception as e:
            self.logger.error(f"Restaurant normalization failed: {e}", exc_info=True)
            return [], []

    async def _normalize_attractions(
        self, items: list[dict[str, Any]], qctx: dict[str, Any], *, run_id: str | None
    ) -> tuple[list[AttractionOutput], list[dict[str, Any]]]:
        if not items:
            return [], []

        ref_pool = self._top_by_score(items, n=self.ATTRACTION_REF_POOL)
        top = ref_pool[: self.ATTRACTION_LLM_IN]
        search_text = self._format_search_text(top, include_raw_content=True)
        destination = qctx.get("destination_city")

        system_prompt = build_attractions_prompt(destination=destination)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, AttractionList)
            picked = result.attractions[:self.ATTRACTION_TOP]
            selected_urls = {canonicalize_url(a.url) for a in picked}
            refs = [
                {**r, "section": "attraction"}
                for r in ref_pool
                if canonicalize_url(r.get("url", "")) not in selected_urls
            ]
            self.logger.info(
                "%s normalize(attractions): raw_in=%d top_in=%d llm_out=%d post_dedup=%d refs=%d",
                self.agent_id,
                len(items),
                len(top),
                len(result.attractions),
                len(picked),
                len(refs),
                extra={"run_id": run_id},
            )
            return picked, refs
        except Exception as e:
            self.logger.error(f"Attractions normalization failed: {e}", exc_info=True)
            return [], []

    async def _normalize_hotels(
        self, items: list[dict[str, Any]], qctx: dict[str, Any], *, run_id: str | None
    ) -> tuple[list[HotelOutput], list[dict[str, Any]]]:
        if not items:
            return [], []

        ref_pool = self._top_by_score(items, n=self.HOTEL_REF_POOL)
        top = ref_pool[: self.HOTEL_LLM_IN]
        search_text = self._format_search_text(top, include_raw_content=True)

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
            picked = result.hotels[:self.HOTEL_TOP]
            selected_urls = {canonicalize_url(h.url) for h in picked}
            refs = [
                {**r, "section": "hotel"}
                for r in ref_pool
                if canonicalize_url(r.get("url", "")) not in selected_urls
            ]
            self.logger.info(
                "%s normalize(hotels): raw_in=%d top_in=%d llm_out=%d post_dedup=%d refs=%d",
                self.agent_id,
                len(items),
                len(top),
                len(result.hotels),
                len(picked),
                len(refs),
                extra={"run_id": run_id},
            )
            return picked, refs
        except Exception as e:
            self.logger.error(f"Hotel normalization failed: {e}", exc_info=True)
            return [], []

    async def _normalize_cars(
        self, items: list[dict[str, Any]], qctx: dict[str, Any], *, run_id: str | None
    ) -> tuple[list[CarRentalOutput], list[dict[str, Any]]]:
        if not items:
            return [], []

        ref_pool = self._top_by_score(items, n=self.CAR_REF_POOL)
        top = ref_pool[: self.CAR_LLM_IN]
        search_text = self._format_search_text(top, content_limit=400, include_raw_content=True)
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
            picked = result.cars[: self.CAR_TOP]
            selected_urls = {canonicalize_url(c.url) for c in picked}
            refs = [
                {**r, "section": "car"}
                for r in ref_pool
                if canonicalize_url(r.get("url", "")) not in selected_urls
            ]
            self.logger.info(
                "%s normalize(cars): raw_in=%d top_in=%d llm_out=%d picked=%d refs=%d",
                self.agent_id,
                len(items),
                len(top),
                len(result.cars),
                len(picked),
                len(refs),
                extra={"run_id": run_id},
            )
            return picked, refs
        except Exception as e:
            self.logger.error(f"Car rental normalization failed: {e}", exc_info=True)
            return [], []

    async def _normalize_flights(
        self, items: list[dict[str, Any]], qctx: dict[str, Any], *, run_id: str | None
    ) -> tuple[list[FlightOutput], list[dict[str, Any]]]:
        if not items:
            return [], []

        ref_pool = self._top_by_score(items, n=self.FLIGHT_REF_POOL)
        top = ref_pool[: self.FLIGHT_LLM_IN]
        search_text = self._format_search_text(top, content_limit=400, include_raw_content=True)
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
            picked = result.flights[: self.FLIGHT_TOP]
            selected_urls = {canonicalize_url(f.url) for f in picked}
            refs = [
                {**r, "section": "flight"}
                for r in ref_pool
                if canonicalize_url(r.get("url", "")) not in selected_urls
            ]
            self.logger.info(
                "%s normalize(flights): raw_in=%d top_in=%d llm_out=%d picked=%d refs=%d",
                self.agent_id,
                len(items),
                len(top),
                len(result.flights),
                len(picked),
                len(refs),
                extra={"run_id": run_id},
            )
            return picked, refs
        except Exception as e:
            self.logger.error(f"Flight normalization failed: {e}", exc_info=True)
            return [], []
