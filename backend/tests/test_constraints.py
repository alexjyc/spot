from app.schemas.spot_on import TravelConstraints


def test_constraints_validate_roundtrip_ok():
    c = TravelConstraints.model_validate(
        {
            "origin": "Paris (CDG)",
            "destination": "Singapore (SIN)",
            "departing_date": "2026-02-10",
            "returning_date": "2026-02-12",
        }
    )
    assert c.budget == "moderate"
    assert c.interests == []


def test_constraints_reject_return_before_depart():
    try:
        TravelConstraints.model_validate(
            {
                "origin": "Paris",
                "destination": "Singapore",
                "departing_date": "2026-02-10",
                "returning_date": "2026-02-09",
            }
        )
    except Exception as e:
        assert "returning_date" in str(e)
    else:
        raise AssertionError("Expected validation to fail")

