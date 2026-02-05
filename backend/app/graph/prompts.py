from __future__ import annotations

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage


SYSTEM_STYLE = (
    "You are a careful travel planning assistant. "
    "Do not invent facts like opening hours; if unknown, set fields to null and add a warning. "
    "Prefer official sources (venue websites, tourism boards, museums, transit agencies)."
)


def parse_request_messages(user_prompt: str, options_json: str) -> list[BaseMessage]:
    return [
        SystemMessage(content=SYSTEM_STYLE),
        HumanMessage(
            content=f"""Convert this freeform travel request into structured constraints.

INPUT PROMPT:
{user_prompt}

OPTIONS (may be empty):
{options_json}

Extract: city, region, country, dates, days, budget, pace ("relaxed"|"standard"|"packed"|null), interests, must_do, constraints (e.g. "stroller-friendly"), notes."""
        ),
    ]


def normalize_candidates_messages(
    raw_results_json: str, city_hint: str | None
) -> list[BaseMessage]:
    city_line = f"City hint: {city_hint}" if city_hint else "City hint: null"
    return [
        SystemMessage(content=SYSTEM_STYLE),
        HumanMessage(
            content=f"""Normalize raw web search results into candidate items for an itinerary.
Keep kinds open-ended (freeform string, not enum).
Also output helpful non-schedulable references (ticket pages, transit guides, neighborhood guides).
Do NOT include concrete opening hours; hours must be verified later.

{city_line}

RAW SEARCH RESULTS JSON:
{raw_results_json}"""
        ),
    ]


def extract_details_messages(candidates_json: str, raw_contents_json: str) -> list[BaseMessage]:
    """Prompt for extracting price, hours, address from raw webpage content."""
    return [
        SystemMessage(content=SYSTEM_STYLE),
        HumanMessage(
            content=f"""Extract specific details from webpage content for each candidate.

CANDIDATES (each has candidateId, name, url):
{candidates_json}

RAW WEBPAGE CONTENTS (keyed by URL):
{raw_contents_json}

For each candidate, extract from its corresponding webpage content:
1. priceHint - Entry fee, menu prices, typical cost (use local currency symbol)
2. hoursText - Opening hours, days open/closed (e.g., "Mon-Sat 09:00-21:00, Sun closed")
3. address - Full street address with postal code if available

If information is not found in the content, leave as null.
Match each result to its candidateId."""
        ),
    ]


def global_schedule_messages(
    candidates_json: str,
    constraints_json: str,
    weather_json: str,
    slot_labels: list[str],
    num_days: int,
) -> list[BaseMessage]:
    slots_str = ", ".join(slot_labels)
    return [
        SystemMessage(content=SYSTEM_STYLE),
        HumanMessage(
            content=f"""You are scheduling a {num_days}-day travel itinerary.

SLOT TEMPLATE (each day has these slots): {slots_str}

CONSTRAINTS:
{constraints_json}

WEATHER CONTEXT:
{weather_json}

CANDIDATES (each has id, name, kind, tags, area, timeOfDayFit, mealFit, weatherFit, energy):
{candidates_json}

INSTRUCTIONS:
1. Assign one candidate per slot per day. Use candidateId from the candidates list.
2. Each candidate may only be used ONCE across the entire itinerary.
3. Reason about geographic clustering — group nearby spots on the same day/morning/afternoon.
4. Reason about cultural context — markets are best early morning, temples may close at sunset.
5. Reason about logical daily flow — coffee → museum → lunch nearby → park walk.
6. Prioritize must_do items into prime slots, not leftovers.
7. For meal slots (Lunch, Dinner), prefer restaurants/cafes/food markets.
8. For Evening/Night slots, prefer bars, music venues, shows.
9. Consider weather: if indoor bias is high, prefer indoor candidates.
11. Provide a short reasoning for each slot assignment.
12. If you cannot fill a slot because no suitable candidate remains, leave it out and add it to gaps.
13. For each slot, also list 1-3 alternateIds (unused candidates that would also fit).
14. In gaps, describe what's missing so a targeted search can fill it."""
        ),
    ]


def verify_facts_messages(extract_pages_json: str) -> list[BaseMessage]:
    return [
        SystemMessage(content=SYSTEM_STYLE),
        HumanMessage(
            content=f"""From extracted page text, pull practical visit facts (hours/closures/address/booking) and warnings.
Do NOT guess hours; if hours are unclear or absent, set hoursText null and add a warning.

EXTRACT PAGES JSON:
{extract_pages_json}"""
        ),
    ]


