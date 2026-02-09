import pytest

from app.graph.nodes.parse import parse_request
from app.schemas.spot_on import LocationNormalization


@pytest.mark.asyncio
async def test_parse_request_requires_constraints():
    with pytest.raises(ValueError, match="constraints are required"):
        await parse_request({"runId": "r1"}, deps=None)


@pytest.mark.asyncio
async def test_parse_request_validates_and_derives_query_context():
    state = {
        "runId": "r1",
        "constraints": {
            "origin": "Paris (CDG)",
            "destination": "Singapore (SIN)",
            "departing_date": "2026-02-10",
            "returning_date": "2026-02-12",
        },
    }
    out = await parse_request(state, deps=None)

    assert out["constraints"]["origin"] == "Paris (CDG)"
    assert out["constraints"]["destination"] == "Singapore (SIN)"
    assert out["constraints"]["departing_date"] == "2026-02-10"
    assert out["constraints"]["returning_date"] == "2026-02-12"

    ctx = out["query_context"]
    assert ctx["trip_type"] == "round-trip"
    assert ctx["origin_city"] == "Paris"
    assert ctx["destination_city"] == "Singapore"
    assert ctx["origin_code"] == "CDG"
    assert ctx["destination_code"] == "SIN"
    assert ctx["depart_year"] == 2026
    assert ctx["stay_nights"] == 2


@pytest.mark.asyncio
async def test_parse_request_uses_llm_location_normalization_for_query_context(mock_deps):
    mock_deps.llm.structured.return_value = LocationNormalization(
        origin_city="San Francisco, CA",
        destination_city="Tokyo",
        origin_code="SFO",
        destination_code=None,
        confidence="high",
    )

    state = {
        "runId": "r1",
        "constraints": {
            "origin": "SF",
            "destination": "Tokyo",
            "departing_date": "2026-02-10",
            "returning_date": None,
        },
    }
    out = await parse_request(state, deps=mock_deps)

    # Raw constraints stay as user input (only validated).
    assert out["constraints"]["origin"] == "SF"
    assert out["constraints"]["destination"] == "Tokyo"

    ctx = out["query_context"]
    assert ctx["trip_type"] == "one-way"
    assert ctx["stay_nights"] is None
    assert ctx["origin_city"] == "San Francisco, CA"
    assert ctx["origin_code"] == "SFO"
    assert ctx["destination_city"] == "Tokyo"
    assert ctx["destination_code"] is None
