"""Base agent class for all Spot On agents."""

from __future__ import annotations

import asyncio
import collections
import logging
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlparse

from app.utils.dedup import canonicalize_url, domain, normalize_name


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

    MIN_RESULTS_THRESHOLD = 15

    @staticmethod
    def _is_serp_url(url: str) -> bool:
        """Heuristic: drop generic search pages that don't represent a single place."""
        try:
            p = urlparse(url or "")
        except Exception:
            return False

        host = (p.netloc or "").lower()
        path = p.path or ""
        if host.endswith("google.com"):
            if path.startswith("/search"):
                return True
            if path.startswith("/maps/search"):
                return True
        return False

    @classmethod
    def _filter_serp_items(
        cls, items: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], int]:
        kept: list[dict[str, Any]] = []
        dropped = 0
        for item in items:
            url = (item.get("url", "") or "") if isinstance(item, dict) else ""
            if url and cls._is_serp_url(url):
                dropped += 1
                continue
            kept.append(item)
        return kept, dropped

    async def _emit_run_log(
        self,
        run_id: str | None,
        message: str,
        *,
        node: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.logger.info(
            message,
            extra={"run_id": run_id, "node": node} if run_id or node else None,
        )
        mongo = getattr(self.deps, "mongo", None)
        if not run_id or not mongo:
            return
        try:
            await mongo.append_event(
                run_id,
                type="log",
                node=node,
                payload={"message": message, **(payload or {})},
            )
        except Exception:
            self.logger.debug("Failed to emit run log", exc_info=True)

    @staticmethod
    def _summarize_items(items: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(items)
        missing_url = 0
        canon_urls: list[str] = []
        domains: list[str] = []

        for item in items:
            url = (item.get("url", "") or "") if isinstance(item, dict) else ""
            canon = canonicalize_url(url)
            if not canon or canon == "https:///":
                missing_url += 1
                continue
            canon_urls.append(canon)
            domains.append(domain(canon))

        canon_counts = collections.Counter(canon_urls)
        domain_counts = collections.Counter([d for d in domains if d])
        top_dups = [(u, c) for u, c in canon_counts.most_common(5) if c > 1]
        top_domains = domain_counts.most_common(5)

        return {
            "total": total,
            "missing_url": missing_url,
            "top_duplicates": top_dups,
            "top_domains": top_domains,
        }

    async def _search_with_fallback(
        self,
        primary_queries: list[str],
        fallback_queries: list[str],
        *,
        top_n: int,
        run_id: str | None = None,
        label: str | None = None,
        max_results_per_query: int = 8,
        include_raw_content: bool = False,
    ) -> list[dict[str, Any]]:
        """Search with primary queries, fall back if dedup drops below threshold."""
        agent_label = f"{self.agent_id}:{label}" if label else self.agent_id
        primary_results = await self._parallel_search(
            primary_queries, max_results=max_results_per_query, include_raw_content=include_raw_content
        )
        primary_items = self._flatten_search_results(primary_results)
        primary_items_filtered, primary_serp_dropped = self._filter_serp_items(primary_items)
        primary_items_for_dedup = (
            primary_items
            if primary_serp_dropped and len(primary_items_filtered) < self.MIN_RESULTS_THRESHOLD
            else primary_items_filtered
        )

        primary_summary = self._summarize_items(primary_items_for_dedup)
        unique = self._dedup_by_url_and_title(primary_items_for_dedup)

        if len(unique) < self.MIN_RESULTS_THRESHOLD and fallback_queries:
            fb_results = await self._parallel_search(
                fallback_queries, max_results=max_results_per_query, include_raw_content=include_raw_content
            )
            fb_items = self._flatten_search_results(fb_results)
            fb_items_filtered, fb_serp_dropped = self._filter_serp_items(fb_items)
            fb_items_for_dedup = (
                fb_items
                if fb_serp_dropped and len(fb_items_filtered) < self.MIN_RESULTS_THRESHOLD
                else fb_items_filtered
            )

            fb_summary = self._summarize_items(fb_items_for_dedup)
            unique = self._dedup_by_url_and_title(unique + fb_items_for_dedup)

        return self._top_by_score(unique, n=top_n)

    async def _parallel_search(
        self, queries: list[str], max_results: int = 8, include_raw_content: bool = False
    ) -> list[dict[str, Any]]:
        """Execute multiple Tavily searches in parallel, preserving per-query errors."""

        async def _one(query: str) -> dict[str, Any]:
            try:
                res = await self.deps.tavily.search(
                    query, max_results=max_results, include_raw_content=include_raw_content
                )
                return {"query": query, "ok": True, "response": res}
            except Exception as e:
                return {"query": query, "ok": False, "error": str(e), "response": None}

        tasks = [_one(q) for q in queries]
        return await asyncio.gather(*tasks)

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
        include_raw_content: bool = False,
        raw_content_limit: int = 3000,
    ) -> str:
        """Format search result items into text for LLM input."""
        parts: list[str] = []
        for item in items:
            block = (
                f"Title: {item.get('title', 'N/A')}\n"
                f"URL: {item.get('url', 'N/A')}\n"
                f"Content: {item.get('content', 'N/A')[:content_limit]}"
            )
            if include_raw_content:
                rc = (item.get("raw_content") or "")[:raw_content_limit]
                if rc:
                    block += f"\nPage Content: {rc}"
            parts.append(block)
        return "\n\n".join(parts)
