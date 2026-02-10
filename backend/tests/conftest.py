"""Shared fixtures for the backend test suite."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_mongo():
    """AsyncMock of MongoService with all required methods."""
    mongo = AsyncMock()
    mongo.create_run = AsyncMock()
    mongo.update_run = AsyncMock()
    mongo.get_run = AsyncMock(return_value=None)
    mongo.append_event = AsyncMock()
    mongo.set_node_progress = AsyncMock()
    mongo.add_artifact = AsyncMock()
    mongo.ping = AsyncMock()
    mongo.ensure_indexes = AsyncMock()
    mongo.close = MagicMock()
    return mongo


@pytest.fixture
def mock_llm():
    """AsyncMock of LLMService with configurable structured output."""
    llm = AsyncMock()
    llm.structured = AsyncMock()
    return llm


@pytest.fixture
def mock_tavily():
    """AsyncMock of TavilyService."""
    tavily = AsyncMock()
    tavily.search = AsyncMock(return_value={"results": []})
    tavily.extract = AsyncMock(return_value={"results": []})
    return tavily


@pytest.fixture
def mock_deps(mock_mongo, mock_llm, mock_tavily):
    """SimpleNamespace deps bundle with mocked services."""
    deps = SimpleNamespace()
    deps.mongo = mock_mongo
    deps.llm = mock_llm
    deps.tavily = mock_tavily
    deps.settings = SimpleNamespace(
        openai_api_key="test-key",
        openai_model="gpt-test",
        openai_timeout=60,
        tavily_api_key="test-key",
        tavily_search_timeout=10,
        tavily_extract_timeout=30,
        mongodb_uri="mongodb://localhost:27017",
        db_name="test_db",
        cors_origins="http://localhost:3000",
    )
    deps.graph = None
    return deps


@pytest.fixture
def sample_constraints():
    """Valid ConstraintsOutput dict."""
    return {
        "origin": "Tokyo (NRT)",
        "destination": "Seoul (ICN)",
        "departing_date": "2026-03-15",
        "returning_date": "2026-03-18",
    }


@pytest.fixture
def sample_state(sample_constraints):
    """Minimal SpotOnState dict for agent tests."""
    return {
        "runId": "test-run-123",
        "constraints": sample_constraints,
        "restaurants": [],
        "travel_spots": [],
        "hotels": [],
        "car_rentals": [],
        "flights": [],
        "enriched_data": {},
        "agent_statuses": {},
        "warnings": [],
        "status": "running",
    }
