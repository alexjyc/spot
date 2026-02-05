"""Hotel recommendation agent."""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.schemas.spot_on import HotelOutput, HotelList
from app.utils.dedup import canonicalize_url, normalize_name


class HotelAgent(BaseAgent):
    """Agent responsible for finding hotel recommendations with per-night pricing.

    Uses Tavily for web search and LLM for normalization.
    Returns 3-5 hotel recommendations with pricing from departing date.
    """

    TIMEOUT_SECONDS = 30
    MIN_RESULTS = 3
    MAX_RESULTS = 5

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute hotel search workflow.

        Args:
            state: Graph state containing constraints (destination, dates, etc.)

        Returns:
            Partial state update with hotels list and agent status
        """
        try:
            constraints = state.get("constraints", {})
            destination = constraints.get("destination")
            departing_date = constraints.get("departing_date")

            # Validate required fields
            if not destination or not isinstance(destination, str):
                self.logger.warning("Invalid or missing destination in constraints")
                return self._failed_result("Missing or invalid destination")

            # Build search queries (include dates for better price results)
            queries = self._build_queries(destination, departing_date, constraints)
            self.logger.info(
                f"HotelAgent searching with {len(queries)} queries",
                extra={"run_id": state.get("runId"), "destination": destination},
            )

            # Parallel search with timeout
            search_results = await self.with_timeout(
                self._parallel_search(queries), timeout_seconds=self.TIMEOUT_SECONDS
            )

            if search_results is None:
                return self._failed_result("Search timeout")

            # Flatten results
            all_items = []
            for result_set in search_results:
                if isinstance(result_set, Exception):
                    continue
                all_items.extend(result_set.get("results", []))

            if not all_items:
                return self._failed_result("No search results found")

            # LLM normalization
            hotels = await self._normalize_with_llm(all_items, constraints)

            if not hotels:
                return self._failed_result("LLM normalization returned no results")

            # Dedup and rank
            final = self._dedup_and_rank(hotels, max_n=self.MAX_RESULTS)

            if len(final) < self.MIN_RESULTS:
                self.logger.warning(
                    f"HotelAgent only found {len(final)} hotels (min: {self.MIN_RESULTS})"
                )
                return {
                    "hotels": [h.model_dump() for h in final],
                    "agent_statuses": {self.agent_id: "partial"},
                    "warnings": [
                        f"Only found {len(final)} hotels instead of {self.MIN_RESULTS}+"
                    ],
                }

            self.logger.info(
                f"HotelAgent completed",
                extra={
                    "run_id": state.get("runId"),
                    "result_count": len(final),
                },
            )

            return {
                "hotels": [h.model_dump() for h in final],
                "agent_statuses": {self.agent_id: "completed"},
            }

        except Exception as e:
            self.logger.error(
                f"HotelAgent failed: {e}",
                exc_info=True,
                extra={"run_id": state.get("runId")},
            )
            return self._failed_result(str(e))

    def _build_queries(
        self, destination: str, departing_date: str | None, constraints: dict[str, Any]
    ) -> list[str]:
        """Build search queries for hotel recommendations.

        Args:
            destination: Destination city
            departing_date: Departure date (YYYY-MM-DD)
            constraints: User constraints (budget, etc.)

        Returns:
            List of search queries
        """
        # Extract clean city name
        city = destination.split("(")[0].strip()

        # Include date in query for better pricing results
        date_str = f" {departing_date}" if departing_date else " 2026"

        queries = [
            f"best hotels in {city}{date_str}",
            f"top rated hotels {city}{date_str}",
            f"hotel recommendations {city}{date_str}",
        ]

        # Add budget-specific query if provided
        budget = constraints.get("budget", "moderate")
        if budget == "luxury":
            queries.append(f"luxury hotels {city}{date_str}")
        elif budget == "budget":
            queries.append(f"affordable hotels {city}{date_str}")

        return queries

    async def _parallel_search(self, queries: list[str]) -> list[dict[str, Any]]:
        """Execute multiple Tavily searches in parallel.

        Args:
            queries: List of search queries

        Returns:
            List of Tavily search results
        """
        search_tasks = [
            self.deps.tavily.search(q, max_results=6) for q in queries
        ]
        return await asyncio.gather(*search_tasks, return_exceptions=True)

    async def _normalize_with_llm(
        self, items: list[dict[str, Any]], constraints: dict[str, Any]
    ) -> list[HotelOutput]:
        """Use LLM to parse and normalize search results into structured output.

        Args:
            items: Raw Tavily search results
            constraints: User constraints for ranking

        Returns:
            List of normalized HotelOutput objects
        """
        # Deduplicate by URL first
        seen_urls = set()
        unique_items = []
        for item in items:
            url = canonicalize_url(item.get("url", ""))
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_items.append(item)

        if not unique_items:
            return []

        # Take top 20 by score
        sorted_items = sorted(
            unique_items,
            key=lambda x: x.get("score", 0),
            reverse=True,
        )[:20]

        # Format for LLM
        search_text = "\n\n".join(
            [
                f"Title: {item.get('title', 'N/A')}\n"
                f"URL: {item.get('url', 'N/A')}\n"
                f"Content: {item.get('content', 'N/A')[:500]}"
                for item in sorted_items
            ]
        )

        destination = constraints.get("destination", "the destination")
        departing_date = constraints.get("departing_date", "")
        budget = constraints.get("budget", "moderate")

        system_prompt = f"""You are a hotel recommendation expert. Parse the search results and extract 5-7 hotel recommendations for {destination}.

For each hotel, extract:
- name: Hotel name
- area: Neighborhood/district (if mentioned)
- price_per_night: Per-night price with currency (e.g., '$150', '₩180,000'). Extract from content if available.
- url: The original URL
- snippet: 1-2 sentence description
- why_recommended: 1-2 sentences explaining why this is a good choice
- amenities: List of key amenities (e.g., 'wifi', 'pool', 'breakfast-included', 'gym', 'parking')

Context:
- Check-in date: {departing_date}
- Budget preference: {budget}

Prioritize hotels that match the budget preference and are well-located for tourists.

Return results as a JSON array. Generate unique IDs using format "hotel_{{destination_code}}_{{number}}"."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, HotelList)
            return result.hotels

        except Exception as e:
            self.logger.error(f"LLM normalization failed: {e}", exc_info=True)
            return []

    def _dedup_and_rank(
        self, hotels: list[HotelOutput], max_n: int
    ) -> list[HotelOutput]:
        """Deduplicate by name and URL, then return top N.

        Args:
            hotels: List of hotel outputs
            max_n: Maximum number of results to return

        Returns:
            Deduplicated and ranked list
        """
        seen_names = set()
        seen_urls = set()
        unique = []

        for h in hotels:
            norm_name = normalize_name(h.name)
            canon_url = canonicalize_url(h.url)

            if norm_name in seen_names or canon_url in seen_urls:
                continue

            seen_names.add(norm_name)
            seen_urls.add(canon_url)
            unique.append(h)

        return unique[:max_n]
