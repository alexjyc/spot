import asyncio
import logging
from typing import Any

from tavily import AsyncTavilyClient

logger = logging.getLogger(__name__)


class TavilyService:
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
        include_domains: list[str] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "query": query,
            "max_results": max_results,
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

    async def extract(self, urls: list[str]) -> dict[str, Any]:
        try:
            return await asyncio.wait_for(
                self.client.extract(urls=urls),
                timeout=self.extract_timeout_seconds,
            )
        except asyncio.TimeoutError as e:
            raise TimeoutError(
                f"Tavily extract timed out after {self.extract_timeout_seconds:.0f}s"
            ) from e
