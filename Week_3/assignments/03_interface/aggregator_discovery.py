#!/usr/bin/env python3
"""aggregator_discovery.py - Aggregator Discovery Interface (Assignment 3)

Provides a unified entry-point that wires together:
  - Discovery adapters  (HTML listing, RSS feed, XML sitemap)  [Assignment 1]
  - URL scope filter                                            [Assignment 2]

Public API
----------
High-level (one call, all channels):
    discover_items(source_config) -> list[dict]

Low-level (individual adapters — same shape returned):
    discover_from_html(source_config)    -> list[dict]
    discover_from_feed(source_config)    -> list[dict]
    discover_from_sitemap(source_config) -> list[dict]

Canonical discovery record shape
---------------------------------
Every item returned by any function is a plain dict with exactly these keys:

    {
        "source_name":      str,              # e.g. "iima"
        "discovered_url":   str,              # fully-qualified, canonicalized
        "discovery_method": str,              # "html_listing" | "rss" | "sitemap"
        "discovered_title": str | None,
        "source_timestamp": str | None,       # as found in source (not parsed)
        "discovered_at":    str,              # ISO-8601 UTC timestamp
    }

The shape is source_config-agnostic — the same detail parser can accept any
record regardless of which channel produced it (checkpoint requirement).

source_config keys
------------------
Required:
    source_name         str   human label, e.g. "iima"
    allowed_hostname    str   e.g. "www.iima.ac.in"

Optional discovery sources (at least one should be set):
    html_url            str   live URL  -or-
    html_fixture        str   local file path

    feed_url            str   live URL  -or-
    feed_fixture        str   local file path

    sitemap_url         str   live URL  -or-
    sitemap_fixture     str   local file path

Optional scope rules (forwarded to UrlScopeFilter):
    allowed_path_prefixes    list[str]
    excluded_path_prefixes   list[str]
    allow_external           bool        (default False)
    strip_query_params       bool        (default False)
    ignored_query_params     list[str]

Optional limits:
    max_items_per_channel    int         (default: no limit)
"""

from __future__ import annotations

import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
import feedparser  # type: ignore

# ---------------------------------------------------------------------------
# Resolve sibling modules (02_scope lives next to 03_interface)
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_SCOPE_DIR = os.path.join(_HERE, "..", "02_scope")
if _SCOPE_DIR not in sys.path:
    sys.path.insert(0, _SCOPE_DIR)

