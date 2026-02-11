"""Tests for API endpoint error handling and data logging."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def app_no_mongo():
    """App with no MongoDB configured (deps.mongo = None)."""
    app = create_app()
    with TestClient(app) as client:
        # Ensure mongo is None
        app.state.deps.mongo = None
        yield client, app


@pytest.fixture
def app_with_mongo():
    """App with mocked MongoDB."""
    app = create_app()
    with TestClient(app) as client:
        mongo = AsyncMock()
        mongo.get_run = AsyncMock(return_value=None)
        mongo.create_run = AsyncMock()
        mongo.append_event = AsyncMock()
        mongo.set_node_progress = AsyncMock()
        app.state.deps.mongo = mongo
        yield client, app, mongo


class TestCreateRun:
    def test_422_no_prompt_or_constraints(self, app_with_mongo):
        client, app, mongo = app_with_mongo
        resp = client.post("/api/runs", json={})
        assert resp.status_code == 422

    def test_500_no_mongo(self, app_no_mongo):
        client, app = app_no_mongo
        resp = client.post("/api/runs", json={
            "constraints": {
                "origin": "Tokyo",
                "destination": "Seoul",
                "departing_date": "2026-03-01"
            }
        })
        assert resp.status_code == 500
        assert "MongoDB" in resp.json()["detail"]

    def test_creates_run_calls_mongo(self, app_with_mongo):
        client, app, mongo = app_with_mongo
        resp = client.post("/api/runs", json={
            "constraints": {
                "origin": "Tokyo",
                "destination": "Seoul",
                "departing_date": "2026-03-01"
            }
        })
        assert resp.status_code == 200
        assert "runId" in resp.json()
        mongo.create_run.assert_called_once()
        # Verify append_event called for queue event
        mongo.append_event.assert_called()


class TestGetRun:
    def test_404_nonexistent_run(self, app_with_mongo):
        client, app, mongo = app_with_mongo
        mongo.get_run = AsyncMock(return_value=None)
        resp = client.get("/api/runs/nonexistent-id")
        assert resp.status_code == 404

    def test_500_no_mongo(self, app_no_mongo):
        client, app = app_no_mongo
        resp = client.get("/api/runs/some-id")
        assert resp.status_code == 500
        assert "MongoDB" in resp.json()["detail"]

    def test_returns_run(self, app_with_mongo):
        client, app, mongo = app_with_mongo
        mongo.get_run = AsyncMock(return_value={
            "_id": "r1",
            "status": "done",
            "updatedAt": datetime.now(timezone.utc),
            "progress": None,
            "constraints": {"origin": "Tokyo"},
            "final_output": {"restaurants": []},
            "warnings": [],
            "error": None,
            "durationMs": 5000,
        })
        resp = client.get("/api/runs/r1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["runId"] == "r1"
        assert data["status"] == "done"


class TestCancelRun:
    def test_returns_ok_even_if_not_found(self):
        app = create_app()
        with TestClient(app) as client:
            resp = client.post("/api/runs/nonexistent/cancel")
            assert resp.status_code == 200
            assert resp.json() == {"ok": True}


class TestExportPdf:
    def test_400_if_not_completed(self, app_with_mongo):
        client, app, mongo = app_with_mongo
        mongo.get_run = AsyncMock(return_value={
            "_id": "r1",
            "status": "running",
            "updatedAt": datetime.now(timezone.utc),
        })
        resp = client.get("/api/runs/r1/export/pdf")
        assert resp.status_code == 400
        assert "not completed" in resp.json()["detail"]


class TestExportXlsx:
    def test_404_if_not_found(self, app_with_mongo):
        client, app, mongo = app_with_mongo
        mongo.get_run = AsyncMock(return_value=None)
        resp = client.get("/api/runs/r1/export/xlsx")
        assert resp.status_code == 404
