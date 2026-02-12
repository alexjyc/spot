import pytest

from app.graph.nodes.quality_split import quality_split


class TestQualitySplit:
    async def test_splits_complete_vs_incomplete(self, mock_deps):
        state = {
            "runId": "r1",
            "restaurants": [
                {"id": "r1", "name": "Sushi Place", "url": "https://a.com", "cuisine": "Japanese", "price_range": "$$"},
                {"id": "r2", "name": "Incomplete", "url": "https://b.com", "cuisine": None, "price_range": None},
            ],
            "travel_spots": [],
            "hotels": [],
            "car_rentals": [],
            "flights": [],
            "enriched_data": {},
            "references": [],
        }
        result = await quality_split(state, deps=mock_deps)

        assert len(result["main_results"]["restaurants"]) == 1
        assert result["main_results"]["restaurants"][0]["name"] == "Sushi Place"
        # Incomplete items are demoted to references
        assert any(r.get("name") == "Incomplete" for r in result["references"])

    async def test_merges_enriched_data(self, mock_deps):
        state = {
            "runId": "r1",
            "restaurants": [
                {"id": "r1", "name": "Place", "url": "https://a.com", "cuisine": None, "price_range": None},
            ],
            "travel_spots": [],
            "hotels": [],
            "car_rentals": [],
            "flights": [],
            "enriched_data": {
                "r1": {"cuisine": "Italian", "price_range": "$$$"},
            },
            "references": [],
        }
        result = await quality_split(state, deps=mock_deps)

        # After enrichment merge, the restaurant should qualify as main
        assert len(result["main_results"]["restaurants"]) == 1
        assert result["main_results"]["restaurants"][0]["cuisine"] == "Italian"

    async def test_handles_empty_categories(self, mock_deps):
        state = {
            "runId": "r1",
            "restaurants": [],
            "travel_spots": [],
            "hotels": [],
            "car_rentals": [],
            "flights": [],
            "enriched_data": {},
            "references": [],
        }
        result = await quality_split(state, deps=mock_deps)
        for cat in ["restaurants", "travel_spots", "hotels", "car_rentals", "flights"]:
            assert result["main_results"][cat] == []

    async def test_preserves_existing_references(self, mock_deps):
        state = {
            "runId": "r1",
            "restaurants": [],
            "travel_spots": [],
            "hotels": [],
            "car_rentals": [],
            "flights": [],
            "enriched_data": {},
            "references": [{"url": "https://example.com", "section": "restaurant", "title": "Existing"}],
        }
        result = await quality_split(state, deps=mock_deps)
        assert len(result["references"]) == 1
        assert result["references"][0]["title"] == "Existing"

    async def test_car_rentals_use_provider_field(self, mock_deps):
        state = {
            "runId": "r1",
            "restaurants": [],
            "travel_spots": [],
            "hotels": [],
            "car_rentals": [
                {"id": "c1", "provider": "Hertz", "url": "https://hertz.com", "price_per_day": "$50"},
            ],
            "flights": [],
            "enriched_data": {},
            "references": [],
        }
        result = await quality_split(state, deps=mock_deps)
        assert len(result["main_results"]["car_rentals"]) == 1
