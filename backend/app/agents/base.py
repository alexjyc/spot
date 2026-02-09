"""Base agent class for all Spot On agents."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

from app.utils.dedup import canonicalize_url, normalize_name


class BaseAgent(ABC):
    """Abstract base class for all agents in the multi-agent system.

    Provides common functionality like logging, timeout handling,
    standardized error responses, and shared search helpers.
    """

    def __init__(self, agent_id: str, deps: Any) -> None:
        self.agent_id = agent_id
        self.deps = deps
        self.logger = logging.getLogger(f"agent.{agent_id}")

    @abstractmethod
    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute agent logic and return partial state update."""
        pass

    async def with_timeout(
        self, coro: Any, timeout_seconds: float
    ) -> Any | None:
        try:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            self.logger.warning(
                f"Agent {self.agent_id} timed out after {timeout_seconds}s"
            )
            return None

    def _failed_result(
        self, error: str, warnings: list[str] | None = None
    ) -> dict[str, Any]:
        warning_msgs = warnings or [f"{self.agent_id} failed: {error}"]
        return {
            "agent_statuses": {self.agent_id: "failed"},
            "warnings": warning_msgs,
        }

    # -- Shared helpers used by domain agents --

    async def _parallel_search(
        self, queries: list[str], max_results: int = 8
    ) -> list[dict[str, Any]]:
        """Execute multiple Tavily searches in parallel."""
        tasks = [self.deps.tavily.search(q, max_results=max_results) for q in queries]
        return await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    def _dedup_by_url(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicate search results by canonicalized URL."""
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in items:
            url = canonicalize_url(item.get("url", ""))
            if url and url not in seen:
                seen.add(url)
                unique.append(item)
        return unique

    @staticmethod
    def _dedup_by_name_and_url(items: list[Any], top_n: int) -> list[Any]:
        """Deduplicate Pydantic model results by name and URL, return top N."""
        seen_names: set[str] = set()
        seen_urls: set[str] = set()
        unique: list[Any] = []
        for item in items:
            norm_name = normalize_name(item.name)
            canon_url = canonicalize_url(item.url)
            if norm_name in seen_names or canon_url in seen_urls:
                continue
            seen_names.add(norm_name)
            seen_urls.add(canon_url)
            unique.append(item)
        return unique[:top_n]

    @staticmethod
    def _flatten_search_results(search_results: list[Any]) -> list[dict[str, Any]]:
        """Flatten parallel search results, skipping exceptions."""
        items: list[dict[str, Any]] = []
        for result_set in search_results:
            if isinstance(result_set, Exception):
                continue
            items.extend(result_set.get("results", []))
        return items

    @staticmethod
    def _top_by_score(items: list[dict[str, Any]], n: int = 10) -> list[dict[str, Any]]:
        """Sort items by score descending and take top N."""
        return sorted(items, key=lambda x: x.get("score", 0), reverse=True)[:n]

    @staticmethod
    def _format_search_text(items: list[dict[str, Any]], content_limit: int = 500) -> str:
        """Format search result items into text for LLM input."""
        return "\n\n".join(
            f"Title: {item.get('title', 'N/A')}\n"
            f"URL: {item.get('url', 'N/A')}\n"
            f"Content: {item.get('content', 'N/A')[:content_limit]}"
            for item in items
        )

