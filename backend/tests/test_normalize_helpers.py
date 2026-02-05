from app.graph.nodes.normalize import _ensure_ids, _fallback_candidates_from_raw


def test_ensure_ids_fills_missing_and_is_deterministic():
    items = [
        {"id": "", "name": "Place A", "url": "https://example.com/a?utm=1"},
        {"name": "Place B", "url": "https://example.com/b"},
    ]
    out1 = _ensure_ids(items, prefix="cand")
    out2 = _ensure_ids(items, prefix="cand")

    assert out1[0]["id"]
    assert out1[1]["id"]
    assert out1[0]["id"] != out1[1]["id"]

    assert out1[0]["id"] == out2[0]["id"]
    assert out1[1]["id"] == out2[1]["id"]


def test_ensure_ids_resolves_duplicate_ids():
    items = [
        {"id": "dup", "name": "Place A", "url": "https://example.com/a"},
        {"id": "dup", "name": "Place B", "url": "https://example.com/b"},
    ]
    out = _ensure_ids(items, prefix="cand")
    assert out[0]["id"] != out[1]["id"]
    assert out[0]["id"] == "dup"


def test_fallback_candidates_from_raw_search():
    raw = [
        {
            "query": "best coffee in Paris",
            "results": [
                {
                    "title": "Cafe A",
                    "url": "https://example.com/cafe-a",
                    "content": "Nice cafe.",
                }
            ],
        }
    ]
    candidates = _fallback_candidates_from_raw(raw)
    assert len(candidates) == 1
    assert candidates[0]["name"] == "Cafe A"
    assert candidates[0]["url"] == "https://example.com/cafe-a"


def test_fallback_candidates_uses_url_when_title_missing():
    raw = [
        {
            "query": "things to do",
            "results": [{"title": None, "url": "https://example.com/x", "content": None}],
        }
    ]
    candidates = _fallback_candidates_from_raw(raw)
    assert len(candidates) == 1
    assert candidates[0]["name"] in {"example.com", "https://example.com/x"}
    assert candidates[0]["url"] == "https://example.com/x"
