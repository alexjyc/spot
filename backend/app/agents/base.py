import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from app.utils.dedup import canonicalize_url, normalize_name


class BaseAgent(ABC):
    def __init__(self, agent_id: str, deps: Any) -> None:
        self.agent_id = agent_id
        self.deps = deps
        self.logger = logging.getLogger(f"agent.{agent_id}")

    @abstractmethod
    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
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

    async def _normalize_chunked(
        self,
        items: list[dict[str, Any]],
        normalize_fn: Callable[[list[dict[str, Any]]], Awaitable[list]],
        chunk_size: int,
    ) -> list:
        if len(items) <= chunk_size:
            return await normalize_fn(items)

        chunks = [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]
        results = await asyncio.gather(
            *[normalize_fn(chunk) for chunk in chunks],
            return_exceptions=True,
        )

        merged: list = []
        for batch in results:
            if isinstance(batch, Exception):
                self.logger.warning("Chunk normalization failed: %s", batch)
                continue
            merged.extend(batch)
        return merged


    # MIN_RESULTS_THRESHOLD = 15

    async def _search_with_fallback(
        self,
        primary_queries: list[str],
        fallback_queries: list[str],
        *,
        top_n: int,
        run_id: str | None = None,
        label: str | None = None,
        max_results_per_query: int = 8,
        include_domains: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        agent_label = f"{self.agent_id}:{label}" if label else self.agent_id
        primary_results = await self._parallel_search(
            primary_queries,
            max_results=max_results_per_query,
            include_domains=include_domains,
        )
        primary_items = self._flatten_search_results(primary_results)
        unique = self._dedup_by_url_and_title(primary_items)

        # if len(unique) < self.MIN_RESULTS_THRESHOLD and fallback_queries:
        #     fb_results = await self._parallel_search(
        #         fallback_queries,
        #         max_results=max_results_per_query,
        #         include_domains=include_domains,
        #     )
        #     fb_items = self._flatten_search_results(fb_results)
        #     unique = self._dedup_by_url_and_title(unique + fb_items)

        return self._top_by_score(unique, n=top_n)

    async def _parallel_search(
        self,
        queries: list[str],
        max_results: int = 8,
        include_domains: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute multiple Tavily searches in parallel, preserving per-query errors."""

        async def _one(query: str) -> dict[str, Any]:
            try:
                res = await self.deps.tavily.search(
                    query,
                    max_results=max_results,
                    include_domains=include_domains,
                )
                return {"query": query, "ok": True, "response": res}
            except Exception as e:
                return {"query": query, "ok": False, "error": str(e), "response": None}

        tasks = [_one(q) for q in queries]
        return await asyncio.gather(*tasks)


    @staticmethod
    def _dedup_by_url_and_title(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicate search results by (canonicalized URL, normalized title) composite key."""
        seen: set[tuple[str, str]] = set()
        unique: list[dict[str, Any]] = []
        for item in items:
            url = canonicalize_url(item.get("url", ""))
            title = normalize_name(item.get("title", ""))
            if not url:
                continue
            key = (url, title)
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique


    @staticmethod
    def _flatten_search_results(search_results: list[Any]) -> list[dict[str, Any]]:
        """Flatten parallel search results, skipping exceptions."""
        items: list[dict[str, Any]] = []
        for result_set in search_results:
            if not isinstance(result_set, dict):
                continue
            if not result_set.get("ok"):
                continue
            resp = result_set.get("response") or {}
            items.extend(resp.get("results", []))
        return items

    @staticmethod
    def _top_by_score(items: list[dict[str, Any]], n: int = 10) -> list[dict[str, Any]]:
        """Sort items by score descending and take top N."""
        return sorted(items, key=lambda x: x.get("score", 0), reverse=True)[:n]

    @staticmethod
    def _format_search_text(
        items: list[dict[str, Any]],
        content_limit: int = 500,
        raw_content_limit: int = 3000,
    ) -> str:
        """Format search result items into text for LLM input."""
        total = len(items)
        parts: list[str] = []
        for idx, item in enumerate(items, 1):
            block = (
                f"[{idx}/{total}] Title: {item.get('title', 'N/A')}\n"
                f"URL: {item.get('url', 'N/A')}\n"
                f"Content: {item.get('content', 'N/A')[:content_limit]}"
            )
            rc = (item.get("raw_content") or "")[:raw_content_limit]
            if rc:
                block += f"\nPage Content: {rc}"
            parts.append(block)
        header = f"Total items: {total} — you MUST output exactly {total} structured items.\n\n"
        return header + "\n\n".join(parts)
