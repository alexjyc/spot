from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.db.schemas import RunCreateRequest, RunCreateResponse, RunGetResponse
from app.utils.ids import new_run_id
from app.utils.sse import sse_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def _epoch() -> datetime:
    return datetime.fromtimestamp(0, tz=timezone.utc)


async def _execute_run(deps: Any, run_id: str) -> None:
    mongo = getattr(deps, "mongo", None)
    t0 = time.monotonic()
    try:
        if not mongo:
            raise RuntimeError("MongoDB not configured")
        if not getattr(deps, "llm", None):
            raise RuntimeError("OpenAI not configured (missing OPENAI_API_KEY)")
        if not getattr(deps, "tavily", None):
            raise RuntimeError("Tavily not configured (missing TAVILY_API_KEY)")
        if not getattr(deps, "graph", None):
            raise RuntimeError("Workflow not initialized")

        await mongo.update_run(run_id, {"status": "running"})
        await mongo.append_event(run_id, type="log", payload={"message": "Run started"})

        # Use Spot On graph (new system)
        graph = deps.graph
        run_doc = await mongo.get_run(run_id)
        if not run_doc:
            raise RuntimeError("Run not found")

        # Initial state for Spot On
        initial_state = {
            "runId": run_id,
            "prompt": run_doc.get("prompt"),
            "status": "running",
            "agent_statuses": {},
            "warnings": [],
            "constraints": run_doc.get("constraints") or {},
        }

        final_state = await graph.ainvoke(initial_state)

        constraints = final_state.get("constraints")
        final_output = final_state.get("final_output")
        warnings = final_state.get("warnings") or []

        # Store final output artifact if present
        if final_output:
            await mongo.add_artifact(
                run_id, type="final_output", payload={"final_output": final_output}
            )

        await mongo.update_run(
            run_id,
            {
                "status": "done",
                "durationMs": int((time.monotonic() - t0) * 1000),
                "constraints": constraints,
                "warnings": warnings,
                "final_output": final_output,
                "error": None,
            },
        )
        await mongo.append_event(
            run_id, type="log", payload={"message": "Run completed"}
        )
    except Exception as e:
        logger.exception("Run failed: %s", run_id)
        if mongo:
            await mongo.update_run(
                run_id,
                {
                    "status": "error",
                    "durationMs": int((time.monotonic() - t0) * 1000),
                    "error": {"message": str(e)},
                },
            )
            await mongo.append_event(
                run_id, type="log", payload={"message": "Run failed", "error": str(e)}
            )


@router.post("/runs", response_model=RunCreateResponse)
async def create_run(req: RunCreateRequest, request: Request) -> RunCreateResponse:
    deps = getattr(request.app.state, "deps", None)
    mongo = getattr(deps, "mongo", None) if deps else None
    if not mongo:
        raise HTTPException(status_code=500, detail="MongoDB is not configured")

    run_id = new_run_id()
    options = dict(req.options or {})
    await mongo.create_run(
        run_id,
        prompt=req.prompt,
        constraints=req.constraints,
        options=options,
    )
    await mongo.append_event(
        run_id,
        type="node",
        node="Queue",
        payload={"node": "Queue", "status": "start", "message": "Queued"},
    )

    task = asyncio.create_task(_execute_run(deps, run_id))
    request.app.state.background_tasks[run_id] = task
    return RunCreateResponse(runId=run_id)


@router.get("/runs/{runId}", response_model=RunGetResponse)
async def get_run(runId: str, request: Request) -> RunGetResponse:
    deps = getattr(request.app.state, "deps", None)
    mongo = getattr(deps, "mongo", None) if deps else None
    if not mongo:
        raise HTTPException(status_code=500, detail="MongoDB is not configured")
    doc = await mongo.get_run(runId)
    if not doc:
        raise HTTPException(status_code=404, detail="Run not found")

    return RunGetResponse(
        runId=doc["_id"],
        status=doc["status"],
        updatedAt=doc["updatedAt"],
        constraints=doc.get("constraints"),
        final_output=doc.get("final_output"),
        warnings=doc.get("warnings") or [],
        error=doc.get("error"),
        durationMs=doc.get("durationMs"),
    )


@router.get("/runs/{runId}/events")
async def run_events(runId: str, request: Request):
    deps = getattr(request.app.state, "deps", None)
    mongo = getattr(deps, "mongo", None) if deps else None
    if not mongo:
        raise HTTPException(status_code=500, detail="MongoDB is not configured")

    async def _gen():
        cursor_ts = _epoch()
        cursor_id = None
        idle = 0
        try:
            while True:
                if await request.is_disconnected():
                    break
                events = await mongo.list_events_since_cursor(
                    runId, since_ts=cursor_ts, since_id=cursor_id
                )
                if events:
                    idle = 0
                    for ev in events:
                        cursor_ts = ev["ts"]
                        cursor_id = ev.get("_id")
                        etype = ev.get("type") or "log"
                        payload = ev.get("payload") or {}
                        if etype == "artifact":
                            yield sse_event("artifact", payload)
                        elif etype == "node":
                            yield sse_event("node", payload)
                        else:
                            yield sse_event("log", payload)
                else:
                    idle += 1
                    # Stop after completion + brief idle to let final events flush.
                    run = await mongo.get_run(runId)
                    if run and run.get("status") in {"done", "error"} and idle >= 30:
                        break
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        _gen(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
