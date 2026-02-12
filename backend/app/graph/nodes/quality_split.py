import logging
from typing import Any

logger = logging.getLogger(__name__)

# Tier 1: ALWAYS required for main results
CRITICAL_FIELDS: dict[str, list[str]] = {
    "restaurants": ["name", "url"],
    "travel_spots": ["name", "url"],
    "hotels": ["name", "url"],
    "car_rentals": ["provider", "url"],
    "flights": ["route", "url"],
}

# Tier 2: at least 1 required for main results
IMPORTANT_FIELDS: dict[str, list[str]] = {
    "restaurants": ["price_range", "cuisine"],      
    "travel_spots": ["kind"],                       
    "hotels": ["price_per_night"],                  
    "car_rentals": ["price_per_day"],               
    "flights": ["price_range"],                     
}

NAME_FIELD_MAP: dict[str, str] = {
    "car_rentals": "provider",
    "flights": "route",
}


def _merge_enriched(
    items: list[dict[str, Any]], enriched: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
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
    name_field = NAME_FIELD_MAP.get(category, "name")

    critical = CRITICAL_FIELDS.get(category, [])
    for field in critical:
        actual_field = name_field if field == "name" else field
        val = item.get(actual_field)
        if val in (None, "", [], {}):
            return False

    important = IMPORTANT_FIELDS.get(category, [])
    if not important:
        return True

    for field in important:
        val = item.get(field)
        if val not in (None, "", [], {}):
            return True

    return False


async def quality_split(state: dict[str, Any], *, deps: Any) -> dict[str, Any]:
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
                section_map = {
                    "restaurants": "restaurant",
                    "travel_spots": "attraction",
                    "hotels": "hotel",
                    "car_rentals": "car",
                    "flights": "flight",
                }
                name_field = NAME_FIELD_MAP.get(cat, "name")
                demoted_refs.append({
                    **item,
                    "section": section_map.get(cat, cat),
                    "title": item.get(name_field) or item.get("name") or "Source",
                    "content": item.get("snippet") or item.get("why_recommended") or "",
                })
        main_results[cat] = main

    existing_refs = state.get("references", [])
    all_refs = existing_refs + demoted_refs

    total_main = sum(len(v) for v in main_results.values())
    total_demoted = len(demoted_refs)

    logger.info(
        "QualitySplit: %d main results (critical + ≥1 important), %d demoted to references",
        total_main,
        total_demoted,
        extra={"run_id": state.get("runId")},
    )

    return {
        "main_results": main_results,
        "references": all_refs,
    }
