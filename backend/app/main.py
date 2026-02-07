from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pymongo.errors import PyMongoError

from app.config import Settings, get_settings
from app.db.mongo import MongoService
from app.db.schemas import RunCreateRequest, RunCreateResponse, RunGetResponse
from app.graph.graph import build_graph
from app.services.llm import LLMService
from app.services.tavily import TavilyService
from app.utils.ids import new_run_id
from app.utils.sse import sse_event


def create_app() -> FastAPI:
    settings = get_settings()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        deps = SimpleNamespace()
        deps.settings = settings
        deps.mongo = None
        deps.llm = None
        deps.tavily = None
        deps.graph = None

        app.state.background_tasks = {}

        try:
            if settings.mongodb_uri:
                deps.mongo = MongoService(settings.mongodb_uri, settings.db_name)
                await deps.mongo.ping()
                await deps.mongo.ensure_indexes()
        except Exception as e:
            logging.getLogger(__name__).error("Mongo init failed: %s", e)

        try:
            if settings.openai_api_key:
                deps.llm = LLMService(
                    settings.openai_api_key,
                    settings.openai_model,
                    timeout_seconds=float(settings.openai_timeout),
                )
        except Exception as e:
            logging.getLogger(__name__).error("OpenAI init failed: %s", e)

        try:
            if settings.tavily_api_key:
                deps.tavily = TavilyService(
                    settings.tavily_api_key,
                    search_timeout_seconds=float(settings.tavily_search_timeout),
                    extract_timeout_seconds=float(settings.tavily_extract_timeout),
                )
        except Exception as e:
            logging.getLogger(__name__).error("Tavily init failed: %s", e)

        if deps.mongo and deps.llm and deps.tavily:
            deps.graph = build_graph(deps)

        app.state.deps = deps

        try:
            yield
        finally:
            tasks = list((app.state.background_tasks or {}).values())
            for t in tasks:
                t.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            if getattr(deps, "mongo", None):
                deps.mongo.close()

    app = FastAPI(title="Travel Planner API", version="0.1.0", lifespan=lifespan)

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
            await mongo.append_event(
                run_id,
                type="node",
                node="Queue",
                payload={"node": "Queue", "status": "end", "message": "Dequeued"},
            )
            await mongo.set_node_progress(
                run_id,
                node="Queue",
                payload={"node": "Queue", "status": "end", "message": "Dequeued"},
            )
            await mongo.append_event(run_id, type="log", payload={"message": "Run started"})

            graph = deps.graph
            run_doc = await mongo.get_run(run_id)
            if not run_doc:
                raise RuntimeError("Run not found")

            options = run_doc.get("options") or {}
            initial_state = {
                "runId": run_id,
                "prompt": run_doc.get("prompt"),
                "status": "running",
                "agent_statuses": {},
                "warnings": [],
                "constraints": run_doc.get("constraints") or {},
                "skip_enrichment": bool(options.get("skip_enrichment")),
            }

            final_state = await graph.ainvoke(initial_state)

            constraints = final_state.get("constraints")
            final_output = final_state.get("final_output")
            warnings = final_state.get("warnings") or []

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
            await mongo.append_event(run_id, type="log", payload={"message": "Run completed"})
        except Exception as e:
            logging.getLogger(__name__).exception("Run failed: %s", run_id)
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.parsed_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def root() -> dict:
        return {"ok": True}

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/api/runs", response_model=RunCreateResponse)
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
        await mongo.set_node_progress(
            run_id,
            node="Queue",
            payload={"node": "Queue", "status": "start", "message": "Queued"},
        )

        task = asyncio.create_task(_execute_run(deps, run_id))
        request.app.state.background_tasks[run_id] = task
        return RunCreateResponse(runId=run_id)

    @app.get("/api/runs/{runId}", response_model=RunGetResponse)
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
            progress=doc.get("progress"),
            constraints=doc.get("constraints"),
            final_output=doc.get("final_output"),
            warnings=doc.get("warnings") or [],
            error=doc.get("error"),
            durationMs=doc.get("durationMs"),
        )

    @app.get("/api/runs/{runId}/events")
    async def run_events(runId: str, request: Request):
        deps = getattr(request.app.state, "deps", None)
        mongo = getattr(deps, "mongo", None) if deps else None
        if not mongo:
            raise HTTPException(status_code=500, detail="MongoDB is not configured")

        terminal_messages = {"Run completed", "Run failed"}

        def _format_event(ev: dict[str, Any]) -> bytes:
            etype = ev.get("type") or "log"
            payload = ev.get("payload") or {}
            if etype == "artifact":
                return sse_event("artifact", payload)
            if etype == "node":
                return sse_event("node", payload)
            return sse_event("log", payload)

        async def _gen():
            seen_ids: set[Any] = set()
            idle = 0

            try:
                pipeline = [
                    {
                        "$match": {
                            "operationType": "insert",
                            "fullDocument.runId": runId,
                        }
                    }
                ]

                async with mongo.run_events.watch(
                    pipeline,
                    full_document="default",
                    max_await_time_ms=1000,
                ) as stream:
                    # Backlog first so clients that connect late still get earlier events.
                    cursor_ts = _epoch()
                    cursor_id = None
                    saw_terminal = False
                    while True:
                        events = await mongo.list_events_since_cursor(
                            runId, since_ts=cursor_ts, since_id=cursor_id
                        )
                        if not events:
                            break
                        for ev in events:
                            cursor_ts = ev["ts"]
                            cursor_id = ev.get("_id")
                            if cursor_id is not None:
                                seen_ids.add(cursor_id)
                            payload = ev.get("payload") or {}
                            if ev.get("type") == "log" and payload.get("message") in terminal_messages:
                                saw_terminal = True
                            yield _format_event(ev)

                    if saw_terminal:
                        return

                    while True:
                        if await request.is_disconnected():
                            return

                        change = await stream.try_next()
                        if change is None:
                            idle += 1
                            if idle >= 5:
                                run = await mongo.get_run(runId)
                                if run and run.get("status") in {"done", "error"}:
                                    return
                            continue

                        idle = 0
                        doc = (change.get("fullDocument") or {}) if isinstance(change, dict) else {}
                        ev_id = doc.get("_id")
                        if ev_id is not None and ev_id in seen_ids:
                            continue
                        if ev_id is not None:
                            seen_ids.add(ev_id)

                        payload = doc.get("payload") or {}
                        if doc.get("type") == "log" and payload.get("message") in terminal_messages:
                            yield _format_event(doc)
                            return

                        yield _format_event(doc)

            except PyMongoError:
                # Fallback for local/standalone Mongo where change streams aren't available.
                cursor_ts = _epoch()
                cursor_id = None
                idle = 0
                try:
                    while True:
                        if await request.is_disconnected():
                            return
                        events = await mongo.list_events_since_cursor(
                            runId, since_ts=cursor_ts, since_id=cursor_id
                        )
                        if events:
                            idle = 0
                            for ev in events:
                                cursor_ts = ev["ts"]
                                cursor_id = ev.get("_id")
                                yield _format_event(ev)
                        else:
                            idle += 1
                            run = await mongo.get_run(runId)
                            if run and run.get("status") in {"done", "error"} and idle >= 6:
                                return
                            await asyncio.sleep(0.5)
                except asyncio.CancelledError:
                    return

        return StreamingResponse(
            _gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return app


app = create_app()
