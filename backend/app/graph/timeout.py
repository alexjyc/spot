from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TimeoutBudget:
    """Tracks execution time budget across phases."""

    def __init__(self, total_seconds: float):
        self.total_seconds = total_seconds
        self.start_time = time.monotonic()

    def remaining(self) -> float:
        """Returns remaining time in seconds."""
        elapsed = time.monotonic() - self.start_time
        return max(0.0, self.total_seconds - elapsed)

    def elapsed(self) -> float:
        """Returns elapsed time in seconds."""
        return time.monotonic() - self.start_time

    def is_exhausted(self) -> bool:
        """Returns True if budget is exhausted."""
        return self.remaining() <= 0

    def can_proceed(self, required_seconds: float) -> bool:
        """Returns True if there's enough budget for the operation."""
        return self.remaining() >= required_seconds


async def with_timeout(
    coro: Awaitable[T],
    timeout_seconds: float,
    fallback: T | None = None,
    operation_name: str = "operation",
) -> T | None:
    """
    Execute a coroutine with a timeout, returning fallback on timeout.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(
            "%s timed out after %.1fs, using fallback", operation_name, timeout_seconds
        )
        return fallback
    except Exception as e:
        logger.error("%s failed: %s", operation_name, e)
        return fallback


async def gather_with_timeout(
    coros: list[Awaitable[T]],
    timeout_seconds: float,
    operation_name: str = "batch operation",
) -> list[T | None]:
    """
    Execute multiple coroutines concurrently with a shared timeout.
    Returns partial results if timeout occurs.
    """
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*coros, return_exceptions=True),
            timeout=timeout_seconds,
        )
        # Convert exceptions to None
        return [r if not isinstance(r, Exception) else None for r in results]
    except asyncio.TimeoutError:
        logger.warning(
            "%s timed out after %.1fs", operation_name, timeout_seconds
        )
        return [None] * len(coros)


def create_budget_from_state(state: dict[str, Any], total_timeout: int = 180) -> TimeoutBudget:
    """Create or retrieve a TimeoutBudget from graph state."""
    start_ms = state.get("startTimeMs")
    if start_ms:
        budget = TimeoutBudget(total_timeout)
        budget.start_time = start_ms / 1000.0
        return budget
    return TimeoutBudget(total_timeout)
