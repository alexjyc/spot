"""Aggregate results node for Spot On system."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def aggregate_results(state: dict[str, Any], *, deps: Any) -> dict[str, Any]:
    """Merge enriched data into final output.

    Takes results from all domain agents and enrichment agent,
    combines them into a structured final_output.

    Args:
        state: Graph state with domain agent results and enriched_data
        deps: Dependencies (not used)

    Returns:
        Partial state update with final_output and status
    """
    enriched = state.get("enriched_data", {})

    # Merge enrichment into restaurants
    restaurants = []
    for r in state.get("restaurants", []):
        item = r.copy()
        if r["id"] in enriched:
            # Merge enriched details into the restaurant dict
            item.update(enriched[r["id"]])
        restaurants.append(item)

    # Merge enrichment into travel spots
    travel_spots = []
    for t in state.get("travel_spots", []):
        item = t.copy()
        if t["id"] in enriched:
            item.update(enriched[t["id"]])
        travel_spots.append(item)

    # Merge enrichment into hotels
    hotels = []
    for h in state.get("hotels", []):
        item = h.copy()
        if h["id"] in enriched:
            item.update(enriched[h["id"]])
        hotels.append(item)

    # Merge enrichment into car rentals
    car_rentals = []
    for c in state.get("car_rentals", []):
        item = c.copy()
        if c["id"] in enriched:
            item.update(enriched[c["id"]])
        car_rentals.append(item)

    # Merge enrichment into flights
    flights = []
    for f in state.get("flights", []):
        item = f.copy()
        if f["id"] in enriched:
            item.update(enriched[f["id"]])
        flights.append(item)

    # Build final output
    final_output = {
        "restaurants": restaurants,
        "travel_spots": travel_spots,
        "hotels": hotels,
        "car_rentals": car_rentals,
        "flights": flights,
        "constraints": state.get("constraints", {}),
    }

    # Count total results
    total_results = (
        len(restaurants)
        + len(travel_spots)
        + len(hotels)
        + len(car_rentals)
        + len(flights)
    )

    logger.info(
        f"Aggregated {total_results} total results",
        extra={
            "run_id": state.get("runId"),
            "restaurants": len(restaurants),
            "travel_spots": len(travel_spots),
            "hotels": len(hotels),
            "car_rentals": len(car_rentals),
            "flights": len(flights),
        },
    )

    return {
        "final_output": final_output,
        "status": "done",
    }
