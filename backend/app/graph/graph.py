import logging
from typing import Any, Callable, Coroutine

from langgraph.graph import END, StateGraph

from app.agents.attractions import AttractionsAgent
from app.agents.enrichment import EnrichmentAgent
from app.agents.hotel import HotelAgent
from app.agents.budget import BudgetAgent
from app.agents.restaurant import RestaurantAgent
from app.agents.transport import TransportAgent
from app.graph.nodes.parse import parse_request
from app.graph.nodes.quality_split import quality_split
from app.graph.state import SpotOnState

logger = logging.getLogger(__name__)


def build_graph(deps: Any):
    graph = StateGraph(SpotOnState)
    restaurant_agent = RestaurantAgent("restaurant_agent", deps)
    attractions_agent = AttractionsAgent("attractions_agent", deps)
    hotel_agent = HotelAgent("hotel_agent", deps)
    transport_agent = TransportAgent("transport_agent", deps)
    enrichment_agent = EnrichmentAgent("enrichment_agent", deps)
    budget_agent = BudgetAgent("budget_agent", deps)

    async def _emit_node_event(
        run_id: str,
        *,
        node: str,
        status: str,
        message: str,
        error: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {"node": node, "status": status, "message": message}
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
        error: dict[str, Any] | None = None,
    ) -> None:
        await deps.mongo.append_node_end_log(
            run_id,
            node=node,
            input=input,
            output=output,
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
            logger.info("Graph node start: %s (runId=%s)", name, run_id or "-")
            node_input: dict[str, Any] = {
                "runId": state.get("runId"),
                "status": state.get("status"),
                "agent_statuses": state.get("agent_statuses"),
            }

            if run_id:
                await _emit_node_event(
                    run_id,
                    node=name,
                    status="start",
                    message=f"{name} started",
                )

            try:
                out = await (fn(state, deps=deps) if pass_deps_kwarg else fn(state))
                logger.info("Graph node end: %s (runId=%s)", name, run_id or "-")

                if run_id:
                    try:
                        await _emit_run_log(
                            run_id,
                            node=name,
                            input=node_input,
                            output=out,
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
                    )

                    if name == "ParseRequest" and out.get("constraints"):
                        await deps.mongo.add_artifact(
                            run_id,
                            type="constraints",
                            payload={"constraints": out.get("constraints")},
                        )

                return out

            except Exception as e:
                logger.exception("Node failed: %s", name)
                logger.error(
                    "Graph node error: %s (runId=%s, error=%s)",
                    name,
                    run_id or "-",
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
                        error=str(e),
                    )
                return {
                    "agent_statuses": {name: "failed"},
                    "warnings": [f"{name} failed: {e}"],
                }

        return _inner

    # =========================================================================
    # NODES
    # =========================================================================
    graph.add_node("ParseRequest", _wrap("ParseRequest", parse_request, pass_deps_kwarg=True))

    # Domain agents
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

    # EnrichAgent
    graph.add_node(
        "EnrichAgent",
        _wrap("EnrichAgent", enrichment_agent.execute, pass_deps_kwarg=False),
    )

    # QualitySplit
    graph.add_node(
        "QualitySplit",
        _wrap("QualitySplit", quality_split, pass_deps_kwarg=True),
    )

    # BudgetAgent
    graph.add_node(
        "BudgetAgent",
        _wrap("BudgetAgent", budget_agent.execute, pass_deps_kwarg=False),
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

    # Join: all 4 domain agents → enrichment or skip to QualitySplit
    def domain_router(state: dict[str, Any]) -> str:
        if state.get("skip_enrichment"):
            return "QualitySplit"
        return "EnrichAgent"

    graph.add_conditional_edges("RestaurantAgent", domain_router, {
        "EnrichAgent": "EnrichAgent",
        "QualitySplit": "QualitySplit",
    })
    graph.add_conditional_edges("AttractionsAgent", domain_router, {
        "EnrichAgent": "EnrichAgent",
        "QualitySplit": "QualitySplit",
    })
    graph.add_conditional_edges("HotelAgent", domain_router, {
        "EnrichAgent": "EnrichAgent",
        "QualitySplit": "QualitySplit",
    })
    graph.add_conditional_edges("TransportAgent", domain_router, {
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

    # QualitySplit → BudgetAgent → END
    graph.add_edge("QualitySplit", "BudgetAgent")
    graph.add_edge("BudgetAgent", END)

    return graph.compile()
