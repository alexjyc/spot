import asyncio
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.agents.prompt import build_car_rental_prompt, build_flight_prompt
from app.schemas.spot_on import CarRentalList, FlightList


class TransportAgent(BaseAgent):
    """Agent responsible for finding and normalizing car rental and flight results.

    Combines both transportation modalities. Searches via Tavily, then
    normalizes raw results inline using LLM calls.
    """

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            qctx = state.get("query_context", {})
            settings = self.deps.settings

            self.logger.info(
                "TransportAgent starting parallel car + flight searches",
                extra={"run_id": state.get("runId")},
            )

            car_results, flight_results = await asyncio.gather(
                self._search_car_rentals(qctx, run_id=state.get("runId")),
                self._search_flights(qctx, run_id=state.get("runId")),
                return_exceptions=True,
            )

            cars = [] if isinstance(car_results, Exception) else car_results
            flights = [] if isinstance(flight_results, Exception) else flight_results

            if isinstance(car_results, Exception) and isinstance(
                flight_results, Exception
            ):
                self.logger.error("Both car and flight searches failed")
                return self._failed_result("Both transport searches failed")

            warnings: list[str] = []
            status = "completed"

            if isinstance(car_results, Exception):
                warnings.append("Car rental search failed")
                status = "partial"
                self.logger.warning(f"Car rental search failed: {car_results}")

            if isinstance(flight_results, Exception):
                warnings.append("Flight search failed")
                status = "partial"
                self.logger.warning(f"Flight search failed: {flight_results}")

            chunk_size = settings.normalize_chunk_size
            norm_cars, norm_flights = await asyncio.gather(
                self._normalize_chunked(
                    cars,
                    lambda chunk: self._normalize_cars(chunk, qctx, run_id=state.get("runId")),
                    chunk_size=chunk_size,
                ),
                self._normalize_chunked(
                    flights,
                    lambda chunk: self._normalize_flights(chunk, qctx, run_id=state.get("runId")),
                    chunk_size=chunk_size,
                ),
                return_exceptions=True,
            )

            if isinstance(norm_cars, Exception):
                self.logger.warning(f"Car normalization failed: {norm_cars}")
                norm_cars = []
            if isinstance(norm_flights, Exception):
                self.logger.warning(
                    f"Flight normalization failed: {norm_flights}",
                    extra={"run_id": state.get("runId"), "error_type": type(norm_flights).__name__}
                )
                norm_flights = []

            dest = qctx.get("destination_city", "").lower().replace(" ", "_").replace(",", "")
            for i, item in enumerate(norm_cars, 1):
                item.id = f"car_{dest}_{i}"
            for i, item in enumerate(norm_flights, 1):
                item.id = f"flight_{dest}_{i}"

            self.logger.info(
                "TransportAgent completed",
                extra={
                    "run_id": state.get("runId"),
                    "car_count": len(norm_cars),
                    "flight_count": len(norm_flights),
                    "status": status,
                },
            )

            result: dict[str, Any] = {
                "car_rentals": [c.model_dump() for c in norm_cars],
                "flights": [f.model_dump() for f in norm_flights],
                "agent_statuses": {self.agent_id: status},
            }

            if warnings:
                result["warnings"] = warnings

            return result

        except Exception as e:
            self.logger.error(
                f"TransportAgent failed: {e}",
                exc_info=True,
                extra={"run_id": state.get("runId")},
            )
            return self._failed_result(str(e))

    async def _search_car_rentals(
        self, qctx: dict[str, Any], *, run_id: str | None
    ) -> list[dict[str, Any]]:
        settings = self.deps.settings
        city = qctx.get("destination_city")
        airport = qctx.get("destination_code")
        departing_date = qctx.get("departing_date")
        returning_date = qctx.get("returning_date")

        if not city:
            self.logger.warning("No destination for car rentals")
            return []

        if returning_date:
            returning_date = " -> " + returning_date

        primary = [
            f"car rental {airport} airport pickup {departing_date}{returning_date}",
            f"best car rental deals {city} {departing_date}{returning_date}",
            f"local car rental companies {city} tourist {departing_date}{returning_date}",
        ]
        fallback = [
            f"car rental {city} airport hours phone address",
            f"economy SUV minivan car rental {city} price per day",
        ]

        return await self._search_with_fallback(
            primary,
            fallback,
            top_n=settings.search_top_n,
            run_id=run_id,
            label="cars",
            max_results_per_query=settings.tavily_max_results,
            include_domains=["kayak.com", "rentalcars.com", "hertz.com",
                             "enterprise.com", "avis.com", "budget.com", "sixt.com"],
        )

    async def _search_flights(
        self, qctx: dict[str, Any], *, run_id: str | None
    ) -> list[dict[str, Any]]:
        settings = self.deps.settings
        origin_airport = qctx.get("origin_code")
        destination_airport = qctx.get("destination_code")
        departing_date = qctx.get("departing_date")
        returning_date = qctx.get("returning_date")
        budget = qctx.get("budget")

        if not origin_airport or not destination_airport:
            origin_airport = qctx.get("origin_city")
            destination_airport = qctx.get("destination_city")

        if returning_date:
            returning_date = " -> " + returning_date

        if budget == "Luxury":
            price_query = f"business class premium flights {origin_airport} -> {destination_airport} {departing_date}{returning_date}"
        elif budget == "Mid-range":
            price_query = f"best value flights {origin_airport} -> {destination_airport} {departing_date}{returning_date}"
        else:
            price_query = f"cheap flights {origin_airport} -> {destination_airport} {departing_date}{returning_date}"

        primary = [
            f"flights {origin_airport} -> {destination_airport} {departing_date}{returning_date}",
            price_query,
            f"direct nonstop flights {origin_airport} -> {destination_airport} {departing_date}{returning_date}",
        ]
        fallback = [
            f"best airlines for flights {origin_airport} to {destination_airport} direct",
            f"flight schedule {origin_airport} to {destination_airport} {departing_date}{returning_date}",
        ]

        return await self._search_with_fallback(
            primary,
            fallback,
            top_n=settings.search_top_n,
            run_id=run_id,
            label="flights",
            max_results_per_query=settings.tavily_max_results,
            include_domains=["google.com/flights", "kayak.com", "skyscanner.com",
                             "expedia.com", "trip.com", "momondo.com"],
        )

    async def _normalize_cars(
        self, items: list[dict[str, Any]], qctx: dict[str, Any], *, run_id: str | None
    ) -> list:
        if not items:
            return []

        deduped = self._dedup_by_url_and_title(items)
        search_text = self._format_search_text(deduped, content_limit=400, raw_content_limit=0)
        destination = qctx.get("destination_city")
        departing_date = qctx.get("departing_date")
        returning_date = qctx.get("returning_date")

        system_prompt = build_car_rental_prompt(
            destination=destination,
            departing_date=departing_date,
            returning_date=returning_date,
            item_count=len(deduped)
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, CarRentalList)
            self.logger.info(
                "%s normalize(cars): deduped=%d llm_out=%d",
                self.agent_id,
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
    ) -> list:
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
            item_count=len(deduped)
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, FlightList)
            self.logger.info(
                "%s normalize(flights): deduped=%d llm_out=%d",
                self.agent_id,
                len(deduped),
                len(result.flights),
                extra={"run_id": run_id},
            )
            return result.flights
        except Exception as e:
            self.logger.error(f"Flight normalization failed: {e}", exc_info=True)
            return []
