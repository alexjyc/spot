from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict


class SpotOnState(TypedDict, total=False):
    """State for Spot On multi-agent travel recommendation system."""
    # Input
    runId: str

    # Parsed constraints
    constraints: dict[str, Any]
    # {
    #   "origin": "Tokyo (NRT)",
    #   "destination": "Seoul (ICN)",
    #   "departing_date": "2026-03-15",
    #   "returning_date": "2026-03-18" | None
    # }

    # Raw search results from domain agents (merged via operator.add)
    raw_restaurants: Annotated[list[dict[str, Any]], operator.add]
    raw_travel_spots: Annotated[list[dict[str, Any]], operator.add]
    raw_hotels: Annotated[list[dict[str, Any]], operator.add]
    raw_car_rentals: Annotated[list[dict[str, Any]], operator.add]
    raw_flights: Annotated[list[dict[str, Any]], operator.add]

    # Domain agent outputs (written by WriterAgent)
    restaurants: list[dict[str, Any]]
    travel_spots: list[dict[str, Any]]
    hotels: list[dict[str, Any]]
    car_rentals: list[dict[str, Any]]
    flights: list[dict[str, Any]]

    # Reference items not selected as top picks
    references: list[dict[str, Any]]

    # Enrichment
    enriched_data: dict[str, dict[str, Any]]  # item_id -> enriched fields
    enrichment_loop_count: int
    enrichment_gap_ratio: float

    # Quality split outputs
    main_results: dict[str, list[dict[str, Any]]]

    # Report
    travel_report: dict[str, Any]

    # Derived deterministic context
    query_context: dict[str, Any]

    # Options
    skip_enrichment: bool

    # Metadata
    agent_statuses: Annotated[
        dict[str, str],
        operator.or_ 
    ]
    warnings: Annotated[list[str], operator.add]
    duration_ms: int

    # Final
    status: Literal["queued", "running", "done", "error"]
    final_output: dict[str, Any]
