"""Travel attractions recommendation agent."""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.schemas.spot_on import AttractionOutput, AttractionList
from app.utils.dedup import canonicalize_url, normalize_name


class AttractionsAgent(BaseAgent):
    """Agent responsible for finding exactly 3 travel spot recommendations.

    Uses Tavily for web search and LLM for ranking/selection.
    Returns exactly 3 must-see attractions.
    """

    TIMEOUT_SECONDS = 30
    TARGET_RESULTS = 3

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute attractions search workflow.

        Args:
            state: Graph state containing constraints (destination, dates, etc.)

        Returns:
            Partial state update with travel_spots list and agent status
        """
        try:
            constraints = state.get("constraints", {})
            destination = constraints.get("destination")

            # Validate required fields
            if not destination or not isinstance(destination, str):
                self.logger.warning("Invalid or missing destination in constraints")
                return self._failed_result("Missing or invalid destination")

            # Build search queries
            queries = self._build_queries(destination, constraints)
            self.logger.info(
                f"AttractionsAgent searching with {len(queries)} queries",
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

            # LLM ranking to select top 3
            attractions = await self._select_top_with_llm(all_items, constraints)

            if not attractions:
                return self._failed_result("LLM selection returned no results")

            # Ensure exactly 3 results
            final = attractions[: self.TARGET_RESULTS]

            if len(final) < self.TARGET_RESULTS:
                self.logger.warning(
                    f"AttractionsAgent only found {len(final)} attractions (target: {self.TARGET_RESULTS})"
                )
                return {
                    "travel_spots": [a.model_dump() for a in final],
                    "agent_statuses": {self.agent_id: "partial"},
                    "warnings": [
                        f"Only found {len(final)} attractions instead of {self.TARGET_RESULTS}"
                    ],
                }

            self.logger.info(
                f"AttractionsAgent completed",
                extra={
                    "run_id": state.get("runId"),
                    "result_count": len(final),
                },
            )

            return {
                "travel_spots": [a.model_dump() for a in final],
                "agent_statuses": {self.agent_id: "completed"},
            }

        except Exception as e:
            self.logger.error(
                f"AttractionsAgent failed: {e}",
                exc_info=True,
                extra={"run_id": state.get("runId")},
            )
            return self._failed_result(str(e))

    def _build_queries(
        self, destination: str, constraints: dict[str, Any]
    ) -> list[str]:
        """Build search queries for attraction recommendations.

        Args:
            destination: Destination city
            constraints: User constraints (interests, etc.)

        Returns:
            List of search queries
        """
        # Extract clean city name
        city = destination.split("(")[0].strip()

        queries = [
            f"top attractions in {city} 2026",
            f"must see places {city}",
            f"best things to do {city}",
        ]

        # Add interest-based query if provided
        interests = constraints.get("interests", [])
        if interests and len(interests) > 0:
            interest_str = " ".join(interests[:2])
            queries.append(f"{interest_str} attractions in {city}")

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

    async def _select_top_with_llm(
        self, items: list[dict[str, Any]], constraints: dict[str, Any]
    ) -> list[AttractionOutput]:
        """Use LLM to select and rank top 3 attractions.

        Args:
            items: Raw Tavily search results
            constraints: User constraints for ranking

        Returns:
            List of exactly 3 AttractionOutput objects (or fewer if not enough found)
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
        )[:10]  # Reduced from 20 to prevent LLM timeout

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
        interests = constraints.get("interests", [])
        interest_context = (
            f" User interests: {', '.join(interests)}." if interests else ""
        )

        system_prompt = f"""You are a travel expert. Parse the search results and select EXACTLY 3 must-see attractions in {destination}.

For each attraction, extract:
- name: Attraction name
- kind: Type (e.g., 'museum', 'park', 'landmark', 'temple', 'shopping district')
- area: Neighborhood/district (if mentioned)
- url: The original URL
- snippet: 1-2 sentence description
- why_recommended: 1-2 sentences explaining why this is must-see
- estimated_duration_min: Typical visit duration in minutes (estimate if not stated)
- time_of_day_fit: Best times to visit as list (e.g., ['morning'], ['afternoon', 'evening'])

Select attractions that:
1. Are truly iconic or highly recommended for first-time visitors
2. Offer diverse experiences (mix of culture, nature, landmarks, etc.)
3. Are realistically visitable during a trip{interest_context}

IMPORTANT: Return EXACTLY 3 attractions. Prioritize quality over quantity.

Return results as a JSON array. Generate unique IDs using format "attraction_{{destination_code}}_{{number}}"."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, AttractionList)

            # Deduplicate by name
            seen_names = set()
            unique = []
            for a in result.attractions:
                norm_name = normalize_name(a.name)
                if norm_name not in seen_names:
                    seen_names.add(norm_name)
                    unique.append(a)

            return unique

        except Exception as e:
            self.logger.error(f"LLM selection failed: {e}", exc_info=True)
            return []
