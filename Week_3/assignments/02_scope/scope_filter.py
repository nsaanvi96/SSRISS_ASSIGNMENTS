#!/usr/bin/env python3
"""scope_filter.py - URL Scope Filter (Assignment 2)

Implements a configurable crawl-frontier boundary that decides whether a
discovered URL is allowed to enter the collection pipeline.

Key concepts implemented
------------------------
- Allowlist rules (hostname, path prefixes, excluded path prefixes)
- Same-site vs external link control
- URL canonicalization (scheme normalisation, fragment stripping, query
  parameter handling)
- Duplicate / visited-URL tracking
- Avoidance of calendar / search / filter / infinite URL spaces

Typical source_config shape
----------------------------
{
    "allowed_hostname": "www.iima.ac.in",
    "allowed_path_prefixes": ["/the-institute/events", "/news"],
    "excluded_path_prefixes": [
        "/calendar", "/search", "/filter",
        "/login", "/user", "/admin",
        "/sites/default/files"           # PDFs / binaries
    ],
    "allow_external": False,             # reject all off-domain links
    "strip_query_params": True,          # canonicalize before dup check
    "ignored_query_params": ["utm_source", "utm_medium", "utm_campaign",
                              "utm_term", "utm_content", "fbclid",
                              "gclid", "ref", "source"]
}
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Canonical URL helpers
# ---------------------------------------------------------------------------

def _canonicalize(url: str, config: Dict[str, Any]) -> str:
    """Return a stable canonical form of *url* for deduplication.

    Steps applied
    ~~~~~~~~~~~~~
    1. Lower-case the scheme and hostname.
    2. Remove the fragment (#...).
    3. Drop tracking / ignored query parameters.
    4. If strip_query_params is True in config, drop the entire query string.
    """
    try:
        parts = urllib.parse.urlsplit(url.strip())
    except Exception:
        return url

    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path          # preserve case - paths can be case-sensitive
    fragment = ""              # always strip fragments

    # Build cleaned query string
    if config.get("strip_query_params", False):
        query = ""
    else:
        ignored: List[str] = config.get("ignored_query_params", [])
        if ignored:
            params = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
            params = [(k, v) for k, v in params if k not in ignored]
            query = urllib.parse.urlencode(params)
        else:
            query = parts.query

    return urllib.parse.urlunsplit((scheme, netloc, path, query, fragment))


# ---------------------------------------------------------------------------
# Main filter
# ---------------------------------------------------------------------------

_BINARY_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".ppt", ".pptx", ".zip", ".rar", ".tar", ".gz",
    ".mp3", ".mp4", ".avi", ".mkv",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".webp",
    ".css", ".js",
}


class UrlScopeFilter:
    """Stateful crawl-frontier boundary for a single source.

    Parameters
    ----------
    source_config : dict
        See module docstring for the expected keys.
    """

    def __init__(self, source_config: Dict[str, Any]) -> None:
        self._config = source_config
        self._visited: Set[str] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_allowed(self, url: str) -> bool:
        """Return True if *url* may enter the collection pipeline."""
        return _is_allowed_item_url(url, self._config, self._visited)

    def reset_visited(self) -> None:
        """Clear the visited-URL memory (e.g. between runs)."""
        self._visited.clear()

    @property
    def visited_count(self) -> int:
        return len(self._visited)


# ---------------------------------------------------------------------------
# Stateless predicate (pure function, importable for tests)
# ---------------------------------------------------------------------------

def is_allowed_item_url(
    url: str,
    source_config: Dict[str, Any],
    _visited: Optional[Set[str]] = None,
) -> bool:
    """Pure predicate - decide if *url* is in scope for the given source.

    Parameters
    ----------
    url : str
        The candidate URL to evaluate.
    source_config : dict
        Scope rules (see module docstring).
    _visited : set, optional
        External visited-URL set for duplicate tracking.

    Returns
    -------
    bool
        True  -> URL is allowed into the pipeline.
        False -> URL must be rejected.
    """
    visited: Set[str] = _visited if _visited is not None else set()
    return _is_allowed_item_url(url, source_config, visited)


def _is_allowed_item_url(
    url: str,
    config: Dict[str, Any],
    visited: Set[str],
) -> bool:
    """Internal implementation shared by both the stateful and stateless APIs."""

    # -- 0. Basic sanity ---------------------------------------------------
    if not url or not url.strip():
        return False

    url = url.strip()

    # -- 1. Parse the URL --------------------------------------------------
    try:
        parts = urllib.parse.urlsplit(url)
    except Exception:
        return False

    # -- 2. Scheme must be http or https -----------------------------------
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        # Rejects mailto:, ftp:, javascript:, data:, etc.
        return False

    # -- 3. Hostname check -------------------------------------------------
    hostname = parts.hostname or ""
    allowed_hostname: str = config.get("allowed_hostname", "").lower()

    if allowed_hostname and hostname != allowed_hostname:
        # External link - check whether the config permits it
        if not config.get("allow_external", False):
            return False

    # -- 4. Path-prefix allowlist ------------------------------------------
    path: str = parts.path  # e.g.  /the-institute/events/some-event
    allowed_prefixes: List[str] = config.get("allowed_path_prefixes", [])

    if allowed_prefixes:
        if not any(path.startswith(prefix) for prefix in allowed_prefixes):
            return False

    # -- 5. Excluded path prefixes -----------------------------------------
    excluded_prefixes: List[str] = config.get("excluded_path_prefixes", [])
    if any(path.startswith(prefix) for prefix in excluded_prefixes):
        return False

    # -- 6. Binary / non-HTML resource extensions --------------------------
    path_lower = path.lower().rstrip("/")
    ext = ""
    if "." in path_lower.split("/")[-1]:
        ext = "." + path_lower.rsplit(".", 1)[-1]
    if ext in _BINARY_EXTENSIONS:
        return False

    # -- 7. Canonicalize and duplicate check -------------------------------
    canonical = _canonicalize(url, config)
    if canonical in visited:
        return False

    # -- 8. Accept - mark as visited ---------------------------------------
    visited.add(canonical)
    return True


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------

_IIMA_CONFIG: Dict[str, Any] = {
    "allowed_hostname": "www.iima.ac.in",
    "allowed_path_prefixes": [
        "/the-institute/events",
        "/news",
        "/research/publications",
    ],
    "excluded_path_prefixes": [
        "/calendar",
        "/search",
        "/filter",
        "/login",
        "/user",
        "/admin",
        "/sites/default/files",
        "/tag",
        "/taxonomy",
    ],
    "allow_external": False,
    "strip_query_params": False,
    "ignored_query_params": [
        "utm_source", "utm_medium", "utm_campaign",
        "utm_term", "utm_content",
        "fbclid", "gclid", "ref", "source",
    ],
}


_DEMO_URLS = [
    ("Valid event detail",           "https://www.iima.ac.in/the-institute/events/annual-management-retreat-2026"),
    ("Valid news detail",            "https://www.iima.ac.in/news/iima-ranked-1-in-india"),
    ("External registration site",   "https://www.eventbrite.com/e/iima-annual-retreat-tickets-123456"),
    ("Social media link",            "https://twitter.com/IIMAhmedabad/status/1776543210987654321"),
    ("PDF document",                 "https://www.iima.ac.in/sites/default/files/brochure.pdf"),
    ("Login URL",                    "https://www.iima.ac.in/login?destination=/events"),
    ("Search URL",                   "https://www.iima.ac.in/search?q=conference"),
    ("Duplicate URL with fragment",  "https://www.iima.ac.in/the-institute/events/annual-management-retreat-2026#agenda"),
    ("Same page + tracking param",   "https://www.iima.ac.in/the-institute/events/annual-management-retreat-2026?utm_source=email"),
    ("Calendar explosion URL",       "https://www.iima.ac.in/calendar/2026-10"),
    ("Filter URL",                   "https://www.iima.ac.in/filter/events?type=seminar&month=10"),
    ("Out-of-scope internal page",   "https://www.iima.ac.in/about/leadership"),
]


def main() -> None:
    import json

    scope = UrlScopeFilter(_IIMA_CONFIG)

    print("=" * 72)
    print("ASSIGNMENT 2 - URL SCOPE FILTER DEMO")
    print("Source: IIMA  |  Config:")
    print(json.dumps(_IIMA_CONFIG, indent=2))
    print("=" * 72)

    for label, url in _DEMO_URLS:
        allowed = scope.is_allowed(url)
        status = "ALLOW " if allowed else "REJECT"
        print(f"\n[{status}]  {label}")
        print(f"         {url}")

    print("\n" + "=" * 72)
    print(f"Visited set size after run: {scope.visited_count}")
    print("=" * 72)


if __name__ == "__main__":
    main()
