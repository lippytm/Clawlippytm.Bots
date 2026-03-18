"""Tests for clawlippytm_bots.scraper."""

from __future__ import annotations

import responses as responses_lib

from clawlippytm_bots.scraper import Scraper


_SIMPLE_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Test Page</title>
  <meta name="description" content="A test page">
  <meta name="keywords" content="test, scraper">
  <meta property="og:title" content="OG Title">
  <link rel="canonical" href="https://example.com/canonical">
  <link rel="stylesheet" href="/style.css">
</head>
<body>
  <h1>Hello</h1>
  <p>Some visible text here.</p>
  <a href="/about">About</a>
  <a href="https://external.com/page">External</a>
  <a href="mailto:test@example.com">Mail</a>
  <img src="/img/logo.png" alt="Logo">
  <script src="/js/app.js"></script>
</body>
</html>"""


@responses_lib.activate
def test_scrape_title():
    responses_lib.add(
        responses_lib.GET, "https://example.com/", body=_SIMPLE_HTML,
        content_type="text/html"
    )
    scraper = Scraper()
    result = scraper.scrape("https://example.com/")
    assert result["title"] == "Test Page"


@responses_lib.activate
def test_scrape_meta_description():
    responses_lib.add(
        responses_lib.GET, "https://example.com/", body=_SIMPLE_HTML,
        content_type="text/html"
    )
    result = Scraper().scrape("https://example.com/")
    assert result["description"] == "A test page"


@responses_lib.activate
def test_scrape_meta_keywords():
    responses_lib.add(
        responses_lib.GET, "https://example.com/", body=_SIMPLE_HTML,
        content_type="text/html"
    )
    result = Scraper().scrape("https://example.com/")
    assert result["keywords"] == "test, scraper"


@responses_lib.activate
def test_scrape_og_tags():
    responses_lib.add(
        responses_lib.GET, "https://example.com/", body=_SIMPLE_HTML,
        content_type="text/html"
    )
    result = Scraper().scrape("https://example.com/")
    assert result["og"].get("og:title") == "OG Title"


@responses_lib.activate
def test_scrape_canonical():
    responses_lib.add(
        responses_lib.GET, "https://example.com/", body=_SIMPLE_HTML,
        content_type="text/html"
    )
    result = Scraper().scrape("https://example.com/")
    assert result["canonical"] == "https://example.com/canonical"


@responses_lib.activate
def test_scrape_links_absolute():
    responses_lib.add(
        responses_lib.GET, "https://example.com/", body=_SIMPLE_HTML,
        content_type="text/html"
    )
    result = Scraper().scrape("https://example.com/")
    assert "https://example.com/about" in result["links"]
    assert "https://external.com/page" in result["links"]


@responses_lib.activate
def test_scrape_links_excludes_mailto():
    responses_lib.add(
        responses_lib.GET, "https://example.com/", body=_SIMPLE_HTML,
        content_type="text/html"
    )
    result = Scraper().scrape("https://example.com/")
    assert not any("mailto" in link for link in result["links"])


@responses_lib.activate
def test_scrape_images():
    responses_lib.add(
        responses_lib.GET, "https://example.com/", body=_SIMPLE_HTML,
        content_type="text/html"
    )
    result = Scraper().scrape("https://example.com/")
    assert "https://example.com/img/logo.png" in result["images"]


@responses_lib.activate
def test_scrape_scripts():
    responses_lib.add(
        responses_lib.GET, "https://example.com/", body=_SIMPLE_HTML,
        content_type="text/html"
    )
    result = Scraper().scrape("https://example.com/")
    assert "https://example.com/js/app.js" in result["scripts"]


@responses_lib.activate
def test_scrape_styles():
    responses_lib.add(
        responses_lib.GET, "https://example.com/", body=_SIMPLE_HTML,
        content_type="text/html"
    )
    result = Scraper().scrape("https://example.com/")
    assert "https://example.com/style.css" in result["styles"]


@responses_lib.activate
def test_scrape_text_contains_visible_text():
    responses_lib.add(
        responses_lib.GET, "https://example.com/", body=_SIMPLE_HTML,
        content_type="text/html"
    )
    result = Scraper().scrape("https://example.com/")
    assert "Hello" in result["text"]
    assert "Some visible text here" in result["text"]


@responses_lib.activate
def test_scrape_status_code():
    responses_lib.add(
        responses_lib.GET, "https://example.com/", body=_SIMPLE_HTML,
        status=200, content_type="text/html"
    )
    result = Scraper().scrape("https://example.com/")
    assert result["status_code"] == 200


@responses_lib.activate
def test_scrape_many():
    responses_lib.add(
        responses_lib.GET, "https://example.com/a", body="<title>A</title>",
        content_type="text/html"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/b", body="<title>B</title>",
        content_type="text/html"
    )
    scraper = Scraper()
    results = scraper.scrape_many(
        ["https://example.com/a", "https://example.com/b"]
    )
    assert len(results) == 2
    assert results[0]["title"] == "A"
    assert results[1]["title"] == "B"


@responses_lib.activate
def test_scrape_many_records_errors():
    responses_lib.add(
        responses_lib.GET, "https://example.com/ok", body="<title>OK</title>",
        content_type="text/html"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/fail",
        body=Exception("network error")
    )
    scraper = Scraper()
    results = scraper.scrape_many(
        ["https://example.com/ok", "https://example.com/fail"]
    )
    assert results[0]["title"] == "OK"
    assert "error" in results[1]
