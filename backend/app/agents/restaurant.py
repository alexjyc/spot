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
    TOP_N = 10

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            qctx = state.get("query_context", {})

            city = qctx.get("destination_city")
            current_year = qctx.get("depart_year", 2025)

            primary, fallback = self._build_queries(city, current_year)
            self.logger.info(
                f"RestaurantAgent searching with {len(primary)} primary queries",
                extra={"run_id": state.get("runId"), "destination": city},
            )

            top = await self.with_timeout(
                self._search_with_fallback(
                    primary,
                    fallback,
                    top_n=self.TOP_N,
                    run_id=state.get("runId"),
                    label="restaurants",
                    include_domains=["yelp.com", "tripadvisor.com", "michelin.com",
                                     "eater.com", "infatuation.com", "timeout.com",
                                     "thefork.com"],
                ),
                timeout_seconds=self.TIMEOUT_SECONDS,
            )

            if top is None:
                return self._failed_result("Search timeout")
            if not top:
                return self._failed_result("No search results found")

            self.logger.info(
                "RestaurantAgent completed",
                extra={
                    "run_id": state.get("runId"),
                    "result_count": len(top),
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

    def _build_queries(self, city: str, current_year: int) -> tuple[list[str], list[str]]:
        primary = [
            f"best restaurants in {city} {current_year}",
            f"top rated restaurants {city} local favorites where to eat",
            f"Michelin Guide {city} restaurants Bib Gourmand",
        ]
        fallback = [
            f"hidden gem restaurants {city} underrated dining",
            f"{city} chef's tasting menu best restaurants",
        ]
        return primary, fallback
