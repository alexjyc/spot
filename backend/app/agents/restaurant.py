"""Restaurant recommendation agent."""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.schemas.spot_on import RestaurantOutput, RestaurantList
from app.utils.dedup import canonicalize_url, normalize_name


class RestaurantAgent(BaseAgent):
    """Agent responsible for finding restaurant recommendations.

    Uses Tavily for web search and LLM for normalization/ranking.
    Returns top 5 restaurants with enrichment-ready URLs.
    """

    TIMEOUT_SECONDS = 30
    MAX_RESULTS = 5

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute restaurant search workflow.

        Args:
            state: Graph state containing constraints (destination, dates, etc.)

        Returns:
            Partial state update with restaurants list and agent status

        Raises:
            Does not raise - returns error status on failure
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
                f"RestaurantAgent searching with {len(queries)} queries",
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
            restaurants = await self._normalize_with_llm(all_items, constraints)

            if not restaurants:
                return self._failed_result("LLM normalization returned no results")

            # Dedup and rank
            final = self._dedup_and_rank(restaurants, top_n=self.MAX_RESULTS)

            self.logger.info(
                f"RestaurantAgent completed",
                extra={
                    "run_id": state.get("runId"),
                    "result_count": len(final),
                    "queries_used": len(queries),
                },
            )

            return {
                "restaurants": [r.model_dump() for r in final],
                "agent_statuses": {self.agent_id: "completed"},
            }

        except Exception as e:
            self.logger.error(
                f"RestaurantAgent failed: {e}",
                exc_info=True,
                extra={"run_id": state.get("runId")},
            )
            return self._failed_result(str(e))

    def _build_queries(
        self, destination: str, constraints: dict[str, Any]
    ) -> list[str]:
        """Build search queries for restaurant recommendations.

        Args:
            destination: Destination city
            constraints: User constraints (budget, interests, etc.)

        Returns:
            List of search queries
        """
        # Extract clean city name (remove airport codes)
        city = destination.split("(")[0].strip()

        queries = [
            f"best restaurants in {city} 2026",
            f"top rated dining {city}",
            f"must-try restaurants {city}",
        ]

        # Add interest-based query if provided
        interests = constraints.get("interests", [])
        if interests and len(interests) > 0:
            interest_str = " ".join(interests[:2])  # Use first 2 interests
            queries.append(f"{interest_str} restaurants in {city}")

        return queries

    async def _parallel_search(self, queries: list[str]) -> list[dict[str, Any]]:
        """Execute multiple Tavily searches in parallel.

        Args:
            queries: List of search queries

        Returns:
            List of Tavily search results
        """
        # 6 -> 3
        search_tasks = [
            self.deps.tavily.search(q, max_results=3) for q in queries
        ]
        return await asyncio.gather(*search_tasks, return_exceptions=True)

    async def _normalize_with_llm(
        self, items: list[dict[str, Any]], constraints: dict[str, Any]
    ) -> list[RestaurantOutput]:
        """Use LLM to parse and normalize search results into structured output.

        Args:
            items: Raw Tavily search results
            constraints: User constraints for ranking

        Returns:
            List of normalized RestaurantOutput objects
        """
        # Deduplicate by URL first to reduce LLM input size
        seen_urls = set()
        unique_items = []
        for item in items:
            url = canonicalize_url(item.get("url", ""))
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_items.append(item)

        if not unique_items:
            return []

        # Take top 20 by score (if available) to limit LLM input
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

        system_prompt = f"""You are a restaurant recommendation expert. Parse the search results and extract the top 8-10 restaurant recommendations for first-day dining in {destination}.

For each restaurant, extract:
- name: Restaurant name
- cuisine: Type of cuisine
- area: Neighborhood/district (if mentioned)
- price_range: Price level like '$', '$$', '$$$' (if mentioned)
- url: The original URL
- snippet: 1-2 sentence description
- why_recommended: 1-2 sentences explaining why this is a good choice for first day
- tags: List of relevant tags (e.g., 'michelin-star', 'local-favorite', 'vegetarian-friendly')

Prioritize well-known, highly-rated restaurants suitable for first-day visitors.{interest_context}

Return results as a JSON array of restaurant objects. Generate unique IDs using format "restaurant_{{destination_code}}_{{number}}"."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Search results:\n\n{search_text}"),
        ]

        try:
            result = await self.deps.llm.structured(messages, RestaurantList)
            return result.restaurants

        except Exception as e:
            self.logger.error(f"LLM normalization failed: {e}", exc_info=True)
            return []

    def _dedup_and_rank(
        self, restaurants: list[RestaurantOutput], top_n: int
    ) -> list[RestaurantOutput]:
        """Deduplicate by name and URL, then return top N.

        Args:
            restaurants: List of restaurant outputs
            top_n: Number of results to return

        Returns:
            Deduplicated and ranked list
        """
        seen_names = set()
        seen_urls = set()
        unique = []

        for r in restaurants:
            norm_name = normalize_name(r.name)
            canon_url = canonicalize_url(r.url)

            # Skip if we've seen this name or URL
            if norm_name in seen_names or canon_url in seen_urls:
                continue

            seen_names.add(norm_name)
            seen_urls.add(canon_url)
            unique.append(r)

        return unique[:top_n]
