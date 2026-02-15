import asyncio
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.agents.prompt import build_enrichment_prompt, build_enrichment_query_prompt
from app.schemas.spot_on import (
    AttractionEnrichment,
    CarRentalEnrichment,
    EnrichmentQueryList,
    FlightEnrichment,
    HotelEnrichment,
    RestaurantEnrichment,
)
from app.utils.dedup import canonicalize_url

logger = logging.getLogger(__name__)

ENRICHABLE_FIELDS: dict[str, list[str]] = {
    "restaurant": ["operating_hours", "menu_url", "reservation_url", "price_range", "cuisine", "rating"],
    "attraction": ["operating_hours", "admission_price", "reservation_url", "kind"],
    "hotel": ["price_per_night", "amenities"],
    "car_rental": ["price_per_day", "vehicle_class", "operating_hours"],
    "flight": ["price_range", "airline"],
}

STATE_KEYS: dict[str, str] = {
    "restaurant": "restaurants",
    "attraction": "travel_spots",
    "hotel": "hotels",
    "car_rental": "car_rentals",
    "flight": "flights",
}

ENRICHMENT_SCHEMAS: dict[str, type] = {
    "restaurant": RestaurantEnrichment,
    "attraction": AttractionEnrichment,
    "hotel": HotelEnrichment,
    "car_rental": CarRentalEnrichment,
    "flight": FlightEnrichment,
}

DOMAIN_FILTER: dict[str, dict[str, list[str]]] = {
    "restaurant": {
        "include": ["opentable.com", "resy.com", "yelp.com", "tripadvisor.com"],
    },
    "attraction": {
        "include": ["tripadvisor.com", "viator.com", "getyourguide.com"],
    },
    "hotel": {
        "include": ["booking.com", "hotels.com", "expedia.com"],
    },
    "car_rental": {
        "include": ["kayak.com", "rentalcars.com"],
    },
    "flight": {
        "include": ["kayak.com", "skyscanner.com", "google.com"],
    },
}

