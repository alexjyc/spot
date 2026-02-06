from fastapi.testclient import TestClient

from app.main import create_app


def test_settings_available_on_deps():
    app = create_app()
    with TestClient(app):
        deps = app.state.deps
        settings = deps.settings

        assert isinstance(settings.openai_timeout, int)
        assert isinstance(settings.tavily_search_timeout, int)
        assert isinstance(settings.tavily_extract_timeout, int)
