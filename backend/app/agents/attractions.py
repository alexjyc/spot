"""Travel attractions recommendation agent."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent
from app.schemas.spot_on import AttractionOutput, AttractionList
from app.utils.dedup import normalize_name


class AttractionsAgent(BaseAgent):
    """Agent responsible for finding exactly 3 travel spot recommendations.

    Uses Tavily for web search and LLM for ranking/selection.
    Returns exactly 3 must-see attractions.
    """

    TIMEOUT_SECONDS = 30
    TARGET_RESULTS = 3

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            constraints = state.get("constraints", {})
            destination = constraints.get("destination")

            if not destination or not isinstance(destination, str):
                self.logger.warning("Invalid or missing destination in constraints")
                return self._failed_result("Missing or invalid destination")

            city = self._extract_city(destination)
            queries = self._build_queries(city, constraints)
            self.logger.info(
                f"AttractionsAgent searching with {len(queries)} queries",
                extra={"run_id": state.get("runId"), "destination": destination},
            )

            search_results = await self.with_timeout(
                self._parallel_search(queries), timeout_seconds=self.TIMEOUT_SECONDS
            )

            if search_results is None:
                return self._failed_result("Search timeout")

            all_items = self._flatten_search_results(search_results)
            if not all_items:
                return self._failed_result("No search results found")

            attractions = await self._select_top_with_llm(all_items, constraints)
            if not attractions:
                return self._failed_result("LLM selection returned no results")

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
                "AttractionsAgent completed",
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

    def _build_queries(self, city: str, constraints: dict[str, Any]) -> list[str]:
        queries = [
            f"top attractions in {city} 2026",
            f"must see places {city}",
            f"best things to do {city}",
        ]
        interest_q = self._build_interest_query(
            constraints.get("interests", []), "attractions", city
        )
        if interest_q:
            queries.append(interest_q)
        return queries

    async def _select_top_with_llm(
        self, items: list[dict[str, Any]], constraints: dict[str, Any]
    ) -> list[AttractionOutput]:
        unique_items = self._dedup_by_url(items)
        if not unique_items:
            return []

        sorted_items = self._top_by_score(unique_items, n=10)
        search_text = self._format_search_text(sorted_items)

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
            seen_names: set[str] = set()
            unique: list[AttractionOutput] = []
            for a in result.attractions:
                norm_name = normalize_name(a.name)
                if norm_name not in seen_names:
                    seen_names.add(norm_name)
                    unique.append(a)

            return unique

        except Exception as e:
            self.logger.error(f"LLM selection failed: {e}", exc_info=True)
            return []
