"""Spot On multi-agent graph - parallel execution architecture."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Coroutine

from langgraph.graph import END, StateGraph

from app.agents.attractions import AttractionsAgent
from app.agents.enrichment import EnrichmentAgent
from app.agents.hotel import HotelAgent
from app.agents.restaurant import RestaurantAgent
from app.agents.transport import TransportAgent
from app.graph.nodes.aggregate_results import aggregate_results
from app.graph.nodes.parse import parse_request
from app.graph.state import SpotOnState

logger = logging.getLogger(__name__)


def build_graph(deps: Any):
    """Build the Spot On multi-agent graph.

    Architecture:
                        ParseRequest
                             │
             ┌───────────────┼───────────────┬───────────────┐
             │               │               │               │
             ▼               ▼               ▼               ▼
      RestaurantAgent  AttractionsAgent  HotelAgent   TransportAgent
                                                        (Car + Flights)
             │               │               │               │
             └───────────────┴───────────────┴───────────────┘
                                  ▼
                          EnrichmentAgent
                                  ▼
                          AggregateResults
                                  ▼
                                END

    All 4 domain agents execute in parallel. EnrichmentAgent waits for all 4 to complete
    (LangGraph handles the join automatically). Then AggregateResults merges everything.

    Args:
        deps: Dependency container with services (tavily, llm, mongo, etc.)

    Returns:
        Compiled LangGraph
    """
    graph = StateGraph(SpotOnState)

    # Initialize agents
    restaurant_agent = RestaurantAgent("restaurant_agent", deps)
    attractions_agent = AttractionsAgent("attractions_agent", deps)
    hotel_agent = HotelAgent("hotel_agent", deps)
    transport_agent = TransportAgent("transport_agent", deps)
    enrichment_agent = EnrichmentAgent("enrichment_agent", deps)

    def _wrap_node(
        name: str, fn: Callable[[dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]]
    ):
        """Wrap node function with logging and event emission.

        For node functions (parse_request, aggregate_results) that need deps passed as kwarg.

        Args:
            name: Node name for logging
            fn: Async node function that accepts (state, deps=deps)

        Returns:
            Wrapped async function
        """

        async def _inner(state: dict[str, Any]) -> dict[str, Any]:
            run_id = state.get("runId")
            t0 = time.monotonic()
            logger.info("Graph node start: %s (runId=%s)", name, run_id or "-")

            # Emit start event
            if run_id:
                await deps.mongo.append_event(
                    run_id,
                    type="node",
                    node=name,
                    payload={
                        "node": name,
                        "status": "start",
                        "message": f"{name} started",
                    },
                )

            try:
                out = await fn(state, deps=deps)
                duration_ms = int((time.monotonic() - t0) * 1000)

                logger.info(
                    "Graph node end: %s (runId=%s, durationMs=%d)",
                    name,
                    run_id or "-",
                    duration_ms,
                )

                # Emit end event
                if run_id:
                    await deps.mongo.append_event(
                        run_id,
                        type="node",
                        node=name,
                        payload={
                            "node": name,
                            "status": "end",
                            "message": f"{name} finished",
                            "durationMs": duration_ms,
                        },
                    )

                # Store artifacts
                if run_id:
                    # Store constraints after parsing
                    if name == "ParseRequest" and out.get("constraints"):
                        await deps.mongo.add_artifact(
                            run_id,
                            type="constraints",
                            payload={"constraints": out.get("constraints")},
                        )

                    # Store final output
                    if name == "AggregateResults" and out.get("final_output"):
                        await deps.mongo.add_artifact(
                            run_id,
                            type="final",
                            payload={
                                "final_output": out.get("final_output"),
                                "warnings": state.get("warnings", [])
                                + out.get("warnings", []),
                            },
                        )

                return out

            except Exception as e:
                logger.exception("Node failed: %s", name)
                duration_ms = int((time.monotonic() - t0) * 1000)

                logger.error(
                    "Graph node error: %s (runId=%s, durationMs=%d, error=%s)",
                    name,
                    run_id or "-",
                    duration_ms,
                    str(e) or type(e).__name__,
                )

                # Emit error event
                if run_id:
                    await deps.mongo.append_event(
                        run_id,
                        type="node",
                        node=name,
                        payload={
                            "node": name,
                            "status": "error",
                            "message": f"{name} error",
                            "error": str(e),
                            "durationMs": duration_ms,
                        },
                    )

                raise

        return _inner

    def _wrap_agent(
        name: str, agent_method: Callable[[dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]]
    ):
        """Wrap agent method with logging and event emission.

        For agent methods (agent.execute) that already have self.deps and don't need deps passed.

        Args:
            name: Node name for logging
            agent_method: Async agent method that accepts only (state)

        Returns:
            Wrapped async function
        """

        async def _inner(state: dict[str, Any]) -> dict[str, Any]:
            run_id = state.get("runId")
            t0 = time.monotonic()
            logger.info("Graph node start: %s (runId=%s)", name, run_id or "-")

            # Emit start event
            if run_id:
                await deps.mongo.append_event(
                    run_id,
                    type="node",
                    node=name,
                    payload={
                        "node": name,
                        "status": "start",
                        "message": f"{name} started",
                    },
                )

            try:
                out = await agent_method(state)  # Agents use self.deps, no deps kwarg
                duration_ms = int((time.monotonic() - t0) * 1000)

                logger.info(
                    "Graph node end: %s (runId=%s, durationMs=%d)",
                    name,
                    run_id or "-",
                    duration_ms,
                )

                # Emit end event
                if run_id:
                    await deps.mongo.append_event(
                        run_id,
                        type="node",
                        node=name,
                        payload={
                            "node": name,
                            "status": "end",
                            "message": f"{name} finished",
                            "durationMs": duration_ms,
                        },
                    )

                return out

            except Exception as e:
                logger.exception("Node failed: %s", name)
                duration_ms = int((time.monotonic() - t0) * 1000)

                logger.error(
                    "Graph node error: %s (runId=%s, durationMs=%d, error=%s)",
                    name,
                    run_id or "-",
                    duration_ms,
                    str(e) or type(e).__name__,
                )

                # Emit error event
                if run_id:
                    await deps.mongo.append_event(
                        run_id,
                        type="node",
                        node=name,
                        payload={
                            "node": name,
                            "status": "error",
                            "message": f"{name} error",
                            "error": str(e),
                            "durationMs": duration_ms,
                        },
                    )

                raise

        return _inner

    # =========================================================================
    # NODES
    # =========================================================================
    graph.add_node("ParseRequest", _wrap_node("ParseRequest", parse_request))

    # Domain agents (execute in parallel)
    graph.add_node(
        "RestaurantAgent", _wrap_agent("RestaurantAgent", restaurant_agent.execute)
    )
    graph.add_node(
        "AttractionsAgent", _wrap_agent("AttractionsAgent", attractions_agent.execute)
    )
    graph.add_node("HotelAgent", _wrap_agent("HotelAgent", hotel_agent.execute))
    graph.add_node("TransportAgent", _wrap_agent("TransportAgent", transport_agent.execute))

    # Enrichment agent (sequential after all domain agents)
    graph.add_node(
        "EnrichmentAgent", _wrap_agent("EnrichmentAgent", enrichment_agent.execute)
    )

    # Aggregation
    graph.add_node("AggregateResults", _wrap_node("AggregateResults", aggregate_results))

    # =========================================================================
    # GRAPH STRUCTURE - MULTI-AGENT PARALLEL EXECUTION
    # =========================================================================
    #
    # Parse -> [4 domain agents in parallel] -> Enrichment -> Aggregate -> END
    #
    # LangGraph automatically handles the join pattern: EnrichmentAgent waits for
    # all 4 domain agents to complete before executing.
    # =========================================================================

    graph.set_entry_point("ParseRequest")

    # Parallel fan-out: All 4 domain agents start after ParseRequest
    graph.add_edge("ParseRequest", "RestaurantAgent")
    graph.add_edge("ParseRequest", "AttractionsAgent")
    graph.add_edge("ParseRequest", "HotelAgent")
    graph.add_edge("ParseRequest", "TransportAgent")

    # Join pattern: EnrichmentAgent waits for all 4 domain agents
    graph.add_edge("RestaurantAgent", "EnrichmentAgent")
    graph.add_edge("AttractionsAgent", "EnrichmentAgent")
    graph.add_edge("HotelAgent", "EnrichmentAgent")
    graph.add_edge("TransportAgent", "EnrichmentAgent")

    # Sequential after enrichment
    graph.add_edge("EnrichmentAgent", "AggregateResults")
    graph.add_edge("AggregateResults", END)

    return graph.compile()
