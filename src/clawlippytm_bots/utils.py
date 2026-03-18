"""
Shared utility helpers for Clawlippytm.Bots.

Provides:
- build_session()   — requests.Session with retry logic and a realistic User-Agent.
- normalise_url()   — canonicalise a URL (strip fragments, sort query params).
- safe_filename()   — convert a URL path to a safe local filename.
- save_json()       — atomically save data as pretty-printed JSON.
- load_json()       — load JSON from disk, returning None if the file is absent.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
# HTTP session factory
# ---------------------------------------------------------------------------

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; Clawlippytm.Bots/1.0; "
    "+https://github.com/lippytm/Clawlippytm.Bots)"
)


def build_session(
    retries: int = 3,
    backoff_factor: float = 0.5,
    user_agent: str | None = None,
    timeout: int = 30,
) -> requests.Session:
    """Return a requests.Session pre-configured with retry logic.

    Args:
        retries:        Number of retries on transient errors.
        backoff_factor: Exponential back-off between retries (seconds).
        user_agent:     Override the User-Agent header.  Defaults to the
                        Clawlippytm.Bots agent string.
        timeout:        Default socket timeout (stored on the session as an
                        attribute so callers can pass ``session.timeout``).

    Returns:
        A configured :class:`requests.Session`.
    """
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods={"GET", "HEAD"},
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": user_agent or _DEFAULT_USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
    )
    session.timeout = timeout  # type: ignore[attr-defined]
    return session


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def normalise_url(url: str, *, strip_fragment: bool = True) -> str:
    """Return a canonical form of *url*.

    - Lowercases the scheme and host.
    - Strips URL fragments by default.
    - Sorts query-string parameters for stable caching keys.

    Args:
        url:            The URL string to normalise.
        strip_fragment: When ``True`` (default) the ``#fragment`` is removed.

    Returns:
        Normalised URL string.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    query = urlencode(sorted(parse_qsl(parsed.query)))
    fragment = "" if strip_fragment else parsed.fragment
    return urlunparse((scheme, netloc, path, parsed.params, query, fragment))


def is_same_domain(url: str, base_url: str) -> bool:
    """Return ``True`` if *url* belongs to the same host as *base_url*.

    Args:
        url:      URL to test.
        base_url: Reference base URL.

    Returns:
        ``True`` when both URLs share the same network location (host + port).
    """
    return urlparse(url).netloc.lower() == urlparse(base_url).netloc.lower()


def safe_filename(url: str, default: str = "index.html") -> str:
    """Derive a safe local filename from a URL path.

    Replaces path separators and URL-unsafe characters so the result can be
    used directly as a filesystem filename.

    Args:
        url:     Source URL.
        default: Fallback name when the path is empty or root.

    Returns:
        A filename string containing only alphanumerics, hyphens, underscores,
        and a single dot before the extension.
    """
    path = urlparse(url).path.strip("/")
    if not path:
        return default
    # Replace slashes with underscores, collapse unsafe chars
    name = re.sub(r"[^\w.\-]", "_", path.replace("/", "__"))
    # Ensure it doesn't start with a dot
    name = name.lstrip(".")
    return name or default


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------


def save_json(data: object, path: str | Path, indent: int = 2) -> None:
    """Atomically write *data* as pretty-printed JSON to *path*.

    Writes to a temporary file first, then replaces the target so the output
    is never partially written.

    Args:
        data:   JSON-serialisable Python object.
        path:   Destination file path.
        indent: JSON indentation level.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        suffix=".tmp",
    ) as tmp:
        json.dump(data, tmp, indent=indent, ensure_ascii=False)
        tmp_path = tmp.name
    os.replace(tmp_path, path)


def load_json(path: str | Path) -> object | None:
    """Load JSON from *path*, returning ``None`` when the file is absent.

    Args:
        path: Path to the JSON file.

    Returns:
        Deserialised Python object, or ``None`` if *path* does not exist.
    """
    path = Path(path)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)
