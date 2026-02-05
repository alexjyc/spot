from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict
import operator


class SpotOnState(TypedDict, total=False):
    """State for Spot On multi-agent travel recommendation system."""

    # Input
    runId: str
    prompt: str

    # Parsed constraints
    constraints: dict[str, Any]
    # {
    #   "origin": "Tokyo (NRT)",
    #   "destination": "Seoul (ICN)",
    #   "departing_date": "2026-03-15",
    #   "returning_date": "2026-03-18" | None,
    #   "interests": ["history", "food"],
    #   "budget": "moderate"
    # }

    # Domain agent outputs
    restaurants: list[dict[str, Any]]
    travel_spots: list[dict[str, Any]]
    hotels: list[dict[str, Any]]
    car_rentals: list[dict[str, Any]]
    flights: list[dict[str, Any]]

    # Enrichment
    enriched_data: dict[str, dict[str, Any]]  # item_id -> {price, hours, address, phone}

    # Metadata
    agent_statuses: Annotated[
        dict[str, str],
        operator.or_  # Merge dicts: {a: 1} | {b: 2} = {a: 1, b: 2}
    ]  # agent_id -> "completed"|"failed"|"partial"|"skipped"
    warnings: Annotated[list[str], operator.add]  # Merge lists from parallel agents
    duration_ms: int

    # Final
    status: Literal["queued", "running", "done", "error"]
    final_output: dict[str, Any]


class GraphState(TypedDict, total=False):
    runId: str
    prompt: str
    options: dict[str, Any]

    status: Literal["queued", "running", "done", "error"]
    constraints: dict[str, Any]

    searchPlan: list[str]
    rawSearch: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    references: list[dict[str, Any]]

    weatherContext: dict[str, Any]

    # Two-phase allocator fields
    geoClusters: dict[str, list[str]]  # clusterLabel -> list of candidateIds
    dayAllocations: list[dict[str, Any]]  # TravelAllocator output
    dayPlanResults: list[dict[str, Any]]  # Parallel DayPlanner outputs
    startTimeMs: int  # For timeout tracking
    executionBudget: dict[str, Any]  # Per-phase time limits

    slotTemplate: dict[str, Any]
    draftItinerary: dict[str, Any]
    alternatesBySlot: dict[str, Any]

    itinerary: dict[str, Any]
    markdown: str
    warnings: Annotated[list[str], operator.add]
    citations: list[dict[str, Any]]

    usedCandidateIds: list[str]
    scheduleAttempt: int
