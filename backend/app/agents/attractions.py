from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.agents.prompt import build_attractions_prompt
from app.schemas.spot_on import AttractionList


class AttractionsAgent(BaseAgent):
    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            qctx = state.get("query_context", {})
            settings = self.deps.settings

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
                    top_n=settings.search_top_n,
                    run_id=state.get("runId"),
                    label="attractions",
                    max_results_per_query=settings.tavily_max_results,
                    include_domains=["tripadvisor.com", "lonelyplanet.com", "timeout.com",
                                     "viator.com", "cntraveler.com", "atlasobscura.com"],
                ),
                timeout_seconds=settings.agent_search_timeout,
            )

            if top is None:
                return self._failed_result("Search timeout")
            if not top:
                return self._failed_result("No search results found")

            chunk_size = settings.normalize_chunk_size
            structured = await self._normalize_chunked(
                top,
                lambda chunk: self._normalize(chunk, qctx, run_id=state.get("runId")),
                chunk_size=chunk_size,
            )

            dest = qctx.get("destination_city", "").lower().replace(" ", "_").replace(",", "")
            for i, item in enumerate(structured, 1):
                item.id = f"attraction_{dest}_{i}"

            self.logger.info(
                "AttractionsAgent completed",
                extra={
                    "run_id": state.get("runId"),
                    "search_count": len(top),
                    "normalized_count": len(structured),
                },
            )

            return {
                "travel_spots": [a.model_dump() for a in structured],
                "agent_statuses": {self.agent_id: "completed"},
            }

        except Exception as e:
            self.logger.error(
                f"AttractionsAgent failed: {e}",
                exc_info=True,
                extra={"run_id": state.get("runId")},
            )
            return self._failed_result(str(e))

    async def _normalize(
        self, items: list[dict[str, Any]], qctx: dict[str, Any], *, run_id: str | None
    ) -> list:
        if not items:
            return []

        deduped = self._dedup_by_url_and_title(items)
        search_text = self._format_search_text(deduped, raw_content_limit=0)
        destination = qctx.get("destination_city")

        system_prompt = build_attractions_prompt(destination=destination, item_count=len(deduped))
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, AttractionList)
            self.logger.info(
                "%s normalize(attractions): deduped=%d llm_out=%d",
                self.agent_id,
                len(deduped),
                len(result.attractions),
                extra={"run_id": run_id},
            )
            return result.attractions
        except Exception as e:
            self.logger.error(f"Attractions normalization failed: {e}", exc_info=True)
            return []

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
