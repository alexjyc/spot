"""Tests for dedup utility functions."""

from __future__ import annotations

from app.utils.dedup import canonicalize_url, domain, normalize_name


class TestNormalizeName:
    def test_basic(self):
        assert normalize_name("  Hello   World  ") == "hello world"

    def test_case_folding(self):
        assert normalize_name("UPPER") == "upper"

    def test_empty_string(self):
        assert normalize_name("") == ""

    def test_none_input(self):
        assert normalize_name(None) == ""

    def test_tabs_and_newlines(self):
        assert normalize_name("foo\t\nbar") == "foo bar"

    def test_already_clean(self):
        assert normalize_name("clean") == "clean"


class TestCanonicalizeUrl:
    def test_strips_query_params(self):
        result = canonicalize_url("https://example.com/page?utm_source=test&id=1")
        assert "?" not in result
        assert result == "https://example.com/page"

    def test_lowercases_netloc(self):
        result = canonicalize_url("https://EXAMPLE.COM/path")
        assert "example.com" in result

    def test_default_scheme(self):
        result = canonicalize_url("//example.com/path")
        assert result.startswith("https://")

    def test_preserves_path(self):
        result = canonicalize_url("https://example.com/some/path")
        assert "/some/path" in result

    def test_malformed_url_returns_original(self):
        # urlparse is quite lenient, but we test the fallback
        result = canonicalize_url("")
        assert isinstance(result, str)

    def test_adds_default_path(self):
        result = canonicalize_url("https://example.com")
        assert result == "https://example.com/"


class TestDomain:
    def test_extracts_domain(self):
        assert domain("https://www.example.com/path") == "www.example.com"

    def test_lowercases(self):
        assert domain("https://EXAMPLE.COM/path") == "example.com"

    def test_empty_url(self):
        assert domain("") == ""

    def test_no_scheme(self):
        # urlparse without scheme puts everything in path
        assert domain("example.com") == ""
