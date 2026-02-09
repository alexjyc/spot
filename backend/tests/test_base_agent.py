"""Tests for BaseAgent helper methods."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.agents.base import BaseAgent


class ConcreteAgent(BaseAgent):
    """Concrete subclass for testing abstract BaseAgent."""

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        return {}


@pytest.fixture
def agent():
    deps = SimpleNamespace(
        llm=AsyncMock(), tavily=AsyncMock(), mongo=AsyncMock()
    )
    return ConcreteAgent("test_agent", deps)


class TestDedupByUrl:
    def test_removes_duplicate_urls(self):
        items = [
            {"url": "https://example.com/a", "name": "first"},
            {"url": "https://example.com/a", "name": "second"},
            {"url": "https://example.com/b", "name": "third"},
        ]
        result = BaseAgent._dedup_by_url(items)
        assert len(result) == 2
        assert result[0]["name"] == "first"
        assert result[1]["name"] == "third"

    def test_keeps_first_occurrence(self):
        items = [
            {"url": "https://example.com/a?q=1", "name": "with-query"},
            {"url": "https://example.com/a?q=2", "name": "diff-query"},
        ]
        result = BaseAgent._dedup_by_url(items)
        # Both canonicalize to same URL (query stripped)
        assert len(result) == 1
        assert result[0]["name"] == "with-query"

    def test_empty_list(self):
        assert BaseAgent._dedup_by_url([]) == []


class TestDedupByNameAndUrl:
    def test_dedup_by_name(self):
        Item = SimpleNamespace
        items = [
            Item(name="Test Place", url="https://a.com"),
            Item(name="test place", url="https://b.com"),
            Item(name="Other", url="https://c.com"),
        ]
        result = BaseAgent._dedup_by_name_and_url(items, top_n=10)
        assert len(result) == 2

    def test_dedup_by_url(self):
        Item = SimpleNamespace
        items = [
            Item(name="Place A", url="https://example.com/page"),
            Item(name="Place B", url="https://example.com/page"),
        ]
        result = BaseAgent._dedup_by_name_and_url(items, top_n=10)
        assert len(result) == 1

    def test_respects_top_n(self):
        Item = SimpleNamespace
        items = [
            Item(name=f"Place {i}", url=f"https://example.com/{i}")
            for i in range(10)
        ]
        result = BaseAgent._dedup_by_name_and_url(items, top_n=3)
        assert len(result) == 3


class TestFlattenSearchResults:
    def test_flattens_results(self):
        search_results = [
            {"results": [{"title": "A"}, {"title": "B"}]},
            {"results": [{"title": "C"}]},
        ]
        result = BaseAgent._flatten_search_results(search_results)
        assert len(result) == 3

    def test_skips_exceptions(self):
        search_results = [
            {"results": [{"title": "A"}]},
            ValueError("network error"),
            {"results": [{"title": "B"}]},
        ]
        result = BaseAgent._flatten_search_results(search_results)
        assert len(result) == 2

    def test_empty_results(self):
        assert BaseAgent._flatten_search_results([]) == []


class TestTopByScore:
    def test_sorts_descending(self):
        items = [
            {"score": 0.5, "name": "low"},
            {"score": 0.9, "name": "high"},
            {"score": 0.7, "name": "mid"},
        ]
        result = BaseAgent._top_by_score(items, n=3)
        assert result[0]["name"] == "high"
        assert result[1]["name"] == "mid"
        assert result[2]["name"] == "low"

    def test_limits_to_n(self):
        items = [{"score": i} for i in range(10)]
        result = BaseAgent._top_by_score(items, n=3)
        assert len(result) == 3

    def test_missing_score_defaults_to_zero(self):
        items = [{"name": "no-score"}, {"score": 0.5, "name": "with-score"}]
        result = BaseAgent._top_by_score(items, n=2)
        assert result[0]["name"] == "with-score"


class TestFormatSearchText:
    def test_formats_items(self):
        items = [
            {"title": "Place A", "url": "https://a.com", "content": "About A"},
        ]
        result = BaseAgent._format_search_text(items)
        assert "Title: Place A" in result
        assert "URL: https://a.com" in result
        assert "Content: About A" in result

    def test_respects_content_limit(self):
        items = [{"title": "T", "url": "U", "content": "x" * 1000}]
        result = BaseAgent._format_search_text(items, content_limit=50)
        # Content should be truncated
        content_line = [l for l in result.split("\n") if l.startswith("Content:")][0]
        content_value = content_line[len("Content: "):]
        assert len(content_value) == 50

    def test_missing_fields(self):
        items = [{}]
        result = BaseAgent._format_search_text(items)
        assert "N/A" in result


class TestWithTimeout:
    async def test_returns_result_on_success(self, agent):
        async def quick():
            return "done"

        result = await agent.with_timeout(quick(), timeout_seconds=5.0)
        assert result == "done"

    async def test_returns_none_on_timeout(self, agent):
        async def slow():
            await asyncio.sleep(10)
            return "never"

        result = await agent.with_timeout(slow(), timeout_seconds=0.01)
        assert result is None


class TestFailedResult:
    def test_correct_structure(self, agent):
        result = agent._failed_result("something broke")
        assert result["agent_statuses"]["test_agent"] == "failed"
        assert "test_agent failed: something broke" in result["warnings"]

    def test_custom_warnings(self, agent):
        result = agent._failed_result("err", warnings=["custom warning"])
        assert result["warnings"] == ["custom warning"]
