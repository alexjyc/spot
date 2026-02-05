from __future__ import annotations

import logging
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.exports import router as exports_router
from app.api.health import router as health_router
from app.api.runs import router as runs_router
from app.config import Settings, get_settings
from app.db.mongo import MongoService
from app.graph.graph import build_graph
from app.graph.graph import build_graph
from app.services.llm import LLMService
from app.services.tavily import TavilyService


class SettingsAdapter(dict):
    """
    Adapter that supports both dict-style `.get("ENV_KEY")` lookups and
    attribute-style access (e.g. `.allocator_timeout`) from `Settings`.

    Some nodes were written expecting a dict, others expecting a Settings object.
    This keeps the interface stable without touching every node.
    """

    def __init__(self, settings: Settings) -> None:
        super().__init__(
            {
                "OPENAI_TIMEOUT": settings.openai_timeout,
                "TAVILY_SEARCH_MAX": settings.tavily_search_max,
                "TAVILY_SEARCH_TIMEOUT": settings.tavily_search_timeout,
                "TAVILY_EXTRACT_TIMEOUT": settings.tavily_extract_timeout,
                "TAVILY_VERIFY_URL_CAP": settings.tavily_verify_url_cap,
                "TAVILY_SEARCH_CONTENT_CHAR_CAP": settings.tavily_search_content_char_cap,
                "TAVILY_EXTRACT_CONTENT_CHAR_CAP": settings.tavily_extract_content_char_cap,
                "TAVILY_VERIFY_INCLUDE_ALTERNATES": settings.tavily_verify_include_alternates,
                "GEO_ENRICH_URL_CAP": settings.geo_enrich_url_cap,
                "TOTAL_TIMEOUT": settings.total_timeout,
                "ALLOCATOR_TIMEOUT": settings.allocator_timeout,
                "DAY_PLANNER_TIMEOUT": settings.day_planner_timeout,
                "GEO_ENRICH_TIMEOUT": settings.geo_enrich_timeout,
            }
        )
        self._settings = settings

    def __getattr__(self, name: str):
        return getattr(self._settings, name)


def create_app() -> FastAPI:
    settings = get_settings()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = FastAPI(title="Travel Planner API", version="0.1.0")
    app.state.background_tasks = {}

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

    @app.on_event("startup")
    async def _startup() -> None:
        deps = SimpleNamespace()
        deps.settings = SettingsAdapter(settings)
        deps.mongo = None
        deps.llm = None
        deps.tavily = None
        deps.graph = None

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

    return app


app = create_app()
