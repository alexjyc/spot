from fastapi.testclient import TestClient

from app.main import create_app


def test_settings_supports_dict_and_attrs():
    app = create_app()
    with TestClient(app):
        deps = app.state.deps
        settings = deps.settings

        assert isinstance(settings.get("TAVILY_SEARCH_MAX"), int)
        assert isinstance(settings.get("TAVILY_EXTRACT_CONTENT_CHAR_CAP"), int)

        # Nodes rely on attribute access for timeouts.
        assert isinstance(settings.allocator_timeout, int)
        assert isinstance(settings.day_planner_timeout, int)
        assert isinstance(settings.geo_enrich_timeout, int)

