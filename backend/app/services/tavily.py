"""Tavily API client for search and content extraction."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from tavily import AsyncTavilyClient

logger = logging.getLogger(__name__)


class TavilyService:
    """Thin wrapper around AsyncTavilyClient - returns raw dicts."""

    def __init__(
        self,
        api_key: str,
        *,
        search_timeout_seconds: float = 10.0,
        extract_timeout_seconds: float = 30.0
    ) -> None:
        if not api_key:
            raise ValueError("TAVILY_API_KEY is required")
        self.client = AsyncTavilyClient(api_key=api_key)
        self.search_timeout_seconds = max(1.0, float(search_timeout_seconds))
        self.extract_timeout_seconds = max(1.0, float(extract_timeout_seconds))

    async def search(
        self,
        query: str,
        *,
        max_results: int = 8,
        include_raw_content: bool = False,
        include_domains: list[str] | None = None,
    ) -> dict[str, Any]:
        """Search and return raw Tavily response dict."""
        t0 = time.monotonic()
        kwargs: dict[str, Any] = {
            "query": query,
            "max_results": max_results,
            "include_raw_content": include_raw_content,
        }
        if include_domains:
            kwargs["include_domains"] = include_domains
        try:
            return await asyncio.wait_for(
                self.client.search(**kwargs),
                timeout=self.search_timeout_seconds,
            )
        except asyncio.TimeoutError as e:
            raise TimeoutError(
                f"Tavily search timed out after {self.search_timeout_seconds:.0f}s"
            ) from e
        finally:
            logger.debug(
                "Tavily search finished in %.0fms", (time.monotonic() - t0) * 1000
            )

    async def extract(self, urls: list[str]) -> dict[str, Any]:
        """Extract content from URLs and return raw Tavily response dict."""
        t0 = time.monotonic()
        try:
            return await asyncio.wait_for(
                self.client.extract(urls=urls),
                timeout=self.extract_timeout_seconds,
            )
        except asyncio.TimeoutError as e:
            raise TimeoutError(
                f"Tavily extract timed out after {self.extract_timeout_seconds:.0f}s"
            ) from e
        finally:
            logger.debug(
                "Tavily extract finished in %.0fms", (time.monotonic() - t0) * 1000
            )

    async def map(
        self,
        url: str,
        *,
        max_depth: int = 2,
        limit: int = 30,
        instructions: str | None = None,
        allow_external: bool = False,
    ) -> dict[str, Any]:
        """Map a site structure from a starting URL and return raw Tavily response dict."""
        t0 = time.monotonic()
        try:
            return await asyncio.wait_for(
                self.client.map(
                    url=url,
                    max_depth=max_depth,
                    limit=limit,
                    instructions=instructions,
                    allow_external=allow_external,
                ),
                timeout=self.extract_timeout_seconds,
            )
        except asyncio.TimeoutError as e:
            raise TimeoutError(
                f"Tavily map timed out after {self.extract_timeout_seconds:.0f}s"
            ) from e
        finally:
            logger.debug("Tavily map finished in %.0fms", (time.monotonic() - t0) * 1000)
