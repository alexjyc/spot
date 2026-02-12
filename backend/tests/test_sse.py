import json

from app.utils.sse import sse_event


class TestSseEvent:
    def test_correct_format(self):
        result = sse_event("node", {"status": "start"})
        text = result.decode("utf-8")
        assert text.startswith("event: node\n")
        assert "data: " in text
        assert text.endswith("\n\n")

    def test_utf8_encoding(self):
        result = sse_event("log", {"message": "日本語テスト"})
        assert isinstance(result, bytes)
        text = result.decode("utf-8")
        assert "日本語テスト" in text

    def test_json_no_spaces(self):
        result = sse_event("test", {"key": "value", "num": 42})
        text = result.decode("utf-8")
        data_line = [l for l in text.split("\n") if l.startswith("data: ")][0]
        json_str = data_line[len("data: "):]
        # Verify compact JSON (no spaces after separators)
        assert ": " not in json_str
        assert ", " not in json_str
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert parsed["key"] == "value"
        assert parsed["num"] == 42

    def test_ensure_ascii_false(self):
        result = sse_event("test", {"emoji": "café"})
        text = result.decode("utf-8")
        # With ensure_ascii=False, non-ASCII chars should appear directly
        assert "café" in text
        assert "\\u" not in text
