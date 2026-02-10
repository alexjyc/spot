"""Enrichment agent for extracting detailed information from webpages."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.agents.prompt import build_enrichment_prompt
from app.schemas.spot_on import EnrichedDetails
from app.utils.dedup import canonicalize_url


class EnrichmentAgent(BaseAgent):
    """Agent responsible for enriching results with detailed info.

    Extracts prices, hours, addresses, phone numbers, etc. from webpage content.
    Uses Tavily extract API + LLM parsing.
    Executes sequentially after all domain agents complete.
    """

    TIMEOUT_SECONDS = 45
    MAX_URLS_PER_BATCH = 20
    TAVILY_CALL_CAP = 20
    RESOLVE_ITEMS_CAP = 6  # Phase 1: 0-1 calls. Phase 2: up to 6*(2 search + 1 map) + 1 extract = 19.
    PHASE1_CAP = 4         # Max items to LLM-parse in Phase 1 (1 parallel batch)
    PHASE1_BATCH = 6       # Process all Phase 1 items in a single parallel batch

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute enrichment workflow.

        Args:
            state: Graph state with domain agent results

        Returns:
            Partial state update with enriched_data dict
        """
        # Short-circuit if enrichment is disabled
        if state.get("skip_enrichment"):
            self.logger.info(
                "EnrichmentAgent: skipped (skip_enrichment=True)",
                extra={"run_id": state.get("runId")},
            )
            return {
                "enriched_data": {},
                "agent_statuses": {self.agent_id: "skipped"},
                "warnings": [],
            }

        try:
            # Collect all URLs from domain agent results
            items = self._collect_items(state)

            if not items:
                self.logger.info(
                    "EnrichmentAgent: No items to enrich",
                    extra={"run_id": state.get("runId")},
                )
                return {
                    "agent_statuses": {self.agent_id: "skipped"},
                }

            self.logger.info(
                f"EnrichmentAgent processing {len(items)} items",
                extra={"run_id": state.get("runId")},
            )

            # Limit to avoid overwhelming extract API
            items_to_process = items[: self.MAX_URLS_PER_BATCH]

            # Extract content with timeout
            enriched = await self.with_timeout(
                self._extract_and_parse(items_to_process, state=state),
                timeout_seconds=self.TIMEOUT_SECONDS,
            )

            if enriched is None:
                self.logger.warning("EnrichmentAgent timed out")
                return {
                    "enriched_data": {},
                    "agent_statuses": {self.agent_id: "failed"},
                    "warnings": ["Enrichment timed out"],
                }

            self.logger.info(
                f"EnrichmentAgent completed",
                extra={
                    "run_id": state.get("runId"),
                    "enriched_count": len(enriched),
                    "total_items": len(items),
                },
            )

            status = "completed" if len(enriched) > 0 else "partial"
            warnings = []
            if len(enriched) < len(items_to_process) * 0.5:
                warnings.append(
                    f"Only enriched {len(enriched)}/{len(items_to_process)} items"
                )
                status = "partial"

            result = {
                "enriched_data": enriched,
                "agent_statuses": {self.agent_id: status},
            }

            if warnings:
                result["warnings"] = warnings

            return result

        except Exception as e:
            self.logger.error(
                f"EnrichmentAgent failed: {e}",
                exc_info=True,
                extra={"run_id": state.get("runId")},
            )
            return self._failed_result(str(e))

    def _collect_items(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """Collect all items with URLs from domain agent results.

        Args:
            state: Graph state

        Returns:
            List of items with id, url, and type
        """
        items = []
        qctx = state.get("query_context", {}) if isinstance(state, dict) else {}
        city = qctx.get("destination_city")

        # Restaurants
        for r in state.get("restaurants", []):
            if r.get("url"):
                items.append(
                    {
                        "id": r["id"],
                        "name": r.get("name"),
                        "city": city,
                        "url": r["url"],
                        "type": "restaurant",
                    }
                )

        # Travel spots
        for t in state.get("travel_spots", []):
            if t.get("url"):
                items.append(
                    {
                        "id": t["id"],
                        "name": t.get("name"),
                        "city": city,
                        "url": t["url"],
                        "type": "attraction",
                    }
                )

        # Hotels
        for h in state.get("hotels", []):
            if h.get("url"):
                items.append(
                    {
                        "id": h["id"],
                        "name": h.get("name"),
                        "city": city,
                        "url": h["url"],
                        "type": "hotel",
                    }
                )

        # Car rentals
        for c in state.get("car_rentals", []):
            if c.get("url"):
                items.append(
                    {
                        "id": c["id"],
                        "name": c.get("provider"),
                        "city": city,
                        "url": c["url"],
                        "type": "car_rental",
                    }
                )

        # Flights
        for f in state.get("flights", []):
            if f.get("url"):
                items.append(
                    {
                        "id": f["id"],
                        "name": f.get("airline") or f.get("route"),
                        "city": city,
                        "url": f["url"],
                        "type": "flight",
                    }
                )

        return items

    async def _extract_and_parse(
        self, items: list[dict[str, Any]], *, state: dict[str, Any]
    ) -> dict[str, dict[str, Any]]:
        """Extract webpage content and parse with LLM.

        Args:
            items: List of items to enrich

        Returns:
            Dictionary mapping item_id to enriched details
        """
        tavily_calls = 0

        def _take_call() -> bool:
            nonlocal tavily_calls
            if tavily_calls >= self.TAVILY_CALL_CAP:
                return False
            tavily_calls += 1
            return True

        urls = [item["url"] for item in items if item.get("url")]
        if not urls:
            return {}

        # Phase 1: Use raw_content from state instead of calling tavily.extract()
        rc_map = self._build_raw_content_map(state)
        self.logger.info(
            "EnrichmentAgent Phase 1: %d raw_content entries from state for %d items",
            len(rc_map), len(items),
        )

        enriched: dict[str, dict[str, Any]] = {}

        # Build synthetic page dicts from raw_content for each item (canonicalized match)
        valid_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
        unmatched_items: list[dict[str, Any]] = []
        for item in items:
            url = item.get("url", "")
            rc = rc_map.get(canonicalize_url(url), "")
            if rc:
                valid_pairs.append(({"url": url, "raw_content": rc}, item))
            else:
                unmatched_items.append(item)

        # Extract fallback: fetch raw_content for unmatched items via Tavily extract
        remaining_cap = self.PHASE1_CAP - len(valid_pairs)
        if unmatched_items and remaining_cap > 0 and _take_call():
            fallback_items = unmatched_items[:remaining_cap]
            fallback_urls = [it["url"] for it in fallback_items if it.get("url")]
            if fallback_urls:
                try:
                    extract_resp = await self.deps.tavily.extract(fallback_urls)
                    pages = extract_resp.get("results", []) if isinstance(extract_resp, dict) else []
                    page_by_url = {canonicalize_url(p.get("url", "")): p for p in pages if p.get("raw_content")}
                    for it in fallback_items:
                        page = page_by_url.get(canonicalize_url(it["url"]))
                        if page:
                            valid_pairs.append((page, it))
                except Exception as e:
                    self.logger.warning("Tavily extract fallback failed: %s", e)

        # Cap Phase 1 to PHASE1_CAP items and process in a single batch
        valid_pairs = valid_pairs[: self.PHASE1_CAP]

        if valid_pairs:
            tasks = [
                self._parse_page_with_llm(page, item) for page, item in valid_pairs
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for (page, item), result in zip(valid_pairs, batch_results):
                if isinstance(result, Exception):
                    self.logger.warning(f"Failed to parse {item['url']}: {result}")
                    continue
                if result:
                    enriched[item["id"]] = result

        # Phase 2: canonical resolution for deep fields on a few items.
        # Keep this small and deterministic to maximize ROI and avoid runaway calls.
        resolve_candidates = self._pick_resolve_candidates(items, enriched=enriched)
        resolve_candidates = resolve_candidates[: self.RESOLVE_ITEMS_CAP]

        # Reserve 1 call for phase-2 extract if we plan to do any resolution.
        if resolve_candidates and tavily_calls < self.TAVILY_CALL_CAP:
            # If we can't afford at least one search+map for any item plus one extract,
            # skip the entire phase.
            remaining = self.TAVILY_CALL_CAP - tavily_calls
            if remaining < 4:
                return enriched

        resolved_targets: dict[str, dict[str, Any]] = {}
        urls_to_extract: list[str] = []
        url_to_item: dict[str, dict[str, Any]] = {}

        for item in resolve_candidates:
            if self.TAVILY_CALL_CAP - tavily_calls < 4:
                break

            item_id = item["id"]
            item_type = item["type"]
            name = (item.get("name") or "").strip()
            city = (item.get("city") or "").strip()
            if item_type not in {"restaurant", "attraction", "hotel"}:
                continue
            if not name:
                continue

            canonical_url, provider_url = await self._resolve_canonical_urls(
                item_type=item_type,
                name=name,
                city=city,
                take_call=_take_call,
            )

            if provider_url:
                resolved_targets.setdefault(item_id, {})["reservation_url"] = provider_url

            if not canonical_url:
                continue

            mapped = await self._map_subpages(
                item_type=item_type,
                canonical_url=canonical_url,
                take_call=_take_call,
            )

            resolved_targets.setdefault(item_id, {}).update(mapped.get("fields", {}))
            for u in mapped.get("extract_urls", []):
                if u not in url_to_item:
                    url_to_item[u] = {"id": item_id, "type": item_type, "url": u}
                    urls_to_extract.append(u)

        # Batch extract all discovered subpages (up to 20 URLs per Tavily docs).
        if urls_to_extract and _take_call():
            urls_to_extract = urls_to_extract[:20]
            try:
                extract2 = await self.deps.tavily.extract(urls_to_extract)
            except Exception as e:
                self.logger.error("Tavily extract (phase2) failed: %s", e, exc_info=True)
                extract2 = {}

            pages2 = extract2.get("results", []) if isinstance(extract2, dict) else []
            tasks = []
            pairs = []
            for page in pages2:
                u = page.get("url")
                it = url_to_item.get(u)
                if not it:
                    continue
                pairs.append((page, it))
                tasks.append(self._parse_page_with_llm(page, it))
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for (page, it), r in zip(pairs, results):
                if isinstance(r, Exception) or not r:
                    continue
                enriched.setdefault(it["id"], {}).update(
                    {k: v for k, v in r.items() if v not in (None, "", [], {})}
                )

        # Merge any resolved URL fields (menu/reservation) even if extraction didn't parse.
        for item_id, fields in resolved_targets.items():
            if not fields:
                continue
            e = enriched.setdefault(item_id, {})
            for k, v in fields.items():
                if k not in e or e[k] in (None, "", [], {}):
                    e[k] = v

        return enriched

    @staticmethod
    def _build_raw_content_map(state: dict[str, Any]) -> dict[str, str]:
        """Build canonicalized-URL -> raw_content lookup from raw search results in state."""
        rc_map: dict[str, str] = {}
        for key in ("raw_restaurants", "raw_travel_spots", "raw_hotels", "raw_car_rentals", "raw_flights"):
            for item in state.get(key, []):
                url = item.get("url", "")
                rc = item.get("raw_content", "")
                if url and rc:
                    rc_map[canonicalize_url(url)] = rc
        return rc_map

    _LOW_QUALITY_RE = re.compile(
        r"(?:^|/)(?:best|top|guide|things-to-do|things_to_do|blog|list)(?:$|[/?#_-])",
        re.IGNORECASE,
    )

    @classmethod
    def _is_low_quality_url(cls, url: str) -> bool:
        if not url:
            return True
        u = url.lower()
        if "?" in u:
            u = u.split("?", 1)[0]
        return bool(cls._LOW_QUALITY_RE.search(u))

    def _pick_resolve_candidates(
        self, items: list[dict[str, Any]], *, enriched: dict[str, dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Pick a small set of items that benefit most from canonical resolution."""
        buckets: dict[str, list[dict[str, Any]]] = {"restaurant": [], "attraction": [], "hotel": []}

        for it in items:
            t = it.get("type")
            if t not in buckets:
                continue
            it_id = it.get("id")
            if not it_id:
                continue

            e = enriched.get(it_id, {})
            needs = False
            if t == "restaurant":
                needs = not e.get("menu_url") or not e.get("reservation_url")
            elif t == "attraction":
                needs = not e.get("admission_price")
            elif t == "hotel":
                needs = not e.get("parking_details")

            if needs or self._is_low_quality_url(it.get("url", "")):
                buckets[t].append(it)

        picked: list[dict[str, Any]] = []
        for t in ("restaurant", "attraction", "hotel"):
            picked.extend(buckets[t][:2])
        return picked

    async def _resolve_canonical_urls(
        self,
        *,
        item_type: str,
        name: str,
        city: str,
        take_call: Any,
    ) -> tuple[str | None, str | None]:
        """Return (canonical_url, provider_url). Provider URL is only used for restaurant reservations."""
        provider_url = None

        def _pick_best(results: list[dict[str, Any]]) -> str | None:
            for r in results:
                url = (r.get("url") or "").strip()
                if not url:
                    continue
                if self._is_low_quality_url(url):
                    continue
                return url
            return None

        city_part = f" {city}" if city else ""

        if item_type == "restaurant":
            if not take_call():
                return None, None
            r1 = await self.deps.tavily.search(
                f"{name}{city_part} official site",
                max_results=3,
                include_raw_content=True,
            )
            canon = _pick_best(r1.get("results", []) if isinstance(r1, dict) else [])

            if not take_call():
                return canon, None
            r2 = await self.deps.tavily.search(
                f"{name}{city_part} reservations",
                max_results=3,
                include_domains=["opentable.com", "resy.com", "tockhq.com"],
            )
            res2 = r2.get("results", []) if isinstance(r2, dict) else []
            provider_url = _pick_best(res2) or provider_url
            return canon, provider_url

        if item_type == "attraction":
            if not take_call():
                return None, None
            r = await self.deps.tavily.search(
                f"{name}{city_part} official tickets price",
                max_results=3,
                include_raw_content=True,
            )
            return _pick_best(r.get("results", []) if isinstance(r, dict) else []), None

        if item_type == "hotel":
            if not take_call():
                return None, None
            r = await self.deps.tavily.search(
                f"{name}{city_part} official site parking",
                max_results=3,
                include_raw_content=True,
            )
            return _pick_best(r.get("results", []) if isinstance(r, dict) else []), None

        return None, None

    async def _map_subpages(
        self,
        *,
        item_type: str,
        canonical_url: str,
        take_call: Any,
    ) -> dict[str, Any]:
        if not take_call():
            return {"fields": {}, "extract_urls": []}

        instructions = {
            "restaurant": "Find menu and reservation/booking pages",
            "attraction": "Find ticket/admission price pages",
            "hotel": "Find parking policy/info pages",
        }.get(item_type, None)

        try:
            resp = await self.deps.tavily.map(
                canonical_url, max_depth=2, limit=30, instructions=instructions, allow_external=False
            )
        except Exception:
            return {"fields": {}, "extract_urls": []}

        results = resp.get("results", []) if isinstance(resp, dict) else []
        urls = [(r.get("url") or "") for r in results if isinstance(r, dict)]
        urls = [u for u in urls if u]

        def _pick_by_keywords(keywords: list[str]) -> str | None:
            for u in urls:
                lu = u.lower()
                if any(k in lu for k in keywords):
                    return u
            return None

        fields: dict[str, Any] = {}
        extract_urls: list[str] = []

        if item_type == "restaurant":
            menu = _pick_by_keywords(["/menu", "menu"])
            reserve = _pick_by_keywords(["reserve", "reservation", "book", "booking"])
            if menu:
                fields["menu_url"] = menu
                extract_urls.append(menu)
            if reserve:
                fields["reservation_url"] = reserve
                extract_urls.append(reserve)
            if not extract_urls:
                extract_urls.append(canonical_url)

        elif item_type == "attraction":
            ticket = _pick_by_keywords(["ticket", "admission", "price", "pricing"])
            if ticket:
                extract_urls.append(ticket)
            else:
                extract_urls.append(canonical_url)

        elif item_type == "hotel":
            parking = _pick_by_keywords(["parking", "amenities", "policy"])
            if parking:
                extract_urls.append(parking)
            else:
                extract_urls.append(canonical_url)

        return {"fields": fields, "extract_urls": extract_urls[:2]}

    async def _parse_page_with_llm(
        self, page: dict[str, Any], item: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Parse a single webpage with LLM.

        Args:
            page: Tavily extract result for one page
            item: Item metadata (id, url, type)

        Returns:
            Dictionary with enriched details, or None if parsing failed
        """
        content = page.get("raw_content", "")
        if not content:
            return None

        content = content[:5000]

        item_type = item["type"]

        system_prompt = build_enrichment_prompt(item_type=item_type)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Webpage content:\n\n{content}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, EnrichedDetails)
            return result.model_dump()
        except Exception as e:
            self.logger.debug(f"LLM parsing failed for {item['url']}: {e}")
            return None
