from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.exports import router as exports_router
from app.api.health import router as health_router
from app.api.runs import router as runs_router
from app.config import Settings, get_settings
from app.db.mongo import MongoService
from app.graph.graph import build_graph
from app.services.llm import LLMService
from app.services.tavily import TavilyService


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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.parsed_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(runs_router)
    app.include_router(exports_router)

    return app


app = create_app()
