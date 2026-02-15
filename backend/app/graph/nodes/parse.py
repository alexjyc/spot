import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompt import build_location_normalization_prompt
from app.schemas.spot_on import LocationNormalization, QueryContext, TravelConstraints

logger = logging.getLogger(__name__)


async def parse_request(state: dict[str, Any], *, deps: Any) -> dict[str, Any]:
    """Validate structured constraints and derive query context deterministically."""
    raw = state.get("constraints")
    if not isinstance(raw, dict) or not raw:
        raise ValueError("constraints are required")

    constraints = TravelConstraints.model_validate(raw)

    norm: LocationNormalization | None = None
    try:
        system_prompt = build_location_normalization_prompt()
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=(
                    f"Normalize these locations:\n"
                    f"- origin: {constraints.origin}\n"
                    f"- destination: {constraints.destination}\n"
                )
            ),
        ]
        norm = await deps.llm.structured(messages, LocationNormalization)
    except Exception:
        logger.debug("Location normalization skipped", exc_info=True)

    ctx = QueryContext.from_constraints_with_normalization(constraints, norm)

    logger.info(
        "Validated constraints: %s -> %s (%s)",
        constraints.origin,
        constraints.destination,
        ctx.trip_type,
        extra={"run_id": state.get("runId")},
    )

    return {
        "constraints": constraints.model_dump(),
        "query_context": {**ctx.model_dump(), **state.get("preferences", {})},
    }
