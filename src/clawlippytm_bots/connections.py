"""
Connections builder module for Clawlippytm.Bots.

:class:`ConnectionsBuilder` crawls a website and builds a directed graph of
hyperlink connections between pages.  The graph can be exported in multiple
formats for analysis or visualisation.

Features:
- BFS crawl bounded to the seed domain.
- Records directed edges (source page → linked page).
- Distinguishes *internal* edges (same domain) from *external* edges.
- Computes per-node in-degree and out-degree.
- Exports to JSON, CSV (edge list), and Graphviz DOT format.
- Identifies the top-N most-connected pages.

Example::

    from clawlippytm_bots import ConnectionsBuilder

    builder = ConnectionsBuilder(depth=3, rate_limit=0.5)
    graph = builder.build("https://example.com")
    builder.export_json(graph, "connections.json")
    print(graph["stats"]["top_pages"][:3])
"""

from __future__ import annotations

import csv
import io
import time
from collections import deque, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from clawlippytm_bots.utils import (
    build_session,
    is_same_domain,
    normalise_url,
    save_json,
)


class ConnectionsBuilder:
    """Crawl a site and build a URL connection graph.

    Args:
        depth:       Maximum BFS depth from the seed URL.  ``None`` is
                     unlimited.
        rate_limit:  Minimum seconds between requests.
        user_agent:  Override the default User-Agent header.
        timeout:     Per-request socket timeout in seconds.
        retries:     Number of retry attempts on transient HTTP errors.
        include_external: When ``True``, include edges to external domains
                     (but do *not* crawl them).

    Attributes:
        session: The underlying :class:`requests.Session`.
    """

    def __init__(
        self,
        depth: int | None = 3,
        rate_limit: float = 0.5,
        user_agent: str | None = None,
        timeout: int = 30,
        retries: int = 3,
        include_external: bool = True,
    ) -> None:
        self.depth = depth
        self.rate_limit = rate_limit
        self.include_external = include_external
        self.session = build_session(
            retries=retries,
            user_agent=user_agent,
            timeout=timeout,
        )
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self, seed_url: str) -> dict[str, Any]:
        """Crawl *seed_url* and build the connection graph.

        Args:
            seed_url: Root URL to start crawling from.

        Returns:
            A graph dict with the following structure::

                {
                  "seed": "https://example.com",
                  "nodes": {
                    "https://example.com": {
                      "in_degree": 0,
                      "out_degree": 3,
                      "domain": "example.com",
                    },
                    ...
                  },
                  "edges": [
                    {"source": "https://example.com",
                     "target": "https://example.com/about",
                     "internal": true},
                    ...
                  ],
                  "stats": {
                    "node_count": ...,
                    "edge_count": ...,
                    "internal_edges": ...,
                    "external_edges": ...,
                    "top_pages": [...],   # by total degree, descending
                  },
                }
        """
        seed_url = normalise_url(seed_url)
        queue: deque[tuple[str, int]] = deque([(seed_url, 0)])
        visited: set[str] = set()
        edges: list[dict[str, Any]] = []
        in_degree: dict[str, int] = defaultdict(int)
        out_degree: dict[str, int] = defaultdict(int)
        domains: dict[str, str] = {}

        def _add_node(url: str) -> None:
            domains[url] = urlparse(url).netloc.lower()
            in_degree.setdefault(url, 0)
            out_degree.setdefault(url, 0)

        _add_node(seed_url)

        while queue:
            url, current_depth = queue.popleft()
            if url in visited:
                continue
            visited.add(url)

            self._rate_limit()
            try:
                response = self.session.get(
                    url, timeout=getattr(self.session, "timeout", 30)
                )
            except Exception:  # noqa: BLE001
                continue

            if not response.ok:
                continue

            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                continue

            links = self._extract_links(response.text, url)
            for link in links:
                internal = is_same_domain(link, seed_url)
                if not internal and not self.include_external:
                    continue

                _add_node(link)
                edges.append(
                    {"source": url, "target": link, "internal": internal}
                )
                out_degree[url] += 1
                in_degree[link] += 1

                if internal and (
                    self.depth is None or current_depth < self.depth
                ):
                    if link not in visited:
                        queue.append((link, current_depth + 1))

        # Build nodes dict
        all_nodes = set(domains) | set(in_degree) | set(out_degree)
        nodes: dict[str, dict[str, Any]] = {
            n: {
                "in_degree": in_degree.get(n, 0),
                "out_degree": out_degree.get(n, 0),
                "domain": domains.get(n, urlparse(n).netloc.lower()),
            }
            for n in all_nodes
        }

        internal_edges = sum(1 for e in edges if e["internal"])
        external_edges = len(edges) - internal_edges

        # Top pages by total (in + out) degree
        top_pages = sorted(
            nodes.keys(),
            key=lambda n: nodes[n]["in_degree"] + nodes[n]["out_degree"],
            reverse=True,
        )[:20]

        return {
            "seed": seed_url,
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "internal_edges": internal_edges,
                "external_edges": external_edges,
                "top_pages": top_pages,
            },
        }

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def export_json(self, graph: dict[str, Any], path: str | Path) -> None:
        """Save *graph* as a JSON file.

        Args:
            graph: Connection graph returned by :meth:`build`.
            path:  Destination file path.
        """
        save_json(graph, path)

    def export_csv(self, graph: dict[str, Any], path: str | Path) -> None:
        """Save the edge list of *graph* as a CSV file.

        The CSV has three columns: ``source``, ``target``, ``internal``.

        Args:
            graph: Connection graph returned by :meth:`build`.
            path:  Destination file path.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=["source", "target", "internal"]
            )
            writer.writeheader()
            writer.writerows(graph["edges"])

    def export_dot(self, graph: dict[str, Any], path: str | Path) -> None:
        """Save *graph* as a Graphviz DOT file.

        The file can be rendered with ``dot -Tpng connections.dot -o connections.png``.

        Args:
            graph: Connection graph returned by :meth:`build`.
            path:  Destination file path.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        buf = io.StringIO()
        buf.write("digraph connections {\n")
        buf.write('    rankdir="LR";\n')
        buf.write('    node [shape=box fontname="Helvetica"];\n')
        for node in graph["nodes"]:
            label = node.replace('"', '\\"')
            buf.write(f'    "{label}";\n')
        for edge in graph["edges"]:
            src = edge["source"].replace('"', '\\"')
            tgt = edge["target"].replace('"', '\\"')
            colour = "blue" if edge["internal"] else "grey"
            buf.write(f'    "{src}" -> "{tgt}" [color={colour}];\n')
        buf.write("}\n")
        path.write_text(buf.getvalue(), encoding="utf-8")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rate_limit(self) -> None:
        if self.rate_limit <= 0:
            return
        elapsed = time.monotonic() - self._last_request_time
        wait = self.rate_limit - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_time = time.monotonic()

    @staticmethod
    def _extract_links(html: str, base_url: str) -> list[str]:
        """Return de-duplicated absolute ``<a href>`` links from *html*.

        Args:
            html:     Raw HTML string.
            base_url: Base URL for resolving relative links.

        Returns:
            List of unique, normalised absolute URL strings.
        """
        soup = BeautifulSoup(html, "lxml")
        seen: set[str] = set()
        result: list[str] = []
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            if not href or href.startswith(
                ("#", "mailto:", "tel:", "javascript:")
            ):
                continue
            abs_url = urljoin(base_url, href)
            parsed = urlparse(abs_url)
            if parsed.scheme not in ("http", "https"):
                continue
            norm = normalise_url(abs_url)
            if norm not in seen:
                seen.add(norm)
                result.append(norm)
        return result
