from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.agents.prompt import build_restaurant_prompt
from app.schemas.spot_on import RestaurantList


class RestaurantAgent(BaseAgent):
    """Agent responsible for finding and normalizing restaurant results.

    Searches via Tavily, then normalizes raw results into structured output
    using an LLM call — all inline to avoid burst normalization.
    """

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            qctx = state.get("query_context", {})
            settings = self.deps.settings

            city = qctx.get("destination_city")
            current_year = qctx.get("depart_year", 2025)
            vibe = qctx.get("vibe")
            budget = qctx.get("budget")

            primary, fallback = self._build_queries(city, current_year, vibe=vibe, budget=budget)
            self.logger.info(
                f"RestaurantAgent searching with {len(primary)} primary queries",
                extra={"run_id": state.get("runId"), "destination": city},
            )

            top = await self.with_timeout(
                self._search_with_fallback(
                    primary,
                    fallback,
                    top_n=settings.search_top_n,
                    run_id=state.get("runId"),
                    label="restaurants",
                    max_results_per_query=settings.tavily_max_results,
                    include_domains=["yelp.com", "tripadvisor.com", "michelin.com",
                                     "eater.com", "infatuation.com", "timeout.com",
                                     "thefork.com"],
                ),
                timeout_seconds=settings.agent_search_timeout,
            )

            if top is None:
                return self._failed_result("Search timeout")
            if not top:
                return self._failed_result("No search results found")

            # Normalize inline (chunked for large result sets)
            chunk_size = settings.normalize_chunk_size
            structured = await self._normalize_chunked(
                top,
                lambda chunk: self._normalize(chunk, qctx, run_id=state.get("runId")),
                chunk_size=chunk_size,
            )

            # Reindex IDs to avoid collisions across chunks
            dest = qctx.get("destination_city", "").lower().replace(" ", "_").replace(",", "")
            for i, item in enumerate(structured, 1):
                item.id = f"restaurant_{dest}_{i}"

            self.logger.info(
                "RestaurantAgent completed",
                extra={
                    "run_id": state.get("runId"),
                    "search_count": len(top),
                    "normalized_count": len(structured),
                },
            )

            return {
                "restaurants": [r.model_dump() for r in structured],
                "agent_statuses": {self.agent_id: "completed"},
            }

        except Exception as e:
            self.logger.error(
                f"RestaurantAgent failed: {e}",
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

        system_prompt = build_restaurant_prompt(destination=destination, item_count=len(deduped))
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, RestaurantList)
            self.logger.info(
                "%s normalize(restaurants): deduped=%d llm_out=%d",
                self.agent_id,
                len(deduped),
                len(result.restaurants),
                extra={"run_id": run_id},
            )
            return result.restaurants
        except Exception as e:
            self.logger.error(f"Restaurant normalization failed: {e}", exc_info=True)
            return []

    def _build_queries(
        self, city: str, current_year: int, *, vibe: str | None = None, budget: str | None = None
    ) -> tuple[list[str], list[str]]:
        primary = [
            f"best restaurants in {city} {current_year}",
            f"top rated restaurants {city} local favorites where to eat",
            f"Michelin Guide {city} restaurants Bib Gourmand",
        ]

        if budget == "Luxury":
            primary.append(f"fine dining {city} upscale tasting menu")
        elif budget == "Budget-friendly":
            primary.append(f"cheap eats {city} street food affordable")
        elif budget == "Mid-range":
            primary.append(f"best value restaurants {city} local dining")

        if vibe == "Food & Nightlife":
            primary.append(f"food scene {city} must try nightlife")

        fallback = [
            f"hidden gem restaurants {city} underrated dining",
            f"{city} chef's tasting menu best restaurants",
        ]
        return primary, fallback
