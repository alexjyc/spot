"""Transport recommendation agent (car rentals + flights) — search only."""

from __future__ import annotations

import asyncio
from typing import Any

from app.agents.base import BaseAgent


class TransportAgent(BaseAgent):
    """Agent responsible for finding car rental and flight search results.

    Combines both transportation modalities since they're often compared together.
    Uses Tavily for web search. Returns raw deduplicated results.
    LLM normalization happens in WriterAgent.
    """

    TIMEOUT_SECONDS = 40
    CAR_TOP_N = 15
    FLIGHT_TOP_N = 15

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            qctx = state.get("query_context", {})

            self.logger.info(
                "TransportAgent starting parallel car + flight searches",
                extra={"run_id": state.get("runId")},
            )

            car_results, flight_results = await asyncio.gather(
                self._search_car_rentals(qctx),
                self._search_flights(qctx),
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
                "raw_car_rentals": cars,
                "raw_flights": flights,
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
        self, qctx: dict[str, Any]
    ) -> list[dict[str, Any]]:
        city = qctx.get("destination_city")
        airport = qctx.get("destination_code")
        departing_date = qctx.get("departing_date")
        returning_date = qctx.get("returning_date")

        if not city:
            self.logger.warning("No destination for car rentals")
            return []

        if returning_date:
            returning_date = " -> " + returning_date

        queries = [
            f"car rental {airport} airport pickup {departing_date}{returning_date}",
            f"best car rental deals {city} {departing_date}{returning_date}",
            f"local car rental companies {city} tourist {departing_date}{returning_date}",
        ]

        search_results = await self._parallel_search(queries)
        all_items = self._flatten_search_results(search_results)

        if not all_items:
            self.logger.warning("No car rental search results")
            return []

        unique = self._dedup_by_url(all_items)
        return self._top_by_score(unique, n=self.CAR_TOP_N)

    async def _search_flights(
        self, qctx: dict[str, Any]
    ) -> list[dict[str, Any]]:
        origin_airport = qctx.get("origin_code")
        destination_airport = qctx.get("destination_code")
        departing_date = qctx.get("departing_date")
        returning_date = qctx.get("returning_date")

        if not origin_airport or not destination_airport:
            origin_airport = qctx.get("origin_city")
            destination_airport = qctx.get("destination_city")

        if returning_date:
            returning_date = " -> " + returning_date
            
        queries = [
            f"flights {origin_airport} -> {destination_airport} {departing_date}{returning_date}",
            f"cheap flights {origin_airport} -> {destination_airport} {departing_date}{returning_date}",
            f"direct nonstop flights {origin_airport} -> {destination_airport} {departing_date}{returning_date}",
        ]

        search_results = await self._parallel_search(queries)
        all_items = self._flatten_search_results(search_results)

        if not all_items:
            self.logger.warning("No flight search results")
            return []

        unique = self._dedup_by_url(all_items)
        return self._top_by_score(unique, n=self.FLIGHT_TOP_N)