class EnrichmentAgent(BaseAgent):
    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            timeout = self.deps.settings.agent_enrich_timeout
            loop_count = state.get("enrichment_loop_count", 0)
            # Shared mutable dict — _run() writes here incrementally
            self._partial: dict[str, dict[str, Any]] = {
                k: dict(v) for k, v in state.get("enriched_data", {}).items()
            }
            result = await self.with_timeout(
                self._run(state), timeout_seconds=timeout
            )
            if result is not None:
                return result
            # Timeout — return whatever we collected
            filled = sum(1 for v in self._partial.values() if v)
            self.logger.info("EnrichAgent timed out with %d partial items saved", filled)
            return {
                "enriched_data": self._partial,
                "enrichment_gap_ratio": 0.6,
                "enrichment_loop_count": loop_count + 1,
                "agent_statuses": {self.agent_id: "partial"},
                "warnings": [f"Enrichment timed out ({filled} items partially enriched)"],
            }
        except Exception as e:
            self.logger.error("EnrichAgent failed: %s", e, exc_info=True)
            return self._failed_result(str(e))

    async def _run(self, state: dict[str, Any]) -> dict[str, Any]:
        tavily_call_cap = self.deps.settings.tavily_call_cap
        tavily_calls = 0
        loop_count = state.get("enrichment_loop_count", 0)

        enriched = self._partial
        total_enrichable = self._count_total_enrichable_fields(state)
        max_items = self.deps.settings.enrich_max_items_per_pass

        gaps = self._scan_missing_fields(state, enriched)
        # Prioritize: fewer missing fields = faster to complete = more items enriched
        gaps.sort(key=lambda g: len(g["missing_fields"]))
        if len(gaps) > max_items:
            gaps = gaps[:max_items]

        if not gaps:
            self.logger.info("EnrichAgent: nothing to enrich")
            return {
                "enriched_data": enriched,
                "enrichment_gap_ratio": 0.0,
                "enrichment_loop_count": loop_count + 1,
                "agent_statuses": {self.agent_id: "skipped"},
            }

        self.logger.info(
            "EnrichAgent: %d items need enrichment (loop %d)",
            len(gaps),
            loop_count,
            extra={"run_id": state.get("runId")},
        )

        extract_urls = [g["url"] for g in gaps if g.get("url")]
        seen_urls: set[str] = set()
        unique_urls: list[str] = []
        for u in extract_urls:
            cu = canonicalize_url(u)
            if cu not in seen_urls:
                seen_urls.add(cu)
                unique_urls.append(u)

        url_to_gaps: dict[str, list[dict[str, Any]]] = {}
        for g in gaps:
            cu = canonicalize_url(g.get("url", ""))
            url_to_gaps.setdefault(cu, []).append(g)

        if unique_urls and tavily_calls < tavily_call_cap:
            for batch_start in range(0, len(unique_urls), 20):
                if tavily_calls >= tavily_call_cap:
                    break
                batch = unique_urls[batch_start : batch_start + 20]
                tavily_calls += 1
                try:
                    extract_resp = await self.deps.tavily.extract(batch)
                    pages = (
                        extract_resp.get("results", [])
                        if isinstance(extract_resp, dict)
                        else []
                    )
                    parse_tasks = []
                    parse_meta = []
                    for page in pages:
                        page_url = canonicalize_url(page.get("url", ""))
                        matching_gaps = url_to_gaps.get(page_url, [])
                        for gap in matching_gaps:
                            parse_tasks.append(
                                self._fill_from_content(
                                    page.get("raw_content", ""),
                                    gap["type"],
                                    gap["missing_fields"],
                                )
                            )
                            parse_meta.append(gap)

                    if parse_tasks:
                        results = await asyncio.gather(
                            *parse_tasks, return_exceptions=True
                        )
                        for gap, result in zip(parse_meta, results):
                            if isinstance(result, Exception) or not result:
                                continue
                            enriched.setdefault(gap["id"], {}).update(
                                {k: v for k, v in result.items() if v not in (None, "", [], {})}
                            )
                except Exception as e:
                    self.logger.warning("EnrichAgent extract P1 failed: %s", e)

        remaining_gaps = self._rescan_after_enrichment(gaps, enriched)

        if remaining_gaps and tavily_calls < tavily_call_cap:
            queries = await self._generate_queries(remaining_gaps)

            if queries:
                gap_by_id = {g["id"]: g for g in remaining_gaps}
                search_tasks = []
                search_meta = []
                discovered_urls: list[str] = []
                discovered_url_meta: dict[str, dict[str, Any]] = {}

                for eq in queries:
                    if tavily_calls >= tavily_call_cap:
                        break
                    target = gap_by_id.get(eq.item_id)
                    if not target:
                        continue

                    domain_conf = DOMAIN_FILTER.get(target["type"], {})
                    include_domains = domain_conf.get("include")

                    tavily_calls += 1
                    search_tasks.append(
                        self.deps.tavily.search(
                            eq.query,
                            include_domains=include_domains,
                        )
                    )
                    search_meta.append(target)

                if search_tasks:
                    search_results = await asyncio.gather(
                        *search_tasks, return_exceptions=True
                    )
                    for target, result in zip(search_meta, search_results):
                        if isinstance(result, Exception):
                            continue
                        results_list = (
                            result.get("results", [])
                            if isinstance(result, dict)
                            else []
                        )
                        for r in results_list:
                            url = r.get("url", "")
                            if url and canonicalize_url(url) not in seen_urls:
                                seen_urls.add(canonicalize_url(url))
                                discovered_urls.append(url)
                                discovered_url_meta[canonicalize_url(url)] = target

                if discovered_urls and tavily_calls < tavily_call_cap:
                    tavily_calls += 1
                    try:
                        extract2 = await self.deps.tavily.extract(
                            discovered_urls[:20]
                        )
                        pages2 = (
                            extract2.get("results", [])
                            if isinstance(extract2, dict)
                            else []
                        )
                        parse_tasks = []
                        parse_meta = []
                        for page in pages2:
                            page_url = canonicalize_url(page.get("url", ""))
                            target = discovered_url_meta.get(page_url)
                            if not target:
                                continue
                            parse_tasks.append(
                                self._fill_from_content(
                                    page.get("raw_content", ""),
                                    target["type"],
                                    target["missing_fields"],
                                )
                            )
                            parse_meta.append(target)

                        if parse_tasks:
                            results = await asyncio.gather(
                                *parse_tasks, return_exceptions=True
                            )
                            for target, result in zip(parse_meta, results):
                                if isinstance(result, Exception) or not result:
                                    continue
                                e = enriched.setdefault(target["id"], {})
                                for k, v in result.items():
                                    if v not in (None, "", [], {}) and k not in e:
                                        e[k] = v
                    except Exception as e:
                        self.logger.warning("EnrichAgent extract P2 failed: %s", e)

        all_gaps = self._scan_missing_fields(state, enriched)
        total_missing = sum(len(g["missing_fields"]) for g in all_gaps)
        gap_ratio = total_missing / total_enrichable if total_enrichable > 0 else 0.0

        self.logger.info(
            "EnrichAgent completed: enriched %d items, %d Tavily calls, gap_ratio=%.2f, loop=%d",
            len(enriched),
            tavily_calls,
            gap_ratio,
            loop_count,
            extra={"run_id": state.get("runId")},
        )

        status = "completed" if enriched else "partial"
        return {
            "enriched_data": enriched,
            "enrichment_gap_ratio": gap_ratio,
            "enrichment_loop_count": loop_count + 1,
            "agent_statuses": {self.agent_id: status},
        }

    @staticmethod
    def _scan_missing_fields(
        state: dict[str, Any],
        enriched: dict[str, dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Scan output for items with null enrichable fields, accounting for already-enriched data."""
        qctx = state.get("query_context", {}) if isinstance(state, dict) else {}
        city = qctx.get("destination_city", "")
        enriched = enriched or {}
        gaps: list[dict[str, Any]] = []

        for item_type, state_key in STATE_KEYS.items():
            enrichable = ENRICHABLE_FIELDS.get(item_type, [])
            if not enrichable:
                continue
            for item in state.get(state_key, []):
                item_id = item.get("id", "")
                already_filled = enriched.get(item_id, {})
                missing = [
                    f
                    for f in enrichable
                    if item.get(f) in (None, "", [], {}) and f not in already_filled
                ]
                if missing:
                    gaps.append(
                        {
                            "id": item_id,
                            "type": item_type,
                            "url": item.get("url", ""),
                            "name": item.get("name", item.get("provider", "")),
                            "city": city,
                            "missing_fields": missing,
                        }
                    )
        return gaps

    @staticmethod
    def _count_total_enrichable_fields(state: dict[str, Any]) -> int:
        """Count total number of enrichable fields across all items."""
        total = 0
        for item_type, state_key in STATE_KEYS.items():
            enrichable = ENRICHABLE_FIELDS.get(item_type, [])
            items = state.get(state_key, [])
            total += len(enrichable) * len(items)
        return total

    @staticmethod
    def _rescan_after_enrichment(
        original_gaps: list[dict[str, Any]],
        enriched: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Re-check which fields are still missing after enrichment."""
        remaining: list[dict[str, Any]] = []
        for gap in original_gaps:
            filled = enriched.get(gap["id"], {})
            still_missing = [
                f for f in gap["missing_fields"] if f not in filled
            ]
            if still_missing:
                remaining.append({**gap, "missing_fields": still_missing})
        return remaining

    async def _generate_queries(
        self, gaps: list[dict[str, Any]]
    ) -> list[Any]:
        """Use LLM to generate targeted search queries for remaining gaps."""
        gap_descriptions = []
        for g in gaps:
            gap_descriptions.append(
                f"- Item ID: {g['id']}, Name: {g['name']}, Type: {g['type']}, "
                f"City: {g['city']}, Missing: {', '.join(g['missing_fields'])}"
            )

        system_prompt = build_enrichment_query_prompt()
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Items needing enrichment:\n\n" + "\n".join(gap_descriptions)),
        ]

        try:
            result = await self.deps.llm.structured(messages, EnrichmentQueryList)
            return result.queries
        except Exception as e:
            self.logger.warning("LLM query generation failed: %s", e)
            return []

    async def _fill_from_content(
        self,
        content: str,
        item_type: str,
        missing_fields: list[str],
    ) -> dict[str, Any] | None:
        """Parse page content with LLM to extract missing fields."""
        if not content:
            return None

        content = content[:5000]
        schema = ENRICHMENT_SCHEMAS.get(item_type)
        if not schema:
            return None

        system_prompt = build_enrichment_prompt(
            item_type=item_type, missing_fields=missing_fields
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Webpage content:\n\n{content}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, schema)
            return result.model_dump()
        except Exception as e:
            self.logger.debug("LLM parsing failed: %s", e)
            return None
