"""Restaurant recommendation agent."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.schemas.spot_on import RestaurantOutput, RestaurantList


class RestaurantAgent(BaseAgent):
    """Agent responsible for finding restaurant recommendations.

    Uses Tavily for web search and LLM for normalization/ranking.
    Returns top 5 restaurants with enrichment-ready URLs.
    """

    TIMEOUT_SECONDS = 30
    MAX_RESULTS = 5

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            constraints = state.get("constraints", {})
            destination = constraints.get("destination")

            if not destination or not isinstance(destination, str):
                self.logger.warning("Invalid or missing destination in constraints")
                return self._failed_result("Missing or invalid destination")

            city = self._extract_city(destination)
            queries = self._build_queries(city, constraints)
            self.logger.info(
                f"RestaurantAgent searching with {len(queries)} queries",
                extra={"run_id": state.get("runId"), "destination": destination},
            )

            search_results = await self.with_timeout(
                self._parallel_search(queries), timeout_seconds=self.TIMEOUT_SECONDS
            )

            if search_results is None:
                return self._failed_result("Search timeout")

            all_items = self._flatten_search_results(search_results)
            if not all_items:
                return self._failed_result("No search results found")

            restaurants = await self._normalize_with_llm(all_items, constraints)
            if not restaurants:
                return self._failed_result("LLM normalization returned no results")

            final = self._dedup_by_name_and_url(restaurants, top_n=self.MAX_RESULTS)

            self.logger.info(
                "RestaurantAgent completed",
                extra={
                    "run_id": state.get("runId"),
                    "result_count": len(final),
                    "queries_used": len(queries),
                },
            )

            return {
                "restaurants": [r.model_dump() for r in final],
                "agent_statuses": {self.agent_id: "completed"},
            }

        except Exception as e:
            self.logger.error(
                f"RestaurantAgent failed: {e}",
                exc_info=True,
                extra={"run_id": state.get("runId")},
            )
            return self._failed_result(str(e))

    def _build_queries(self, city: str, constraints: dict[str, Any]) -> list[str]:
        queries = [
            f"best restaurants in {city} 2026",
            f"top rated dining {city}",
            f"must-try restaurants {city}",
        ]
        interest_q = self._build_interest_query(
            constraints.get("interests", []), "restaurants", city
        )
        if interest_q:
            queries.append(interest_q)
        return queries

    async def _normalize_with_llm(
        self, items: list[dict[str, Any]], constraints: dict[str, Any]
    ) -> list[RestaurantOutput]:
        unique_items = self._dedup_by_url(items)
        if not unique_items:
            return []

        sorted_items = self._top_by_score(unique_items, n=10)
        search_text = self._format_search_text(sorted_items)

        destination = constraints.get("destination", "the destination")
        interests = constraints.get("interests", [])
        interest_context = (
            f" User interests: {', '.join(interests)}." if interests else ""
        )

        system_prompt = f"""You are a restaurant recommendation expert. Parse the search results and extract the top 8-10 restaurant recommendations for first-day dining in {destination}.

For each restaurant, extract:
- name: Restaurant name
- cuisine: Type of cuisine
- area: Neighborhood/district (if mentioned)
- price_range: Price level like '$', '$$', '$$$' (if mentioned)
- url: The original URL
- snippet: 1-2 sentence description
- why_recommended: 1-2 sentences explaining why this is a good choice for first day
- tags: List of relevant tags (e.g., 'michelin-star', 'local-favorite', 'vegetarian-friendly')

Prioritize well-known, highly-rated restaurants suitable for first-day visitors.{interest_context}

Return results as a JSON array of restaurant objects. Generate unique IDs using format "restaurant_{{destination_code}}_{{number}}"."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, RestaurantList)
            return result.restaurants
        except Exception as e:
            self.logger.error(f"LLM normalization failed: {e}", exc_info=True)
            return []
