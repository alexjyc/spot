"""Travel attractions recommendation agent — search only."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent


class AttractionsAgent(BaseAgent):
    """Agent responsible for finding travel spot search results.

    Uses Tavily for web search. Returns raw deduplicated results
    sorted by relevance score. LLM normalization happens in WriterAgent.
    """

    TIMEOUT_SECONDS = 30
    TOP_N = 20

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            qctx = state.get("query_context", {})

            city = qctx.get("destination_city")
            current_year = qctx.get("depart_year", 2026)

            primary, fallback = self._build_queries(city, current_year)
            self.logger.info(
                f"AttractionsAgent searching with {len(primary)} primary queries",
                extra={"run_id": state.get("runId"), "destination": city},
            )

            top = await self.with_timeout(
                self._search_with_fallback(
                    primary,
                    fallback,
                    top_n=self.TOP_N,
                    run_id=state.get("runId"),
                    label="attractions",
                    include_raw_content=True,
                ),
                timeout_seconds=self.TIMEOUT_SECONDS,
            )

            if top is None:
                return self._failed_result("Search timeout")
            if not top:
                return self._failed_result("No search results found")

            self.logger.info(
                "AttractionsAgent completed",
                extra={
                    "run_id": state.get("runId"),
                    "result_count": len(top),
                },
            )

            return {
                "raw_travel_spots": top,
                "agent_statuses": {self.agent_id: "completed"},
            }

        except Exception as e:
            self.logger.error(
                f"AttractionsAgent failed: {e}",
                exc_info=True,
                extra={"run_id": state.get("runId")},
            )
            return self._failed_result(str(e))

    def _build_queries(self, city: str, current_year: int) -> tuple[list[str], list[str]]:
        primary = [
            f"top attractions {city} must see {current_year}",
            f"{city} best things to do iconic landmarks sightseeing",
            f"{city} unique experiences hidden gems",
        ]
        fallback = [
            f"{city} markets historic districts walking areas",
            f"{city} free things to do self guided walking tour",
        ]
        return primary, fallback
