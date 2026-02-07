"""Transport recommendation agent (car rentals + flights)."""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.schemas.spot_on import CarRentalOutput, FlightOutput, CarRentalList, FlightList


class TransportAgent(BaseAgent):
    """Agent responsible for finding car rental and flight options.

    Combines both transportation modalities since they're often compared together.
    Uses Tavily for web search and LLM for normalization.
    """

    TIMEOUT_SECONDS = 40
    CAR_RESULTS = 3
    FLIGHT_RESULTS = 3

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            constraints = state.get("constraints", {})

            destination = constraints.get("destination")
            if not destination or not isinstance(destination, str):
                self.logger.warning("Invalid or missing destination in constraints")
                return self._failed_result("Missing or invalid destination")

            self.logger.info(
                "TransportAgent starting parallel car + flight searches",
                extra={"run_id": state.get("runId")},
            )

            car_results, flight_results = await asyncio.gather(
                self._search_car_rentals(constraints),
                self._search_flights(constraints),
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

            self.logger.info(
                "TransportAgent completed",
                extra={
                    "run_id": state.get("runId"),
                    "car_count": len(cars),
                    "flight_count": len(flights),
                    "status": status,
                },
            )

            result: dict[str, Any] = {
                "car_rentals": cars,
                "flights": flights,
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
        self, constraints: dict[str, Any]
    ) -> list[dict[str, Any]]:
        destination = constraints.get("destination")
        departing_date = constraints.get("departing_date")

        if not destination:
            self.logger.warning("No destination for car rentals")
            return []

        city = self._extract_city(destination)
        date_str = f" {departing_date}" if departing_date else " 2026"

        queries = [
            f"car rental {city}{date_str}",
            f"rent a car {city} airport",
            f"best car rental deals {city}",
        ]

        search_results = await self._parallel_search(queries)
        all_items = self._flatten_search_results(search_results)

        if not all_items:
            self.logger.warning("No car rental search results")
            return []

        unique_items = self._dedup_by_url(all_items)
        sorted_items = self._top_by_score(unique_items, n=15)

        cars = await self._normalize_cars_with_llm(sorted_items, constraints)
        return [c.model_dump() for c in cars[: self.CAR_RESULTS]]

    async def _search_flights(
        self, constraints: dict[str, Any]
    ) -> list[dict[str, Any]]:
        origin = constraints.get("origin")
        destination = constraints.get("destination")
        departing_date = constraints.get("departing_date")
        returning_date = constraints.get("returning_date")

        if not origin or not destination:
            self.logger.warning("Missing origin or destination for flights")
            return []

        trip_type = "round-trip" if returning_date else "one-way"
        date_str = f" {departing_date}" if departing_date else ""
        return_str = f" return {returning_date}" if returning_date else ""

        queries = [
            f"flights from {origin} to {destination}{date_str}{return_str}",
            f"{origin} to {destination} flight {trip_type}",
            f"cheap flights {origin} {destination}{date_str}",
        ]

        search_results = await self._parallel_search(queries, max_results=5)
        all_items = self._flatten_search_results(search_results)

        if not all_items:
            self.logger.warning("No flight search results")
            return []

        unique_items = self._dedup_by_url(all_items)
        sorted_items = self._top_by_score(unique_items, n=15)

        flights = await self._normalize_flights_with_llm(sorted_items, constraints)
        return [f.model_dump() for f in flights[: self.FLIGHT_RESULTS]]

    async def _normalize_cars_with_llm(
        self, items: list[dict[str, Any]], constraints: dict[str, Any]
    ) -> list[CarRentalOutput]:
        if not items:
            return []

        search_text = self._format_search_text(items, content_limit=400)
        destination = constraints.get("destination", "the destination")
        departing_date = constraints.get("departing_date", "")

        system_prompt = f"""You are a car rental expert. Parse the search results and extract 3-4 car rental options for {destination}.

For each rental option, extract:
- provider: Rental company name (e.g., 'Hertz', 'Budget', 'Enterprise')
- vehicle_class: Vehicle type (e.g., 'compact', 'sedan', 'SUV', 'luxury')
- price_per_day: Per-day price with currency (e.g., '$45', '₩60,000'). Extract if available.
- pickup_location: Pickup location (e.g., 'Airport', 'Downtown', 'City Center')
- url: The original URL
- why_recommended: 1-2 sentences explaining why this is a good option

Context:
- Pickup date: {departing_date}

Return results as a JSON array. Generate unique IDs using format "car_{{destination_code}}_{{number}}"."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, CarRentalList)
            return result.cars
        except Exception as e:
            self.logger.error(f"Car rental LLM normalization failed: {e}", exc_info=True)
            return []

    async def _normalize_flights_with_llm(
        self, items: list[dict[str, Any]], constraints: dict[str, Any]
    ) -> list[FlightOutput]:
        if not items:
            return []

        search_text = self._format_search_text(items, content_limit=400)
        origin = constraints.get("origin", "")
        destination = constraints.get("destination", "")
        departing_date = constraints.get("departing_date", "")
        returning_date = constraints.get("returning_date")
        trip_type = "round-trip" if returning_date else "one-way"

        system_prompt = f"""You are a flight search expert. Parse the search results and extract 3-4 flight options from {origin} to {destination}.

For each flight option, extract:
- airline: Airline name (e.g., 'United', 'Korean Air', 'Delta'). Set to null if not mentioned.
- route: Route description (e.g., 'Tokyo NRT -> Seoul ICN', 'LAX -> JFK')
- trip_type: Must be "{trip_type}"
- price_range: Price range with currency (e.g., '$200-$350', '₩300,000-₩500,000'). Extract if available.
- url: The original URL
- snippet: 1-2 sentence description of the flight option
- why_recommended: 1-2 sentences explaining why this is a good option (e.g., 'Direct flight', 'Best price', 'Premium airline')

Context:
- Departure date: {departing_date}
- Return date: {returning_date or 'N/A'}
- Trip type: {trip_type}

Return results as a JSON array. Generate unique IDs using format "flight_{{origin_code}}_{{dest_code}}_{{number}}"."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, FlightList)
            return result.flights
        except Exception as e:
            self.logger.error(f"Flight LLM normalization failed: {e}", exc_info=True)
            return []
