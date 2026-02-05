"""Parse request node for Spot On system."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.schemas.spot_on import ConstraintsOutput

logger = logging.getLogger(__name__)


async def parse_request(state: dict[str, Any], *, deps: Any) -> dict[str, Any]:
    """Parse user prompt into structured travel constraints.

    Simplified version for Spot On that extracts:
    - Origin city (with airport code if available)
    - Destination city (with airport code if available)
    - Departing date
    - Returning date (optional)
    - Interests (optional)
    - Budget level (optional)

    Args:
        state: Graph state with prompt
        deps: Dependencies (llm service)

    Returns:
        Partial state update with constraints dict
    """
    prompt = state.get("prompt", "")

    if not prompt:
        logger.warning("Empty prompt provided")
        return {
            "constraints": {},
            "warnings": ["No prompt provided"],
        }

    system_prompt = """You are a travel query parser. Extract travel details from the user's prompt.

Extract the following fields:
- origin: Origin city with airport code if mentioned (e.g., "Tokyo (NRT)", "Los Angeles")
- destination: Destination city with airport code if mentioned (e.g., "Seoul (ICN)", "Paris")
- departing_date: Departure date in ISO format (YYYY-MM-DD). Infer year as 2026 if not specified.
- returning_date: Return date in ISO format (YYYY-MM-DD), or null for one-way trips
- interests: List of user interests if mentioned (e.g., ["food", "history", "nature", "shopping"])
- budget: Budget level - one of "budget", "moderate", or "luxury". Default to "moderate" if not specified.

Examples:
- "Tokyo to Seoul, departing March 15, returning March 18" -> origin: "Tokyo", destination: "Seoul", departing_date: "2026-03-15", returning_date: "2026-03-18"
- "From LAX to Paris CDG on 4/10/26" -> origin: "Los Angeles (LAX)", destination: "Paris (CDG)", departing_date: "2026-04-10", returning_date: null
- "New York to London next month, love museums and food" -> origin: "New York", destination: "London", departing_date: [best guess], interests: ["museums", "food"]

Be flexible with date formats. Infer airport codes when possible but don't make them up.
"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt),
    ]

    try:
        result: ConstraintsOutput = await deps.llm.structured(
            messages, ConstraintsOutput
        )
        constraints = result.model_dump()

        logger.info(
            f"Parsed constraints: {constraints['destination']} "
            f"from {constraints['origin']} on {constraints['departing_date']}",
            extra={"run_id": state.get("runId")},
        )

        return {"constraints": constraints}

    except Exception as e:
        logger.error(f"Parse request failed: {e}", exc_info=True)

        # Return minimal constraints to allow graceful degradation
        return {
            "constraints": {
                "origin": "Unknown",
                "destination": "Unknown",
                "departing_date": "2026-01-01",
                "returning_date": None,
                "interests": [],
                "budget": "moderate",
            },
            "warnings": [f"Failed to parse request: {str(e)}"],
        }
