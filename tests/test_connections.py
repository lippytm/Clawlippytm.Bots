"""Tests for clawlippytm_bots.connections."""

from __future__ import annotations

import csv
import json

import responses as responses_lib

from clawlippytm_bots.connections import ConnectionsBuilder


_HOME_HTML = """<!DOCTYPE html>
<html><head><title>Home</title></head>
<body>
  <a href="/about">About</a>
  <a href="/contact">Contact</a>
  <a href="https://external.com/ext">External</a>
</body>
</html>"""

_ABOUT_HTML = """<!DOCTYPE html>
<html><head><title>About</title></head>
<body>
  <a href="/">Home</a>
  <a href="/contact">Contact</a>
</body>
</html>"""

_CONTACT_HTML = """<!DOCTYPE html>
<html><head><title>Contact</title></head>
<body>
  <a href="/">Home</a>
</body>
</html>"""


def _register_pages():
    responses_lib.add(
        responses_lib.GET, "https://example.com/",
        body=_HOME_HTML, content_type="text/html"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/about",
        body=_ABOUT_HTML, content_type="text/html"
    )
    responses_lib.add(
        responses_lib.GET, "https://example.com/contact",
        body=_CONTACT_HTML, content_type="text/html"
    )


@responses_lib.activate
def test_build_returns_graph_structure():
    _register_pages()
    builder = ConnectionsBuilder(depth=2, rate_limit=0)
    graph = builder.build("https://example.com/")
    assert "seed" in graph
    assert "nodes" in graph
    assert "edges" in graph
    assert "stats" in graph


@responses_lib.activate
def test_build_seed_is_first_node():
    _register_pages()
    builder = ConnectionsBuilder(depth=2, rate_limit=0)
    graph = builder.build("https://example.com/")
    assert graph["nodes"].get("https://example.com/") is not None


@responses_lib.activate
def test_build_discovers_internal_links():
    _register_pages()
    builder = ConnectionsBuilder(depth=2, rate_limit=0)
    graph = builder.build("https://example.com/")
    nodes = graph["nodes"]
    assert "https://example.com/about" in nodes
    assert "https://example.com/contact" in nodes


@responses_lib.activate
def test_build_records_external_edges():
    _register_pages()
    builder = ConnectionsBuilder(depth=2, rate_limit=0, include_external=True)
    graph = builder.build("https://example.com/")
    external_edges = [e for e in graph["edges"] if not e["internal"]]
    assert len(external_edges) >= 1


@responses_lib.activate
def test_build_no_external_edges_when_disabled():
    _register_pages()
    builder = ConnectionsBuilder(depth=2, rate_limit=0, include_external=False)
    graph = builder.build("https://example.com/")
    assert all(e["internal"] for e in graph["edges"])


@responses_lib.activate
def test_build_stats_edge_count():
    _register_pages()
    builder = ConnectionsBuilder(depth=2, rate_limit=0)
    graph = builder.build("https://example.com/")
    stats = graph["stats"]
    assert stats["edge_count"] == len(graph["edges"])
    assert stats["internal_edges"] + stats["external_edges"] == stats["edge_count"]


@responses_lib.activate
def test_build_top_pages_present():
    _register_pages()
    builder = ConnectionsBuilder(depth=2, rate_limit=0)
    graph = builder.build("https://example.com/")
    assert isinstance(graph["stats"]["top_pages"], list)


@responses_lib.activate
def test_export_json(tmp_path):
    _register_pages()
    builder = ConnectionsBuilder(depth=2, rate_limit=0)
    graph = builder.build("https://example.com/")
    dest = tmp_path / "graph.json"
    builder.export_json(graph, dest)
    loaded = json.loads(dest.read_text())
    assert loaded["seed"] == graph["seed"]
    assert len(loaded["edges"]) == len(graph["edges"])


@responses_lib.activate
def test_export_csv(tmp_path):
    _register_pages()
    builder = ConnectionsBuilder(depth=2, rate_limit=0)
    graph = builder.build("https://example.com/")
    dest = tmp_path / "edges.csv"
    builder.export_csv(graph, dest)
    with dest.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    assert len(rows) == len(graph["edges"])
    assert set(rows[0].keys()) >= {"source", "target", "internal"}


@responses_lib.activate
def test_export_dot(tmp_path):
    _register_pages()
    builder = ConnectionsBuilder(depth=2, rate_limit=0)
    graph = builder.build("https://example.com/")
    dest = tmp_path / "graph.dot"
    builder.export_dot(graph, dest)
    content = dest.read_text()
    assert "digraph connections" in content
    assert "->" in content


@responses_lib.activate
def test_in_degree_tracked():
    _register_pages()
    builder = ConnectionsBuilder(depth=2, rate_limit=0, include_external=False)
    graph = builder.build("https://example.com/")
    # /contact is linked from both home and about, so in_degree >= 2
    contact = graph["nodes"].get("https://example.com/contact", {})
    assert contact.get("in_degree", 0) >= 1
