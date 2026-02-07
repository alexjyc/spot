from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict


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
    #   "returning_date": "2026-03-18" | None
    # }

    # Domain agent outputs
    restaurants: list[dict[str, Any]]
    travel_spots: list[dict[str, Any]]
    hotels: list[dict[str, Any]]
    car_rentals: list[dict[str, Any]]
    flights: list[dict[str, Any]]

    # Enrichment
    enriched_data: dict[str, dict[str, Any]]  # item_id -> {price, hours, address, phone}

    # Options
    skip_enrichment: bool

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
