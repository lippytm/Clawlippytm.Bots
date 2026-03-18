"""
Site cloner module for Clawlippytm.Bots.

The :class:`SiteCloner` crawls a website and mirrors it to a local directory,
preserving the directory hierarchy and rewriting in-page URLs so the clone
is self-contained and browsable offline.

Features:
- BFS crawl limited to the seed domain.
- Downloads HTML pages, stylesheets, scripts, images, and other linked assets.
- Rewrites ``href``/``src`` attributes in cloned HTML to point to local files.
- Respects ``robots.txt`` (can be disabled).
- Configurable crawl depth limit.
- Progress reported via :mod:`tqdm` (suppressed in non-TTY environments).

Example::

    from clawlippytm_bots import SiteCloner

    cloner = SiteCloner(depth=2, rate_limit=0.5)
    stats = cloner.clone("https://example.com", output_dir="./clone")
    print(stats)
"""

from __future__ import annotations

import time
import urllib.robotparser as robotparser
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from clawlippytm_bots.utils import (
    build_session,
    is_same_domain,
    normalise_url,
)

_ASSET_TAGS: dict[str, str] = {
    "img": "src",
    "script": "src",
    "source": "src",
    "video": "src",
    "audio": "src",
}
_LINK_TAGS: dict[str, str] = {
    "link": "href",
    "a": "href",
}


