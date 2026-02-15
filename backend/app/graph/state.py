import operator
from typing import Annotated, Any, Literal, TypedDict


class SpotOnState(TypedDict, total=False):
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

    # Domain agent outputs
    restaurants: list[dict[str, Any]]
    travel_spots: list[dict[str, Any]]
    hotels: list[dict[str, Any]]
    car_rentals: list[dict[str, Any]]
    flights: list[dict[str, Any]]

    # Reference items
    references: list[dict[str, Any]]

    # Enrichment
    enriched_data: dict[str, dict[str, Any]]
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
    preferences: dict[str, Any]

    # Metadata
    agent_statuses: Annotated[
        dict[str, str],
        operator.or_ 
    ]
    warnings: Annotated[list[str], operator.add]

    # Final
    status: Literal["queued", "running", "done", "error"]
    final_output: dict[str, Any]