def compose_messages(state_json: str) -> list[BaseMessage]:
    return [
        SystemMessage(content=SYSTEM_STYLE),
        HumanMessage(
            content=f"""Produce a grounded travel itinerary and user-facing warnings/citations.
Use the VERIFIED items and their URLs; do not add new venues not present in the input.
You may include non-schedulable references as a separate "References" section in markdown.

INPUT STATE JSON:
{state_json}"""
        ),
    ]


def travel_allocator_messages(
    candidates_json: str,
    constraints_json: str,
    num_days: int,
    capacity_per_day: int,
) -> list[BaseMessage]:
    return [
        SystemMessage(content=SYSTEM_STYLE),
        HumanMessage(
            content=f"""You are allocating candidates to DAYS (not time slots) for a {num_days}-day trip.

CONSTRAINTS:
{constraints_json}

CANDIDATES (each has id, name, kind, tags, area, address):
{candidates_json}

INSTRUCTIONS:
1. Assign candidates to days. Each day should have {capacity_per_day} candidates (±1).
2. Each candidate may only be assigned to ONE day.
3. PRIORITIZE geographic routing: analyze addresses to group nearby candidates on the same day to minimize travel time.
4. Prioritize must_do items - ensure they are assigned to days.
5. Balance activity types across days - don't put all restaurants on one day.
6. For each day, provide areaFocus (the main neighborhood/area) and brief reasoning.
7. If candidates cannot fit or don't suit any day, add their IDs to unassigned.

OUTPUT FORMAT:
- allocations: list of dayIndex (0-indexed), candidateIds, areaFocus, reasoning
- unassigned: list of candidate IDs that couldn't be allocated"""
        ),
    ]


def day_planner_messages(
    day_index: int,
    date_label: str | None,
    candidates_json: str,
    constraints_json: str,
    weather_json: str,
    slot_labels: list[str],
) -> list[BaseMessage]:
    slots_str = ", ".join(slot_labels)
    date_info = f"Date: {date_label}" if date_label else f"Day {day_index + 1}"
    return [
        SystemMessage(content=SYSTEM_STYLE),
        HumanMessage(
            content=f"""You are scheduling a SINGLE day of a travel itinerary.

{date_info}
SLOT TEMPLATE: {slots_str}

CONSTRAINTS:
{constraints_json}

WEATHER CONTEXT (for this day):
{weather_json}

CANDIDATES ALLOCATED TO THIS DAY (each has id, name, kind, tags, area, timeOfDayFit, mealFit, energy):
{candidates_json}

INSTRUCTIONS:
1. Assign ONE candidate per slot. Use candidateId from the candidates list.
2. Each candidate may only be used ONCE.
3. Reason about logical daily flow - coffee → museum → lunch nearby → park walk.
4. For meal slots (Lunch, Dinner), prefer restaurants/cafes/food markets.
5. For Evening/Night slots, prefer bars, music venues, shows.
6. Consider candidate's timeOfDayFit and energy level.
7. Provide reasoning for each slot assignment.
8. List 1-3 alternateIds for each slot (other candidates that would fit).
9. If you cannot fill a slot, skip it.
10. List any unused candidates in unusedCandidates.

OUTPUT FORMAT:
- dayIndex: {day_index}
- dateLabel: the date label if known
- slots: list of slotLabel, candidateId, reasoning, alternateIds
- unusedCandidates: list of candidate IDs not used"""
        ),
    ]


def geo_enrich_messages(
    extract_pages_json: str, city_hint: str | None
) -> list[BaseMessage]:
    city_line = f"City context: {city_hint}" if city_hint else "City context: unknown"
    return [
        SystemMessage(content=SYSTEM_STYLE),
        HumanMessage(
            content=f"""Extract location information from venue page content.

{city_line}

For each venue, extract:
- address: Full street address (if found on page)
- area: Neighborhood/district name (e.g., "Shibuya", "Old Town", "Downtown")
- nearbyLandmarks: Notable nearby places (stations, monuments, etc.)
- locationNotes: Helpful context (e.g., "2nd floor", "inside mall", "near exit 3")

If information is not found, set the field to null. Do not guess.

EXTRACTED PAGE CONTENT:
{extract_pages_json}"""
        ),
    ]
