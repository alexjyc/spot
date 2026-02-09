"""Restaurant recommendation agent — search only."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent


class RestaurantAgent(BaseAgent):
    """Agent responsible for finding restaurant search results.

    Uses Tavily for web search. Returns raw deduplicated results
    sorted by relevance score. LLM normalization happens in WriterAgent.
    """

    TIMEOUT_SECONDS = 30
    TOP_N = 15

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            qctx = state.get("query_context", {})

            city = qctx.get("destination_city")
            current_year = qctx.get("depart_year", 2025)

            queries = self._build_queries(city, current_year)
            self.logger.info(
                f"RestaurantAgent searching with {len(queries)} queries",
                extra={"run_id": state.get("runId"), "destination": city},
            )

            search_results = await self.with_timeout(
                self._parallel_search(queries), 
                timeout_seconds=self.TIMEOUT_SECONDS
            )

            if search_results is None:
                return self._failed_result("Search timeout")

            all_items = self._flatten_search_results(search_results)
            if not all_items:
                return self._failed_result("No search results found")

            unique = self._dedup_by_url(all_items)
            top = self._top_by_score(unique, n=self.TOP_N)

            self.logger.info(
                "RestaurantAgent completed",
                extra={
                    "run_id": state.get("runId"),
                    "result_count": len(top),
                    "queries_used": len(queries),
                },
            )

            return {
                "raw_restaurants": top,
                "agent_statuses": {self.agent_id: "completed"},
            }

        except Exception as e:
            self.logger.error(
                f"RestaurantAgent failed: {e}",
                exc_info=True,
                extra={"run_id": state.get("runId")},
            )
            return self._failed_result(str(e))

    def _build_queries(self, city: str, current_year: int) -> list[str]:
        return [
            f"best restaurants in {city} {current_year}",
            f"top rated restaurants {city} local favorites where to eat",
            f"hidden gem restaurants {city} underrated dining",
        ]
