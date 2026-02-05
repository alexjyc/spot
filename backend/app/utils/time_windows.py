from __future__ import annotations

from typing import Literal


Pace = Literal["relaxed", "standard", "packed"]


def default_day_slots(pace: Pace | None) -> list[str]:
    # Simple heuristic slots; can be extended without changing item "kind" design.
    if pace == "relaxed":
        return ["Morning", "Afternoon", "Evening"]
    if pace == "packed":
        return ["Early morning", "Morning", "Lunch", "Afternoon", "Dinner", "Night"]
    return ["Morning", "Lunch", "Afternoon", "Dinner", "Evening"]
