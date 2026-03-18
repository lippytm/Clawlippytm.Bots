"""Tests for clawlippytm_bots.cloner."""

from __future__ import annotations

import json

import responses as responses_lib

from clawlippytm_bots.cloner import SiteCloner


_INDEX_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Home</title>
  <link rel="stylesheet" href="/style.css">
  <script src="/app.js"></script>
</head>
<body>
  <a href="/about">About</a>
  <a href="https://external.com">External</a>
  <img src="/logo.png">
</body>
</html>"""

_ABOUT_HTML = """<!DOCTYPE html>
<html><head><title>About</title></head>
<body><a href="/">Home</a></body>
</html>"""

_CSS = "body { color: red; }"
_JS = "console.log('hi');"
_PNG = b"\x89PNG\r\n"


@responses_lib.activate
def test_clone_creates_output_dir(tmp_path):
    responses_lib.add(
        responses_lib.GET, "https://example.com/",
        body=_INDEX_HTML, content_type="text/html"
    )
    # Assets the cloner will try to fetch
    responses_lib.add(
        responses_lib.GET, "https://example.com/style.css",
        body=_CSS, content_type="text/css"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/app.js",
        body=_JS, content_type="application/javascript"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/logo.png",
        body=_PNG, content_type="image/png"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/about",
        body=_ABOUT_HTML, content_type="text/html"
    )
    out = tmp_path / "site"
    cloner = SiteCloner(depth=1, rate_limit=0, respect_robots=False)
    stats = cloner.clone("https://example.com/", output_dir=out)
    assert out.exists()
    assert stats["pages_cloned"] >= 1


@responses_lib.activate
def test_clone_saves_manifest(tmp_path):
    responses_lib.add(
        responses_lib.GET, "https://example.com/",
        body=_INDEX_HTML, content_type="text/html"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/style.css",
        body=_CSS, content_type="text/css"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/app.js",
        body=_JS, content_type="application/javascript"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/logo.png",
        body=_PNG, content_type="image/png"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/about",
        body=_ABOUT_HTML, content_type="text/html"
    )
    out = tmp_path / "site"
    cloner = SiteCloner(depth=1, rate_limit=0, respect_robots=False)
    cloner.clone("https://example.com/", output_dir=out)
    manifest_path = out / "index.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())
    assert manifest["seed"] == "https://example.com/"
    assert "stats" in manifest
    assert "files" in manifest


@responses_lib.activate
def test_clone_returns_stats(tmp_path):
    responses_lib.add(
        responses_lib.GET, "https://example.com/",
        body=_INDEX_HTML, content_type="text/html"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/style.css",
        body=_CSS, content_type="text/css"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/app.js",
        body=_JS, content_type="application/javascript"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/logo.png",
        body=_PNG, content_type="image/png"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/about",
        body=_ABOUT_HTML, content_type="text/html"
    )
    out = tmp_path / "site"
    cloner = SiteCloner(depth=0, rate_limit=0, respect_robots=False)
    stats = cloner.clone("https://example.com/", output_dir=out)
    assert "pages_cloned" in stats
    assert "assets_cloned" in stats
    assert "errors" in stats
    assert "output_dir" in stats


@responses_lib.activate
def test_clone_depth_zero_fetches_only_root(tmp_path):
    responses_lib.add(
        responses_lib.GET, "https://example.com/",
        body=_INDEX_HTML, content_type="text/html"
    )
    out = tmp_path / "site"
    cloner = SiteCloner(depth=0, rate_limit=0, respect_robots=False)
    stats = cloner.clone("https://example.com/", output_dir=out)
    # depth=0 means don't follow links — only root HTML saved
    assert stats["pages_cloned"] == 1


@responses_lib.activate
def test_clone_rewrites_local_links(tmp_path):
    responses_lib.add(
        responses_lib.GET, "https://example.com/",
        body=_INDEX_HTML, content_type="text/html"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/about",
        body=_ABOUT_HTML, content_type="text/html"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/style.css",
        body=_CSS, content_type="text/css"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/app.js",
        body=_JS, content_type="application/javascript"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/logo.png",
        body=_PNG, content_type="image/png"
    )
    out = tmp_path / "site"
    cloner = SiteCloner(depth=1, rate_limit=0, respect_robots=False)
    cloner.clone("https://example.com/", output_dir=out)
    index_html = (out / "index.html").read_text(encoding="utf-8")
    # External links should NOT be rewritten to a local path.
    # Parse the HTML; the external anchor must retain its original href exactly.
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(index_html, "lxml")
    external_anchors = [
        tag for tag in soup.find_all("a", href=True)
        if tag["href"] == "https://external.com"
    ]
    assert len(external_anchors) == 1


@responses_lib.activate
def test_clone_handles_http_error(tmp_path):
    responses_lib.add(
        responses_lib.GET, "https://example.com/",
        status=404
    )
    out = tmp_path / "site"
    cloner = SiteCloner(depth=0, rate_limit=0, respect_robots=False)
    stats = cloner.clone("https://example.com/", output_dir=out)
    assert stats["errors"] >= 1
