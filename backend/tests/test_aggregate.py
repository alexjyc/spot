"""Tests for the aggregate results graph node."""

from __future__ import annotations

import logging

import pytest

from app.graph.nodes.aggregate_results import aggregate_results


class TestAggregateResults:
    async def test_merges_enriched_data(self, mock_deps):
        state = {
            "runId": "r1",
            "restaurants": [{"id": "r1", "name": "Sushi Place"}],
            "travel_spots": [],
            "hotels": [],
            "car_rentals": [],
            "flights": [],
            "enriched_data": {
                "r1": {"price_hint": "$$$", "address": "123 Main St"},
            },
            "constraints": {"origin": "Tokyo", "destination": "Seoul"},
        }
        result = await aggregate_results(state, deps=mock_deps)

        restaurant = result["final_output"]["restaurants"][0]
        assert restaurant["price_hint"] == "$$$"
        assert restaurant["address"] == "123 Main St"
        assert restaurant["name"] == "Sushi Place"

    async def test_handles_missing_enriched_data(self, mock_deps):
        state = {
            "runId": "r1",
            "restaurants": [{"id": "r1", "name": "Place"}],
            "travel_spots": [],
            "hotels": [],
            "car_rentals": [],
            "flights": [],
            "enriched_data": {},
            "constraints": {},
        }
        result = await aggregate_results(state, deps=mock_deps)
        # No enrichment applied, original data unchanged
        assert result["final_output"]["restaurants"][0]["name"] == "Place"
        assert "price_hint" not in result["final_output"]["restaurants"][0]

    async def test_handles_empty_categories(self, mock_deps):
        state = {
            "runId": "r1",
            "restaurants": [],
            "travel_spots": [],
            "hotels": [],
            "car_rentals": [],
            "flights": [],
            "enriched_data": {},
            "constraints": {},
        }
        result = await aggregate_results(state, deps=mock_deps)
        for cat in ["restaurants", "travel_spots", "hotels", "car_rentals", "flights"]:
            assert result["final_output"][cat] == []

    async def test_returns_done_status(self, mock_deps, sample_state):
        result = await aggregate_results(sample_state, deps=mock_deps)
        assert result["status"] == "done"

    async def test_final_output_includes_constraints(self, mock_deps, sample_state):
        result = await aggregate_results(sample_state, deps=mock_deps)
        assert "constraints" in result["final_output"]
        assert result["final_output"]["constraints"] == sample_state["constraints"]

    async def test_final_output_has_all_categories(self, mock_deps, sample_state):
        result = await aggregate_results(sample_state, deps=mock_deps)
        for cat in ["restaurants", "travel_spots", "hotels", "car_rentals", "flights"]:
            assert cat in result["final_output"]

    async def test_logs_total_count(self, mock_deps, caplog):
        state = {
            "runId": "r1",
            "restaurants": [{"id": "1", "name": "A"}, {"id": "2", "name": "B"}],
            "travel_spots": [{"id": "3", "name": "C"}],
            "hotels": [],
            "car_rentals": [],
            "flights": [],
            "enriched_data": {},
            "constraints": {},
        }
        with caplog.at_level(logging.INFO):
            await aggregate_results(state, deps=mock_deps)
        assert any("3 total results" in r.message for r in caplog.records)