from scope_filter import UrlScopeFilter  # noqa: E402  (after path fixup)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch(source: str) -> bytes:
    """Fetch bytes from a local file path or an HTTP(S) URL."""
    if os.path.isfile(source):
        with open(source, "rb") as fh:
            return fh.read()
    req = urllib.request.Request(
        source,
        headers={"User-Agent": "Mozilla/5.0 (aggregator-discovery/3.0)"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


def _make_record(
    source_name: str,
    discovered_url: str,
    discovery_method: str,
    discovered_title: Optional[str] = None,
    source_timestamp: Optional[str] = None,
    discovered_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Return the canonical discovery record dict."""
    return {
        "source_name":      source_name,
        "discovered_url":   discovered_url.strip(),
        "discovery_method": discovery_method,
        "discovered_title": discovered_title.strip() if discovered_title else None,
        "source_timestamp": source_timestamp.strip() if source_timestamp else None,
        "discovered_at":    discovered_at or _now_iso(),
    }


def _scope_filter_from_config(cfg: Dict[str, Any]) -> UrlScopeFilter:
    """Build a UrlScopeFilter from the source_config."""
    scope_cfg = {
        "allowed_hostname":       cfg.get("allowed_hostname", ""),
        "allowed_path_prefixes":  cfg.get("allowed_path_prefixes", []),
        "excluded_path_prefixes": cfg.get("excluded_path_prefixes", []),
        "allow_external":         cfg.get("allow_external", False),
        "strip_query_params":     cfg.get("strip_query_params", False),
        "ignored_query_params":   cfg.get("ignored_query_params", []),
    }
    return UrlScopeFilter(scope_cfg)


# ---------------------------------------------------------------------------
# Individual adapter functions
# ---------------------------------------------------------------------------

def discover_from_html(source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Discover items from a server-rendered HTML listing page.

    Reads *html_fixture* (local path) or *html_url* (live).
    Applies scope filter before returning.
    """
    source_name: str = source_config.get("source_name", "unknown")
    source: str = source_config.get("html_fixture") or source_config.get("html_url", "")
    base_url: str = f"https://{source_config.get('allowed_hostname', '')}"
    limit: Optional[int] = source_config.get("max_items_per_channel")

    if not source:
        return []

    scope = _scope_filter_from_config(source_config)
    now = _now_iso()
    records: List[Dict[str, Any]] = []

    html_bytes = _fetch(source)
    soup = BeautifulSoup(html_bytes.decode("utf-8", errors="ignore"), "html.parser")

    for row in soup.select(".views-row"):
        a_tag = row.find("a")
        if not a_tag or not a_tag.get("href"):
            continue

        href = a_tag["href"].strip()
        url = urllib.parse.urljoin(base_url, href)

        if not scope.is_allowed(url):
            continue

        title = a_tag.get_text(strip=True) or None
        date_el = row.select_one(".events-style-1-date, .date, time")
        ts = " ".join(date_el.stripped_strings) if date_el else None

        records.append(_make_record(source_name, url, "html_listing", title, ts, now))
        if limit and len(records) >= limit:
            break

    return records


def discover_from_feed(source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Discover items from an RSS or Atom feed.

    Reads *feed_fixture* (local path) or *feed_url* (live).
    Applies scope filter before returning.
    """
    source_name: str = source_config.get("source_name", "unknown")
    source: str = source_config.get("feed_fixture") or source_config.get("feed_url", "")
    limit: Optional[int] = source_config.get("max_items_per_channel")

    if not source:
        return []

    scope = _scope_filter_from_config(source_config)
    now = _now_iso()
    records: List[Dict[str, Any]] = []

    feed_bytes = _fetch(source)
    parsed = feedparser.parse(feed_bytes)

    for entry in parsed.entries:
        url = (
            entry.get("link")
            or (entry.get("links") or [{}])[0].get("href")
            or entry.get("id")
        )
        if not url:
            continue

        if not scope.is_allowed(url):
            continue

        title = entry.get("title")
        published = entry.get("published") or entry.get("updated") or entry.get("created")

        records.append(_make_record(source_name, url, "rss", title, published, now))
        if limit and len(records) >= limit:
            break

    return records


def discover_from_sitemap(source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Discover items from an XML sitemap (urlset).

    Reads *sitemap_fixture* (local path) or *sitemap_url* (live).
    Applies scope filter before returning.
    """
    source_name: str = source_config.get("source_name", "unknown")
    source: str = source_config.get("sitemap_fixture") or source_config.get("sitemap_url", "")
    limit: Optional[int] = source_config.get("max_items_per_channel")

    if not source:
        return []

    scope = _scope_filter_from_config(source_config)
    now = _now_iso()
    records: List[Dict[str, Any]] = []

    xml_bytes = _fetch(source)
    root = ET.fromstring(xml_bytes)

    def _strip_ns(tag: str) -> str:
        return tag.split("}", 1)[1] if "}" in tag else tag

    for child in root:
        tag = _strip_ns(child.tag).lower()
        if tag not in {"url", "sitemap"}:
            continue

        loc = lastmod = None
        for sub in child:
            sub_tag = _strip_ns(sub.tag).lower()
            if sub_tag == "loc" and sub.text:
                loc = sub.text.strip()
            elif sub_tag == "lastmod" and sub.text:
                lastmod = sub.text.strip()

        if not loc:
            continue

        if not scope.is_allowed(loc):
            continue

        records.append(_make_record(source_name, loc, "sitemap", None, lastmod, now))
        if limit and len(records) >= limit:
            break

    return records


# ---------------------------------------------------------------------------
# Unified entry-point
# ---------------------------------------------------------------------------

DISCOVERY_SCHEMA_KEYS = frozenset({
    "source_name",
    "discovered_url",
    "discovery_method",
    "discovered_title",
    "source_timestamp",
    "discovered_at",
})


def discover_items(source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run all configured discovery channels and return a deduplicated list.

    URLs seen in an earlier channel are not re-emitted by a later one.
    The scope filter''s visited set is shared across all three adapters so
    deduplication works globally within a single discover_items() call.

    Parameters
    ----------
    source_config : dict
        Combined config with discovery sources + scope rules.
        See module docstring for all keys.

    Returns
    -------
    list[dict]
        Flat list of canonical discovery records, one per unique in-scope URL.
    """
    # Build ONE shared scope filter so visited-URL dedup spans all channels
    scope = _scope_filter_from_config(source_config)

    # Inject the shared scope into per-channel calls by temporarily patching
    # We do this cleanly by passing the scope''s visited set around.
    # Strategy: run each adapter with a clone config that holds no scope state
    # of its own, then gate results through the shared scope here.

    all_records: List[Dict[str, Any]] = []

    def _run(fn, method_key: str) -> None:
        """Run adapter fn; gate each result through the shared scope."""
        try:
            raw = fn(source_config)
        except Exception as exc:
            sys.stderr.write(f"[WARNING] {method_key} discovery failed: {exc}\n")
            return
        for rec in raw:
            # The individual adapters already ran their own scope filter.
            # We re-check the canonical URL through our shared scope to
            # prevent cross-channel duplicates.
            url = rec["discovered_url"]
            canonical = _canonicalize_url(url, source_config)
            if canonical not in scope._visited:
                scope._visited.add(canonical)
                all_records.append(rec)

    _run(discover_from_html,    "html_listing")
    _run(discover_from_feed,    "rss")
    _run(discover_from_sitemap, "sitemap")

    return all_records


def _canonicalize_url(url: str, config: Dict[str, Any]) -> str:
    """Lightweight canonical form for cross-channel dedup (mirrors scope_filter logic)."""
    try:
        parts = urllib.parse.urlsplit(url.strip())
    except Exception:
        return url

    ignored = config.get("ignored_query_params", [])
    if config.get("strip_query_params", False):
        query = ""
    elif ignored:
        params = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if k not in ignored]
        query = urllib.parse.urlencode(params)
    else:
        query = parts.query

    return urllib.parse.urlunsplit((
        parts.scheme.lower(), parts.netloc.lower(),
        parts.path, query, ""
    ))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json, argparse

    _FIXTURES = os.path.join(_HERE, "fixtures")
    _DEMO_CONFIG: Dict[str, Any] = {
        "source_name": "iima",
        "allowed_hostname": "www.iima.ac.in",
        "allowed_path_prefixes": ["/the-institute/events", "/news"],
        "excluded_path_prefixes": ["/login", "/search", "/calendar", "/filter",
                                   "/sites/default/files"],
        "allow_external": False,
        "html_fixture":     os.path.join(_FIXTURES, "fixture_html.html"),
        "feed_fixture":     os.path.join(_FIXTURES, "fixture_feed.xml"),
        "sitemap_fixture":  os.path.join(_FIXTURES, "fixture_sitemap.xml"),
    }

    parser = argparse.ArgumentParser(description="Assignment 3 — Aggregator Discovery Interface")
    parser.add_argument("--channel", choices=["all", "html", "feed", "sitemap"], default="all")
    args = parser.parse_args()

    if args.channel == "html":
        results = discover_from_html(_DEMO_CONFIG)
    elif args.channel == "feed":
        results = discover_from_feed(_DEMO_CONFIG)
    elif args.channel == "sitemap":
        results = discover_from_sitemap(_DEMO_CONFIG)
    else:
        results = discover_items(_DEMO_CONFIG)

    print(json.dumps(results, indent=2))
    print(f"\n// Total: {len(results)} records", file=sys.stderr)
