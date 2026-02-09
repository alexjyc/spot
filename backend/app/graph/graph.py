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
from app.agents.writer import WriterAgent
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
        (search only)   (search only)   (search only)  (search only)
             │               │               │               │
             └───────────────┴───────────────┴───────────────┘
                                  ▼
                            WriterAgent
                      (5 parallel LLM calls)
                                  ▼
                          EnrichmentAgent
                                  ▼
                          AggregateResults
                                  ▼
                                END

    All 4 domain agents execute in parallel (search only). WriterAgent waits
    for all 4 to complete, then runs 5 parallel LLM normalizations.
    EnrichmentAgent processes only the top picks (~18 items).

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
    writer_agent = WriterAgent("writer_agent", deps)
    enrichment_agent = EnrichmentAgent("enrichment_agent", deps)

    async def _emit_node_event(
        run_id: str,
        *,
        node: str,
        status: str,
        message: str,
        duration_ms: int | None = None,
        error: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {"node": node, "status": status, "message": message}
        if duration_ms is not None:
            payload["durationMs"] = duration_ms
        if error:
            payload["error"] = error
        await deps.mongo.append_event(run_id, type="node", node=node, payload=payload)
        await deps.mongo.set_node_progress(run_id, node=node, payload=payload)

    def _wrap(
        name: str,
        fn: Callable[..., Coroutine[Any, Any, dict[str, Any]]],
        *,
        pass_deps_kwarg: bool,
    ):
        async def _inner(state: dict[str, Any]) -> dict[str, Any]:
            run_id = state.get("runId")
            t0 = time.monotonic()
            logger.info("Graph node start: %s (runId=%s)", name, run_id or "-")

            if run_id:
                await _emit_node_event(
                    run_id,
                    node=name,
                    status="start",
                    message=f"{name} started",
                )

            try:
                out = await (fn(state, deps=deps) if pass_deps_kwarg else fn(state))
                duration_ms = int((time.monotonic() - t0) * 1000)
                logger.info(
                    "Graph node end: %s (runId=%s, durationMs=%d)",
                    name,
                    run_id or "-",
                    duration_ms,
                )

                if run_id:
                    await _emit_node_event(
                        run_id,
                        node=name,
                        status="end",
                        message=f"{name} finished",
                        duration_ms=duration_ms,
                    )

                    if name == "ParseRequest" and out.get("constraints"):
                        await deps.mongo.add_artifact(
                            run_id,
                            type="constraints",
                            payload={"constraints": out.get("constraints")},
                        )

                return out

            except Exception as e:
                duration_ms = int((time.monotonic() - t0) * 1000)
                logger.exception("Node failed: %s", name)
                logger.error(
                    "Graph node error: %s (runId=%s, durationMs=%d, error=%s)",
                    name,
                    run_id or "-",
                    duration_ms,
                    str(e) or type(e).__name__,
                )

                if run_id:
                    await _emit_node_event(
                        run_id,
                        node=name,
                        status="error",
                        message=f"{name} error",
                        duration_ms=duration_ms,
                        error=str(e),
                    )
                raise

        return _inner

    # =========================================================================
    # NODES
    # =========================================================================
    graph.add_node("ParseRequest", _wrap("ParseRequest", parse_request, pass_deps_kwarg=True))

    # Domain agents (execute in parallel)
    graph.add_node(
        "RestaurantAgent",
        _wrap("RestaurantAgent", restaurant_agent.execute, pass_deps_kwarg=False),
    )
    graph.add_node(
        "AttractionsAgent",
        _wrap("AttractionsAgent", attractions_agent.execute, pass_deps_kwarg=False),
    )
    graph.add_node(
        "HotelAgent", _wrap("HotelAgent", hotel_agent.execute, pass_deps_kwarg=False)
    )
    graph.add_node(
        "TransportAgent",
        _wrap("TransportAgent", transport_agent.execute, pass_deps_kwarg=False),
    )

    # Writer agent (normalizes raw search results into top picks)
    graph.add_node(
        "WriterAgent",
        _wrap("WriterAgent", writer_agent.execute, pass_deps_kwarg=False),
    )

    # Enrichment agent (sequential after writer)
    graph.add_node(
        "EnrichmentAgent",
        _wrap("EnrichmentAgent", enrichment_agent.execute, pass_deps_kwarg=False),
    )

    # Aggregation
    graph.add_node(
        "AggregateResults",
        _wrap("AggregateResults", aggregate_results, pass_deps_kwarg=True),
    )

    # =========================================================================
    # GRAPH STRUCTURE - MULTI-AGENT PARALLEL EXECUTION
    # =========================================================================
    #
    # Parse -> [4 domain agents in parallel] -> Writer -> Enrichment -> Aggregate -> END
    #
    # LangGraph automatically handles the join pattern: WriterAgent waits for
    # all 4 domain agents to complete before executing.
    # =========================================================================

    graph.set_entry_point("ParseRequest")

    # Parallel fan-out: All 4 domain agents start after ParseRequest
    graph.add_edge("ParseRequest", "RestaurantAgent")
    graph.add_edge("ParseRequest", "AttractionsAgent")
    graph.add_edge("ParseRequest", "HotelAgent")
    graph.add_edge("ParseRequest", "TransportAgent")

    # Join pattern: WriterAgent waits for all 4 domain agents
    graph.add_edge("RestaurantAgent", "WriterAgent")
    graph.add_edge("AttractionsAgent", "WriterAgent")
    graph.add_edge("HotelAgent", "WriterAgent")
    graph.add_edge("TransportAgent", "WriterAgent")

    # Sequential: Writer -> Enrichment -> Aggregate -> END
    graph.add_edge("WriterAgent", "EnrichmentAgent")
    graph.add_edge("EnrichmentAgent", "AggregateResults")
    graph.add_edge("AggregateResults", END)

    return graph.compile()
