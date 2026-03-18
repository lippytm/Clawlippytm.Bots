"""Tests for clawlippytm_bots.utils."""

from __future__ import annotations

from urllib.parse import urlparse

from clawlippytm_bots.utils import (
    build_session,
    is_same_domain,
    load_json,
    normalise_url,
    safe_filename,
    save_json,
)


class TestBuildSession:
    def test_returns_session(self):
        session = build_session()
        import requests
        assert isinstance(session, requests.Session)

    def test_custom_user_agent(self):
        session = build_session(user_agent="TestBot/1.0")
        assert session.headers["User-Agent"] == "TestBot/1.0"

    def test_default_user_agent_contains_clawlippytm(self):
        session = build_session()
        assert "Clawlippytm" in session.headers["User-Agent"]

    def test_timeout_attribute_set(self):
        session = build_session(timeout=15)
        assert session.timeout == 15


class TestNormaliseUrl:
    def test_lowercase_scheme(self):
        assert normalise_url("HTTP://Example.COM/") == "http://example.com/"

    def test_lowercase_host(self):
        assert normalise_url("https://EXAMPLE.COM/page") == "https://example.com/page"

    def test_strips_fragment(self):
        assert "#section" not in normalise_url("https://example.com/#section")

    def test_preserves_fragment_when_disabled(self):
        result = normalise_url("https://example.com/#section", strip_fragment=False)
        assert "#section" in result

    def test_sorts_query_params(self):
        url_a = normalise_url("https://example.com/?z=1&a=2")
        url_b = normalise_url("https://example.com/?a=2&z=1")
        assert url_a == url_b

    def test_empty_path_becomes_slash(self):
        result = normalise_url("https://example.com")
        parsed = urlparse(result)
        assert parsed.netloc == "example.com"


class TestIsSameDomain:
    def test_same_domain(self):
        assert is_same_domain("https://example.com/page", "https://example.com/")

    def test_different_domain(self):
        assert not is_same_domain("https://other.com/page", "https://example.com/")

    def test_case_insensitive(self):
        assert is_same_domain("https://EXAMPLE.COM/page", "https://example.com/")


class TestSafeFilename:
    def test_simple_path(self):
        result = safe_filename("https://example.com/about")
        assert "about" in result

    def test_nested_path(self):
        result = safe_filename("https://example.com/blog/post-1")
        assert "blog" in result
        assert "post" in result

    def test_empty_path_returns_default(self):
        assert safe_filename("https://example.com/", default="index.html") == "index.html"

    def test_no_forbidden_chars(self):
        result = safe_filename("https://example.com/path?query=1&x=2")
        # Should not contain characters that are unsafe for filenames
        for ch in ("?", "&", "=", "/"):
            assert ch not in result


class TestSaveAndLoadJson:
    def test_round_trip(self, tmp_path):
        data = {"key": "value", "nums": [1, 2, 3]}
        dest = tmp_path / "data.json"
        save_json(data, dest)
        loaded = load_json(dest)
        assert loaded == data

    def test_creates_parent_dirs(self, tmp_path):
        dest = tmp_path / "a" / "b" / "c.json"
        save_json({"x": 1}, dest)
        assert dest.exists()

    def test_load_missing_returns_none(self, tmp_path):
        result = load_json(tmp_path / "nonexistent.json")
        assert result is None

    def test_json_is_pretty_printed(self, tmp_path):
        dest = tmp_path / "pretty.json"
        save_json({"a": 1}, dest)
        content = dest.read_text()
        assert "\n" in content  # pretty-printed
