"""Aggregate results node for Spot On system."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _merge(items: list[dict[str, Any]], enriched: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge enrichment data into domain agent results.

    Rule: add all new fields from enrichment, but do not overwrite non-empty values
    already present in the item. This lets Writer provide fields when supported by
    search snippets, while enrichment backfills missing values from page content.
    """

    merged: list[dict[str, Any]] = []
    for it in items:
        extra = enriched.get(it.get("id", ""), {})
        if not extra:
            merged.append(it)
            continue

        out = dict(it)
        for k, v in extra.items():
            if k not in out or out[k] in (None, "", [], {}):
                out[k] = v
        merged.append(out)
    return merged


async def aggregate_results(state: dict[str, Any], *, deps: Any) -> dict[str, Any]:
    """Merge enriched data into final output.

    Takes results from all domain agents and enrichment agent,
    combines them into a structured final_output.
    """
    enriched = state.get("enriched_data", {})

    categories = ["restaurants", "travel_spots", "hotels", "car_rentals", "flights"]
    final_output = {cat: _merge(state.get(cat, []), enriched) for cat in categories}
    final_output["constraints"] = state.get("constraints", {})
    final_output["references"] = state.get("references", [])

    total_results = sum(len(final_output[cat]) for cat in categories)

    logger.info(
        f"Aggregated {total_results} total results",
        extra={
            "run_id": state.get("runId"),
            **{cat: len(final_output[cat]) for cat in categories},
        },
    )

    return {
        "final_output": final_output,
        "status": "done",
    }
