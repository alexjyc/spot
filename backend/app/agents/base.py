"""Base agent class for all Spot On agents."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Abstract base class for all agents in the multi-agent system.

    Provides common functionality like logging, timeout handling, and
    standardized error responses.
    """

    def __init__(self, agent_id: str, deps: Any) -> None:
        """Initialize base agent.

        Args:
            agent_id: Unique identifier for this agent (e.g., "restaurant_agent")
            deps: Dependency container with services (tavily, llm, mongo, etc.)
        """
        self.agent_id = agent_id
        self.deps = deps
        self.logger = logging.getLogger(f"agent.{agent_id}")

    @abstractmethod
    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute agent logic and return partial state update.

        Args:
            state: Current graph state

        Returns:
            Dictionary with partial state updates. Should include:
            - Agent-specific results (e.g., "restaurants" key for RestaurantAgent)
            - "agent_statuses" dict with self.agent_id -> "completed"|"failed"|"partial"|"skipped"
            - "warnings" list if there were non-fatal issues

        Note:
            Should NOT raise exceptions. Return error status instead.
        """
        pass

    async def with_timeout(
        self, coro: Any, timeout_seconds: float
    ) -> Any | None:
        """Execute coroutine with timeout.

        Args:
            coro: Coroutine to execute
            timeout_seconds: Maximum execution time

        Returns:
            Coroutine result, or None if timeout occurred
        """
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
        """Helper to return standardized failure response.

        Args:
            error: Error message to log
            warnings: Optional list of warning messages

        Returns:
            Dictionary with agent_statuses set to "failed" and warnings list
        """
        warning_msgs = warnings or [f"{self.agent_id} failed: {error}"]
        return {
            "agent_statuses": {self.agent_id: "failed"},
            "warnings": warning_msgs,
        }

