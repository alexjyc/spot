"""Spot On multi-agent graph - parallel execution architecture."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Coroutine

from langgraph.graph import END, StateGraph

from app.agents.attractions import AttractionsAgent
from app.agents.enrichment import EnrichmentAgent
from app.agents.hotel import HotelAgent
from app.agents.report_writer import ReportWriterAgent
from app.agents.restaurant import RestaurantAgent
from app.agents.transport import TransportAgent
from app.agents.writer import NormalizeAgent
from app.graph.nodes.parse import parse_request
from app.graph.nodes.quality_split import quality_split
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
             │               │               │               │
             └───────────────┴───────────────┴───────────────┘
                                  ▼
                           NormalizeAgent
                      (5 parallel LLM calls)
                                  ▼
                         normalize_router
                        ┌────────┴────────┐
                   enrichment ON     enrichment OFF
                        │                 │
                        ▼                 │
                   EnrichAgent            │
                        │                 │
                   enrichment_router      │
                   ┌────┴────┐            │
                   loop     done          │
                        │                 │
                        ▼                 │
                   QualitySplit  ◄─────────┘
                        │
                        ▼
                   ReportWriter
                        │
                        ▼
                       END
    """
    graph = StateGraph(SpotOnState)

    # Initialize agents
    restaurant_agent = RestaurantAgent("restaurant_agent", deps)
    attractions_agent = AttractionsAgent("attractions_agent", deps)
    hotel_agent = HotelAgent("hotel_agent", deps)
    transport_agent = TransportAgent("transport_agent", deps)
    normalize_agent = NormalizeAgent("normalize_agent", deps)
    enrichment_agent = EnrichmentAgent("enrichment_agent", deps)
    report_writer = ReportWriterAgent("report_writer", deps)

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

    async def _emit_run_log(
        run_id: str,
        *,
        node: str,
        input: dict[str, Any],
        output: dict[str, Any],
        duration_ms: int,
        error: dict[str, Any] | None = None,
    ) -> None:
        await deps.mongo.append_node_end_log(
            run_id,
            node=node,
            input=input,
            output=output,
            duration_ms=duration_ms,
            error=error,
        )

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
            node_input: dict[str, Any] = dict(state)

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
                    try:
                        await _emit_run_log(
                            run_id,
                            node=name,
                            input=node_input,
                            output=out,
                            duration_ms=duration_ms,
                        )
                    except Exception:
                        logger.debug(
                            "Failed to emit node end log: %s (runId=%s)",
                            name,
                            run_id,
                            exc_info=True,
                        )

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
                    try:
                        await _emit_run_log(
                            run_id,
                            node=name,
                            input=node_input,
                            output={
                                "error": {"message": str(e), "type": type(e).__name__}
                            },
                            duration_ms=duration_ms,
                            error={"message": str(e), "type": type(e).__name__},
                        )
                    except Exception:
                        logger.debug(
                            "Failed to emit node end log (error): %s (runId=%s)",
                            name,
                            run_id,
                            exc_info=True,
                        )

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

    # NormalizeAgent (normalizes raw search results into top picks)
    graph.add_node(
        "NormalizeAgent",
        _wrap("NormalizeAgent", normalize_agent.execute, pass_deps_kwarg=False),
    )

    # EnrichAgent (2-phase enrichment with LLM queries + domain filtering)
    graph.add_node(
        "EnrichAgent",
        _wrap("EnrichAgent", enrichment_agent.execute, pass_deps_kwarg=False),
    )

    # QualitySplit (pure logic — main vs references)
    graph.add_node(
        "QualitySplit",
        _wrap("QualitySplit", quality_split, pass_deps_kwarg=True),
    )

    # ReportWriter (synthesize itinerary + budget)
    graph.add_node(
        "ReportWriter",
        _wrap("ReportWriter", report_writer.execute, pass_deps_kwarg=False),
    )

    # =========================================================================
    # GRAPH STRUCTURE
    # =========================================================================

    graph.set_entry_point("ParseRequest")

    # Parallel fan-out: All 4 domain agents start after ParseRequest
    graph.add_edge("ParseRequest", "RestaurantAgent")
    graph.add_edge("ParseRequest", "AttractionsAgent")
    graph.add_edge("ParseRequest", "HotelAgent")
    graph.add_edge("ParseRequest", "TransportAgent")

    # Join pattern: NormalizeAgent waits for all 4 domain agents
    graph.add_edge("RestaurantAgent", "NormalizeAgent")
    graph.add_edge("AttractionsAgent", "NormalizeAgent")
    graph.add_edge("HotelAgent", "NormalizeAgent")
    graph.add_edge("TransportAgent", "NormalizeAgent")

    # Conditional edge 1: enrichment toggle
    def normalize_router(state: dict[str, Any]) -> str:
        if state.get("skip_enrichment"):
            return "QualitySplit"
        return "EnrichAgent"

    graph.add_conditional_edges("NormalizeAgent", normalize_router, {
        "EnrichAgent": "EnrichAgent",
        "QualitySplit": "QualitySplit",
    })

    # Conditional edge 2: enrichment quality loop
    def enrichment_router(state: dict[str, Any]) -> str:
        ratio = state.get("enrichment_gap_ratio", 0.0)
        loops = state.get("enrichment_loop_count", 0)
        if ratio > 0.5 and loops < 2:
            return "EnrichAgent"
        return "QualitySplit"

    graph.add_conditional_edges("EnrichAgent", enrichment_router, {
        "EnrichAgent": "EnrichAgent",
        "QualitySplit": "QualitySplit",
    })

    # QualitySplit → ReportWriter → END
    graph.add_edge("QualitySplit", "ReportWriter")
    graph.add_edge("ReportWriter", END)

    return graph.compile()