class SiteCloner:
    """Clone an entire website to a local directory.

    Args:
        depth:          Maximum crawl depth from the seed URL.  ``0`` clones
                        only the seed page; ``None`` is unlimited.
        rate_limit:     Minimum seconds between requests.
        user_agent:     Override the default User-Agent header.
        timeout:        Per-request socket timeout in seconds.
        retries:        Number of retry attempts on transient HTTP errors.
        respect_robots: When ``True`` (default), honour ``robots.txt``.

    Attributes:
        session: The underlying :class:`requests.Session`.
    """

    def __init__(
        self,
        depth: int | None = 2,
        rate_limit: float = 0.5,
        user_agent: str | None = None,
        timeout: int = 30,
        retries: int = 3,
        respect_robots: bool = True,
    ) -> None:
        self.depth = depth
        self.rate_limit = rate_limit
        self.respect_robots = respect_robots
        self.session = build_session(
            retries=retries,
            user_agent=user_agent,
            timeout=timeout,
        )
        self._last_request_time: float = 0.0
        self._robots: dict[str, robotparser.RobotFileParser] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clone(self, seed_url: str, output_dir: str | Path = "./clone") -> dict[str, Any]:
        """Clone *seed_url* and all reachable same-domain pages/assets.

        The clone is written to *output_dir*.  An ``index.json`` manifest is
        saved alongside the cloned files listing every fetched URL and its
        local path.

        Args:
            seed_url:   The root URL to start cloning from.
            output_dir: Local directory to write files into.  Created if it
                        does not exist.

        Returns:
            A statistics dict with keys:

            ``pages_cloned``   — Number of HTML pages saved.
            ``assets_cloned``  — Number of binary/asset files saved.
            ``errors``         — Number of fetch errors.
            ``output_dir``     — Absolute path of the output directory.
        """
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        seed_url = normalise_url(seed_url)
        queue: deque[tuple[str, int]] = deque([(seed_url, 0)])
        visited: set[str] = set()
        manifest: list[dict[str, str]] = []
        stats = {"pages_cloned": 0, "assets_cloned": 0, "errors": 0}

        while queue:
            url, current_depth = queue.popleft()
            if url in visited:
                continue
            visited.add(url)

            if not self._is_allowed(url):
                continue

            self._rate_limit()
            try:
                response = self.session.get(
                    url, timeout=getattr(self.session, "timeout", 30)
                )
            except Exception as exc:  # noqa: BLE001
                stats["errors"] += 1
                manifest.append({"url": url, "error": str(exc)})
                continue

            if not response.ok:
                stats["errors"] += 1
                manifest.append(
                    {"url": url, "error": f"HTTP {response.status_code}"}
                )
                continue

            content_type = response.headers.get("Content-Type", "")
            is_html = "text/html" in content_type

            local_path = self._derive_local_path(url, output_dir, is_html)
            local_path.parent.mkdir(parents=True, exist_ok=True)

            if is_html:
                html, new_urls = self._process_html(
                    response.text, url, output_dir
                )
                local_path.write_text(html, encoding="utf-8")
                stats["pages_cloned"] += 1

                if self.depth is None or current_depth < self.depth:
                    for new_url in new_urls:
                        if new_url not in visited and is_same_domain(
                            new_url, seed_url
                        ):
                            queue.append((new_url, current_depth + 1))
            else:
                local_path.write_bytes(response.content)
                stats["assets_cloned"] += 1

            manifest.append(
                {"url": url, "local_path": str(local_path.relative_to(output_dir))}
            )

        # Write manifest
        import json

        manifest_path = output_dir / "index.json"
        manifest_path.write_text(
            json.dumps(
                {"seed": seed_url, "stats": stats, "files": manifest},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        stats["output_dir"] = str(output_dir)
        return stats

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

    def _is_allowed(self, url: str) -> bool:
        """Check ``robots.txt`` permissions for *url*.

        Args:
            url: URL to check.

        Returns:
            ``True`` if the bot is allowed to fetch *url*.
        """
        if not self.respect_robots:
            return True
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        if robots_url not in self._robots:
            rp = robotparser.RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
            except Exception:  # noqa: BLE001
                rp.allow_all = True
            self._robots[robots_url] = rp
        ua = self.session.headers.get("User-Agent", "*")
        return self._robots[robots_url].can_fetch(ua, url)

    def _derive_local_path(
        self, url: str, output_dir: Path, is_html: bool
    ) -> Path:
        """Map a URL to a local file path under *output_dir*.

        Args:
            url:        Absolute URL of the resource.
            output_dir: Root of the clone directory.
            is_html:    When ``True``, ensure the path ends with ``.html``.

        Returns:
            Absolute :class:`pathlib.Path` for the local file.
        """
        parsed = urlparse(url)
        rel = parsed.path.lstrip("/")
        if not rel:
            return output_dir / "index.html"
        path = output_dir / rel
        if is_html and not path.suffix:
            path = path.with_suffix(".html")
        elif is_html and path.suffix not in (".html", ".htm"):
            path = path.with_name(path.name + ".html")
        return path

    def _process_html(
        self, html: str, base_url: str, output_dir: Path
    ) -> tuple[str, list[str]]:
        """Rewrite in-page URLs to local paths and extract follow-on URLs.

        Args:
            html:       Raw HTML string.
            base_url:   Absolute URL of this page (used for resolving relatives).
            output_dir: Root of the clone directory.

        Returns:
            A tuple of:

            - Rewritten HTML string suitable for saving to disk.
            - List of new absolute URLs discovered in the page.
        """
        soup = BeautifulSoup(html, "lxml")
        new_urls: list[str] = []

        for tag_name, attr in _ASSET_TAGS.items():
            for tag in soup.find_all(tag_name, **{attr: True}):
                raw = tag[attr].strip()
                if not raw or raw.startswith("data:"):
                    continue
                abs_url = urljoin(base_url, raw)
                parsed = urlparse(abs_url)
                if parsed.scheme not in ("http", "https"):
                    continue
                if is_same_domain(abs_url, base_url):
                    local_path = self._derive_local_path(abs_url, output_dir, False)
                    tag[attr] = str(local_path.relative_to(output_dir))
                    new_urls.append(normalise_url(abs_url))

        for tag_name, attr in _LINK_TAGS.items():
            for tag in soup.find_all(tag_name, **{attr: True}):
                raw = tag[attr].strip()
                if not raw or raw.startswith(
                    ("#", "mailto:", "tel:", "javascript:")
                ):
                    continue
                abs_url = urljoin(base_url, raw)
                parsed = urlparse(abs_url)
                if parsed.scheme not in ("http", "https"):
                    continue
                if is_same_domain(abs_url, base_url):
                    # Only <a> tags link to HTML pages; <link> tags point to
                    # stylesheets, canonical URLs, feeds, etc. — never HTML.
                    is_html = tag_name == "a"
                    local_path = self._derive_local_path(
                        abs_url, output_dir, is_html
                    )
                    tag[attr] = str(local_path.relative_to(output_dir))
                    new_urls.append(normalise_url(abs_url))

        return str(soup), new_urls
