from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.agents.prompt import build_hotel_prompt
from app.schemas.spot_on import HotelList


class HotelAgent(BaseAgent):
    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            qctx = state.get("query_context", {})
            settings = self.deps.settings

            city = qctx.get("destination_city")
            current_year = qctx.get("depart_year", 2026)
            budget = qctx.get("budget")

            primary, fallback = self._build_queries(city, current_year, budget=budget)
            self.logger.info(
                f"HotelAgent searching with {len(primary)} primary queries",
                extra={"run_id": state.get("runId"), "destination": city},
            )

            top = await self.with_timeout(
                self._search_with_fallback(
                    primary,
                    fallback,
                    top_n=settings.search_top_n,
                    run_id=state.get("runId"),
                    label="hotels",
                    max_results_per_query=settings.tavily_max_results,
                    include_domains=["booking.com", "hotels.com", "tripadvisor.com",
                                     "trivago.com", "expedia.com", "agoda.com"],
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
                item.id = f"hotel_{dest}_{i}"

            self.logger.info(
                "HotelAgent completed",
                extra={
                    "run_id": state.get("runId"),
                    "search_count": len(top),
                    "normalized_count": len(structured),
                },
            )

            return {
                "hotels": [h.model_dump() for h in structured],
                "agent_statuses": {self.agent_id: "completed"},
            }

        except Exception as e:
            self.logger.error(
                f"HotelAgent failed: {e}",
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
        departing_date = qctx.get("departing_date", "")
        returning_date = qctx.get("returning_date")
        stay_nights = qctx.get("stay_nights")

        system_prompt = build_hotel_prompt(
            destination=destination,
            departing_date=departing_date,
            returning_date=returning_date,
            stay_nights=stay_nights,
            item_count=len(deduped)
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, HotelList)
            self.logger.info(
                "%s normalize(hotels): deduped=%d llm_out=%d",
                self.agent_id,
                len(deduped),
                len(result.hotels),
                extra={"run_id": run_id},
            )
            return result.hotels
        except Exception as e:
            self.logger.error(f"Hotel normalization failed: {e}", exc_info=True)
            return []

    def _build_queries(
        self, city: str, current_year: int, *, budget: str | None = None
    ) -> tuple[list[str], list[str]]:
        primary = [
            f"best hotels in {city} {current_year}",
            f"where to stay in {city} best neighborhoods for tourists",
        ]

        if budget == "Luxury":
            primary.append(f"luxury 5-star hotels {city} premium resorts")
        elif budget == "Budget-friendly":
            primary.append(f"budget hotels hostels {city} cheap stays")
        elif budget == "Mid-range":
            primary.append(f"boutique mid-range hotels {city} good value")
        else:
            primary.append(f"boutique hotels {city} unique stays")

        fallback = [
            f"top rated hotels in {city} city center walkable",
            f"best hotels in {city} downtown",
        ]
        return primary, fallback
