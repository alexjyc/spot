"""Hotel recommendation agent."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.schemas.spot_on import HotelOutput, HotelList


class HotelAgent(BaseAgent):
    """Agent responsible for finding hotel recommendations with per-night pricing.

    Uses Tavily for web search and LLM for normalization.
    Returns 3-5 hotel recommendations with pricing from departing date.
    """

    TIMEOUT_SECONDS = 30
    MIN_RESULTS = 3
    MAX_RESULTS = 5

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            constraints = state.get("constraints", {})
            destination = constraints.get("destination")
            departing_date = constraints.get("departing_date")

            if not destination or not isinstance(destination, str):
                self.logger.warning("Invalid or missing destination in constraints")
                return self._failed_result("Missing or invalid destination")

            city = self._extract_city(destination)
            queries = self._build_queries(city, departing_date, constraints)
            self.logger.info(
                f"HotelAgent searching with {len(queries)} queries",
                extra={"run_id": state.get("runId"), "destination": destination},
            )

            search_results = await self.with_timeout(
                self._parallel_search(queries, max_results=6),
                timeout_seconds=self.TIMEOUT_SECONDS,
            )

            if search_results is None:
                return self._failed_result("Search timeout")

            all_items = self._flatten_search_results(search_results)
            if not all_items:
                return self._failed_result("No search results found")

            hotels = await self._normalize_with_llm(all_items, constraints)
            if not hotels:
                return self._failed_result("LLM normalization returned no results")

            final = self._dedup_by_name_and_url(hotels, top_n=self.MAX_RESULTS)

            if len(final) < self.MIN_RESULTS:
                self.logger.warning(
                    f"HotelAgent only found {len(final)} hotels (min: {self.MIN_RESULTS})"
                )
                return {
                    "hotels": [h.model_dump() for h in final],
                    "agent_statuses": {self.agent_id: "partial"},
                    "warnings": [
                        f"Only found {len(final)} hotels instead of {self.MIN_RESULTS}+"
                    ],
                }

            self.logger.info(
                "HotelAgent completed",
                extra={
                    "run_id": state.get("runId"),
                    "result_count": len(final),
                },
            )

            return {
                "hotels": [h.model_dump() for h in final],
                "agent_statuses": {self.agent_id: "completed"},
            }

        except Exception as e:
            self.logger.error(
                f"HotelAgent failed: {e}",
                exc_info=True,
                extra={"run_id": state.get("runId")},
            )
            return self._failed_result(str(e))

    def _build_queries(
        self, city: str, departing_date: str | None, constraints: dict[str, Any]
    ) -> list[str]:
        date_str = f" {departing_date}" if departing_date else " 2026"

        queries = [
            f"best hotels in {city}{date_str}",
            f"top rated hotels {city}{date_str}",
            f"hotel recommendations {city}{date_str}",
        ]

        budget = constraints.get("budget", "moderate")
        if budget == "luxury":
            queries.append(f"luxury hotels {city}{date_str}")
        elif budget == "budget":
            queries.append(f"affordable hotels {city}{date_str}")

        return queries

    async def _normalize_with_llm(
        self, items: list[dict[str, Any]], constraints: dict[str, Any]
    ) -> list[HotelOutput]:
        unique_items = self._dedup_by_url(items)
        if not unique_items:
            return []

        sorted_items = self._top_by_score(unique_items, n=10)
        search_text = self._format_search_text(sorted_items)

        destination = constraints.get("destination", "the destination")
        departing_date = constraints.get("departing_date", "")
        budget = constraints.get("budget", "moderate")

        system_prompt = f"""You are a hotel recommendation expert. Parse the search results and extract 5-7 hotel recommendations for {destination}.

For each hotel, extract:
- name: Hotel name
- area: Neighborhood/district (if mentioned)
- price_per_night: Per-night price with currency (e.g., '$150', '₩180,000'). Extract from content if available.
- url: The original URL
- snippet: 1-2 sentence description
- why_recommended: 1-2 sentences explaining why this is a good choice
- amenities: List of key amenities (e.g., 'wifi', 'pool', 'breakfast-included', 'gym', 'parking')

Context:
- Check-in date: {departing_date}
- Budget preference: {budget}

Prioritize hotels that match the budget preference and are well-located for tourists.

Return results as a JSON array. Generate unique IDs using format "hotel_{{destination_code}}_{{number}}"."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, HotelList)
            return result.hotels
        except Exception as e:
            self.logger.error(f"LLM normalization failed: {e}", exc_info=True)
            return []
