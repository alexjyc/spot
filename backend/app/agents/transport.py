"""Transport recommendation agent (car rentals + flights)."""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.schemas.spot_on import CarRentalOutput, FlightOutput, CarRentalList, FlightList
from app.utils.dedup import canonicalize_url, normalize_name


class TransportAgent(BaseAgent):
    """Agent responsible for finding car rental and flight options.

    Combines both transportation modalities since they're often compared together.
    Uses Tavily for web search and LLM for normalization.
    """

    TIMEOUT_SECONDS = 40  # Longer timeout due to two sub-searches
    CAR_RESULTS = 3
    FLIGHT_RESULTS = 3

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute transport search workflow (parallel car + flight searches).

        Args:
            state: Graph state containing constraints (origin, destination, dates)

        Returns:
            Partial state update with car_rentals and flights lists
        """
        try:
            constraints = state.get("constraints", {})

            # Validate required fields
            destination = constraints.get("destination")
            if not destination or not isinstance(destination, str):
                self.logger.warning("Invalid or missing destination in constraints")
                return self._failed_result("Missing or invalid destination")

            # Parallel execution of car and flight searches
            self.logger.info(
                "TransportAgent starting parallel car + flight searches",
                extra={"run_id": state.get("runId")},
            )

            car_task = self._search_car_rentals(constraints)
            flight_task = self._search_flights(constraints)

            car_results, flight_results = await asyncio.gather(
                car_task, flight_task, return_exceptions=True
            )

            # Handle results (don't fail if one sub-search fails)
            cars = [] if isinstance(car_results, Exception) else car_results
            flights = [] if isinstance(flight_results, Exception) else flight_results

            # Determine status
            if isinstance(car_results, Exception) and isinstance(
                flight_results, Exception
            ):
                self.logger.error("Both car and flight searches failed")
                return self._failed_result("Both transport searches failed")

            warnings = []
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
                f"TransportAgent completed",
                extra={
                    "run_id": state.get("runId"),
                    "car_count": len(cars),
                    "flight_count": len(flights),
                    "status": status,
                },
            )

            result = {
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
        """Search for car rental options.

        Args:
            constraints: User constraints (destination, dates, etc.)

        Returns:
            List of car rental dicts (serialized CarRentalOutput)

        Raises:
            Exception if search fails
        """
        destination = constraints.get("destination")
        departing_date = constraints.get("departing_date")

        if not destination:
            self.logger.warning("No destination for car rentals")
            return []

        city = destination.split("(")[0].strip()
        date_str = f" {departing_date}" if departing_date else " 2026"

        queries = [
            f"car rental {city}{date_str}",
            f"rent a car {city} airport",
            f"best car rental deals {city}",
        ]

        # Parallel search
        search_tasks = [
            self.deps.tavily.search(q, max_results=5) for q in queries
        ]
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Flatten results
        all_items = []
        for result_set in search_results:
            if isinstance(result_set, Exception):
                continue
            all_items.extend(result_set.get("results", []))

        if not all_items:
            self.logger.warning("No car rental search results")
            return []

        # Deduplicate by URL
        seen_urls = set()
        unique_items = []
        for item in all_items:
            url = canonicalize_url(item.get("url", ""))
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_items.append(item)

        # Take top 15 by score
        sorted_items = sorted(
            unique_items, key=lambda x: x.get("score", 0), reverse=True
        )[:15]

        # LLM normalization
        cars = await self._normalize_cars_with_llm(sorted_items, constraints)

        return [c.model_dump() for c in cars[: self.CAR_RESULTS]]

    async def _search_flights(
        self, constraints: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Search for flight options.

        Args:
            constraints: User constraints (origin, destination, dates, etc.)

        Returns:
            List of flight dicts (serialized FlightOutput)

        Raises:
            Exception if search fails
        """
        origin = constraints.get("origin")
        destination = constraints.get("destination")
        departing_date = constraints.get("departing_date")
        returning_date = constraints.get("returning_date")

        if not origin or not destination:
            self.logger.warning("Missing origin or destination for flights")
            return []

        # Determine trip type
        trip_type = "round-trip" if returning_date else "one-way"

        # Build queries
        date_str = f" {departing_date}" if departing_date else ""
        return_str = f" return {returning_date}" if returning_date else ""

        queries = [
            f"flights from {origin} to {destination}{date_str}{return_str}",
            f"{origin} to {destination} flight {trip_type}",
            f"cheap flights {origin} {destination}{date_str}",
        ]

        # Parallel search
        search_tasks = [
            self.deps.tavily.search(q, max_results=5) for q in queries
        ]
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Flatten results
        all_items = []
        for result_set in search_results:
            if isinstance(result_set, Exception):
                continue
            all_items.extend(result_set.get("results", []))

        if not all_items:
            self.logger.warning("No flight search results")
            return []

        # Deduplicate by URL
        seen_urls = set()
        unique_items = []
        for item in all_items:
            url = canonicalize_url(item.get("url", ""))
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_items.append(item)

        # Take top 15 by score
        sorted_items = sorted(
            unique_items, key=lambda x: x.get("score", 0), reverse=True
        )[:15]

        # LLM normalization
        flights = await self._normalize_flights_with_llm(sorted_items, constraints)

        return [f.model_dump() for f in flights[: self.FLIGHT_RESULTS]]

    async def _normalize_cars_with_llm(
        self, items: list[dict[str, Any]], constraints: dict[str, Any]
    ) -> list[CarRentalOutput]:
        """Use LLM to parse car rental search results.

        Args:
            items: Deduplicated Tavily search results
            constraints: User constraints

        Returns:
            List of CarRentalOutput objects
        """
        if not items:
            return []

        search_text = "\n\n".join(
            [
                f"Title: {item.get('title', 'N/A')}\n"
                f"URL: {item.get('url', 'N/A')}\n"
                f"Content: {item.get('content', 'N/A')[:400]}"
                for item in items
            ]
        )

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
        """Use LLM to parse flight search results.

        Args:
            items: Deduplicated Tavily search results
            constraints: User constraints

        Returns:
            List of FlightOutput objects
        """
        if not items:
            return []

        search_text = "\n\n".join(
            [
                f"Title: {item.get('title', 'N/A')}\n"
                f"URL: {item.get('url', 'N/A')}\n"
                f"Content: {item.get('content', 'N/A')[:400]}"
                for item in items
            ]
        )

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
