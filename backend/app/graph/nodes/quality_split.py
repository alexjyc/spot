"""QualitySplit node — separates main results from incomplete references."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Required fields per category to qualify as a main result
REQUIRED_FIELDS: dict[str, list[str]] = {
    "restaurants": ["name", "url", "cuisine", "price_range"],
    "travel_spots": ["name", "url", "kind"],
    "hotels": ["name", "url", "price_per_night"],
    "car_rentals": ["name", "url", "price_per_day"],
    "flights": ["name", "url", "price_range"],
}

# Field used as "name" for car_rentals (uses "provider" instead of "name")
NAME_FIELD_MAP: dict[str, str] = {
    "car_rentals": "provider",
    "flights": "airline",
}


def _merge_enriched(
    items: list[dict[str, Any]], enriched: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge enrichment data into items without overwriting existing values."""
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


def _has_required(item: dict[str, Any], category: str) -> bool:
    """Check if item has all required fields for its category."""
    required = REQUIRED_FIELDS.get(category, [])
    name_field = NAME_FIELD_MAP.get(category, "name")

    for field in required:
        # Map "name" to the actual field name for this category
        actual_field = name_field if field == "name" else field
        val = item.get(actual_field)
        if val in (None, "", [], {}):
            return False
    return True


async def quality_split(state: dict[str, Any], *, deps: Any) -> dict[str, Any]:
    """Split items into main_results (complete) and references (incomplete).

    Pure logic — no API calls. Merges enrichment data first, then splits
    based on required field completeness.
    """
    enriched = state.get("enriched_data", {})
    categories = ["restaurants", "travel_spots", "hotels", "car_rentals", "flights"]

    main_results: dict[str, list[dict[str, Any]]] = {}
    demoted_refs: list[dict[str, Any]] = []

    for cat in categories:
        items = _merge_enriched(state.get(cat, []), enriched)
        main: list[dict[str, Any]] = []
        for item in items:
            if _has_required(item, cat):
                main.append(item)
            else:
                # Demote to references
                section_map = {
                    "restaurants": "restaurant",
                    "travel_spots": "attraction",
                    "hotels": "hotel",
                    "car_rentals": "car",
                    "flights": "flight",
                }
                demoted_refs.append({
                    **item,
                    "section": section_map.get(cat, cat),
                })
        main_results[cat] = main

    # Merge with existing references from NormalizeAgent
    existing_refs = state.get("references", [])
    all_refs = existing_refs + demoted_refs

    total_main = sum(len(v) for v in main_results.values())
    total_demoted = len(demoted_refs)

    logger.info(
        "QualitySplit: %d main results, %d demoted to references",
        total_main,
        total_demoted,
        extra={"run_id": state.get("runId")},
    )

    return {
        "main_results": main_results,
        "references": all_refs,
    }
