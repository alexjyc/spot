"""Enrichment agent for extracting detailed information from webpages."""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.schemas.spot_on import EnrichedDetails


class EnrichmentAgent(BaseAgent):
    """Agent responsible for enriching results with detailed info.

    Extracts prices, hours, addresses, phone numbers, etc. from webpage content.
    Uses Tavily extract API + LLM parsing.
    Executes sequentially after all domain agents complete.
    """

    TIMEOUT_SECONDS = 45
    MAX_URLS_PER_BATCH = 5

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
                self._extract_and_parse(items_to_process),
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

        # Restaurants
        for r in state.get("restaurants", []):
            if r.get("url"):
                items.append(
                    {"id": r["id"], "url": r["url"], "type": "restaurant"}
                )

        # Travel spots
        for t in state.get("travel_spots", []):
            if t.get("url"):
                items.append(
                    {"id": t["id"], "url": t["url"], "type": "attraction"}
                )

        # Hotels
        for h in state.get("hotels", []):
            if h.get("url"):
                items.append({"id": h["id"], "url": h["url"], "type": "hotel"})

        # Car rentals
        for c in state.get("car_rentals", []):
            if c.get("url"):
                items.append(
                    {"id": c["id"], "url": c["url"], "type": "car_rental"}
                )

        # Flights
        for f in state.get("flights", []):
            if f.get("url"):
                items.append({"id": f["id"], "url": f["url"], "type": "flight"})

        return items

    async def _extract_and_parse(
        self, items: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Extract webpage content and parse with LLM.

        Args:
            items: List of items to enrich

        Returns:
            Dictionary mapping item_id to enriched details
        """
        # Extract content from all URLs
        urls = [item["url"] for item in items]

        try:
            extract_result = await self.deps.tavily.extract(urls)
        except Exception as e:
            self.logger.error(f"Tavily extract failed: {e}", exc_info=True)
            return {}

        # Parse each page result with LLM
        enriched = {}
        pages = extract_result.get("results", [])

        # Process pages in parallel (with small batches to avoid rate limits)
        batch_size = 5
        for i in range(0, len(pages), batch_size):
            batch_pages = pages[i : i + batch_size]
            batch_items = [
                next((item for item in items if item["url"] == page["url"]), None)
                for page in batch_pages
            ]

            # Filter out None items
            valid_pairs = [
                (page, item)
                for page, item in zip(batch_pages, batch_items)
                if item is not None
            ]

            if not valid_pairs:
                continue

            # Parse batch in parallel
            tasks = [
                self._parse_page_with_llm(page, item)
                for page, item in valid_pairs
            ]

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect results
            for (page, item), result in zip(valid_pairs, batch_results):
                if isinstance(result, Exception):
                    self.logger.warning(
                        f"Failed to parse {item['url']}: {result}"
                    )
                    continue

                if result:
                    enriched[item["id"]] = result

        return enriched

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

        # Limit content size to avoid huge LLM prompts
        content = content[:5000]

        item_type = item["type"]
        type_hints = {
            "restaurant": "Look for: price range, hours, phone, address, reservation info",
            "attraction": "Look for: hours, price/admission, address, phone",
            "hotel": "Look for: nightly rate, address, phone, amenities",
            "car_rental": "Look for: daily rate, address, phone, pickup info",
            "flight": "Look for: flight times, price, booking info",
        }

        hint = type_hints.get(item_type, "Look for: price, hours, address, phone")

        system_prompt = f"""You are an information extraction expert. Extract structured details from the webpage content.

Item type: {item_type}
{hint}

Extract the following fields (set to null if not found):
- price_hint: Any price information found
- hours_text: Opening/operating hours
- address: Full address
- phone: Phone number
- reservation_required: true/false if mentioned, null otherwise

Be precise. Only extract information that is clearly stated. Don't make assumptions."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Webpage content:\n\n{content}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, EnrichedDetails)
            return result.model_dump()
        except Exception as e:
            self.logger.debug(
                f"LLM parsing failed for {item['url']}: {e}"
            )
            return None
