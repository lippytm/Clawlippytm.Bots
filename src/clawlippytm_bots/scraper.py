"""
Web scraper module for Clawlippytm.Bots.

The :class:`Scraper` class fetches a web page and extracts structured data:

- Page title and meta tags
- All hyperlinks (internal and external)
- Visible text content
- Image, script, and stylesheet URLs
- Canonical URL and Open Graph metadata

Results are returned as a plain :class:`dict` that can be saved to JSON via
:func:`clawlippytm_bots.utils.save_json`.

Example::

    from clawlippytm_bots import Scraper

    scraper = Scraper(rate_limit=1.0)
    result = scraper.scrape("https://example.com")
    print(result["title"])
    print(result["links"][:5])
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from clawlippytm_bots.utils import build_session, normalise_url


class Scraper:
    """Fetch and parse a single web page.

    Args:
        rate_limit:  Minimum seconds to wait between successive requests made
                     on the *same* :class:`Scraper` instance.  Defaults to
                     ``0`` (no delay).
        user_agent:  Override the default User-Agent header.
        timeout:     Per-request socket timeout in seconds.
        retries:     Number of retry attempts on transient failures.

    Attributes:
        session: The underlying :class:`requests.Session`.
    """

    def __init__(
        self,
        rate_limit: float = 0.0,
        user_agent: str | None = None,
        timeout: int = 30,
        retries: int = 3,
    ) -> None:
        self.rate_limit = rate_limit
        self.session = build_session(
            retries=retries,
            user_agent=user_agent,
            timeout=timeout,
        )
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape(self, url: str) -> dict[str, Any]:
        """Scrape *url* and return a structured result dict.

        Applies the configured rate limit before fetching.

        Args:
            url: The page URL to scrape.

        Returns:
            A dictionary with the following keys:

            ``url``
                The normalised URL that was scraped.
            ``status_code``
                HTTP response status code.
            ``title``
                The page ``<title>`` text, or ``""`` if absent.
            ``description``
                Content of the ``<meta name="description">`` tag.
            ``keywords``
                Content of the ``<meta name="keywords">`` tag.
            ``canonical``
                Canonical URL from ``<link rel="canonical">``, or ``""``.
            ``og``
                Dict of Open Graph properties (``og:title``, ``og:image``, …).
            ``links``
                Sorted, de-duplicated list of absolute URLs found in ``<a>``
                tags.
            ``images``
                List of absolute ``src`` URLs found in ``<img>`` tags.
            ``scripts``
                List of absolute ``src`` URLs found in ``<script>`` tags.
            ``styles``
                List of absolute ``href`` URLs found in ``<link rel="stylesheet">``
                tags.
            ``text``
                Visible page text (whitespace-normalised).

        Raises:
            requests.RequestException: On network or HTTP errors after all
                retries are exhausted.
        """
        self._rate_limit()
        norm_url = normalise_url(url)
        timeout = getattr(self.session, "timeout", 30)
        response = self.session.get(norm_url, timeout=timeout)
        response.raise_for_status()
        return self._parse(norm_url, response.text, response.status_code)

    def scrape_many(self, urls: list[str]) -> list[dict[str, Any]]:
        """Scrape multiple URLs sequentially, honouring the rate limit.

        Args:
            urls: Iterable of URL strings to scrape.

        Returns:
            List of result dicts in the same order as *urls*.  If a request
            fails the corresponding entry will contain an ``"error"`` key with
            the exception message instead of the normal fields.
        """
        results: list[dict[str, Any]] = []
        for url in urls:
            try:
                results.append(self.scrape(url))
            except Exception as exc:  # noqa: BLE001
                results.append({"url": url, "error": str(exc)})
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rate_limit(self) -> None:
        """Sleep if necessary to honour :attr:`rate_limit`."""
        if self.rate_limit <= 0:
            return
        elapsed = time.monotonic() - self._last_request_time
        wait = self.rate_limit - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_time = time.monotonic()

    def _parse(
        self, url: str, html: str, status_code: int
    ) -> dict[str, Any]:
        """Parse *html* and return the structured result dict.

        Args:
            url:         The canonical URL of the page.
            html:        Raw HTML content.
            status_code: HTTP status code of the response.

        Returns:
            Parsed result dictionary (see :meth:`scrape` for schema).
        """
        soup = BeautifulSoup(html, "lxml")

        title = soup.title.get_text(strip=True) if soup.title else ""
        description = self._meta(soup, "description")
        keywords = self._meta(soup, "keywords")

        canonical_tag = soup.find("link", rel="canonical")
        canonical = canonical_tag.get("href", "") if canonical_tag else ""

        og: dict[str, str] = {}
        for tag in soup.find_all("meta", property=True):
            prop = tag.get("property", "")
            if prop.startswith("og:"):
                og[prop] = tag.get("content", "")

        links = self._extract_links(soup, url)
        images = self._extract_assets(soup, url, "img", "src")
        scripts = self._extract_assets(soup, url, "script", "src")
        styles = [
            urljoin(url, tag.get("href", ""))
            for tag in soup.find_all("link", rel="stylesheet")
            if tag.get("href")
        ]

        text = soup.get_text(separator=" ", strip=True)
        # Collapse whitespace
        text = " ".join(text.split())

        return {
            "url": url,
            "status_code": status_code,
            "title": title,
            "description": description,
            "keywords": keywords,
            "canonical": canonical,
            "og": og,
            "links": links,
            "images": images,
            "scripts": scripts,
            "styles": styles,
            "text": text,
        }

    @staticmethod
    def _meta(soup: BeautifulSoup, name: str) -> str:
        """Return the ``content`` attribute of a ``<meta name=…>`` tag.

        Args:
            soup: Parsed page soup.
            name: Value of the ``name`` attribute to look up.

        Returns:
            The tag's ``content`` value, or ``""`` if not found.
        """
        tag = soup.find("meta", attrs={"name": name})
        return tag.get("content", "") if tag else ""

    @staticmethod
    def _extract_links(soup: BeautifulSoup, base_url: str) -> list[str]:
        """Return sorted, de-duplicated absolute ``href`` URLs from ``<a>`` tags.

        Only ``http`` and ``https`` links are included.

        Args:
            soup:     Parsed page soup.
            base_url: Base URL used to resolve relative links.

        Returns:
            Sorted list of unique absolute URL strings.
        """
        seen: set[str] = set()
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            abs_url = urljoin(base_url, href)
            parsed = urlparse(abs_url)
            if parsed.scheme in ("http", "https"):
                seen.add(normalise_url(abs_url))
        return sorted(seen)

    @staticmethod
    def _extract_assets(
        soup: BeautifulSoup, base_url: str, tag_name: str, attr: str
    ) -> list[str]:
        """Return a list of absolute asset URLs for a given HTML tag/attribute.

        Args:
            soup:     Parsed page soup.
            base_url: Base URL for resolving relative paths.
            tag_name: HTML tag name (e.g. ``"img"``).
            attr:     Attribute holding the URL (e.g. ``"src"``).

        Returns:
            List of absolute URL strings (preserving document order,
            duplicates removed while keeping first occurrence).
        """
        seen: set[str] = set()
        result: list[str] = []
        for tag in soup.find_all(tag_name, **{attr: True}):
            raw = tag[attr].strip()
            if not raw:
                continue
            abs_url = urljoin(base_url, raw)
            if abs_url not in seen:
                seen.add(abs_url)
                result.append(abs_url)
        return result
