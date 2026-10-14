#!/usr/bin/env python3
"""test_aggregator_discovery.py - Tests for Assignment 3: Aggregator Discovery Interface

Run with:   python -m pytest Week_3/assignments/03_interface/test_aggregator_discovery.py -v
        or: python Week_3/assignments/03_interface/test_aggregator_discovery.py
"""

from __future__ import annotations

import os
import sys

# Allow running from repo root or from inside 03_interface/
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from aggregator_discovery import (
    DISCOVERY_SCHEMA_KEYS,
    discover_from_feed,
    discover_from_html,
    discover_from_sitemap,
    discover_items,
)

# ---------------------------------------------------------------------------
# Shared fixture paths
# ---------------------------------------------------------------------------

_FIXTURES = os.path.join(_HERE, "fixtures")
_HTML_FIXTURE     = os.path.join(_FIXTURES, "fixture_html.html")
_FEED_FIXTURE     = os.path.join(_FIXTURES, "fixture_feed.xml")
_SITEMAP_FIXTURE  = os.path.join(_FIXTURES, "fixture_sitemap.xml")

_BASE_CONFIG = {
    "source_name":            "iima",
    "allowed_hostname":       "www.iima.ac.in",
    "allowed_path_prefixes":  ["/the-institute/events", "/news"],
    "excluded_path_prefixes": [
        "/login", "/search", "/calendar", "/filter",
        "/sites/default/files",
    ],
    "allow_external": False,
    "html_fixture":    _HTML_FIXTURE,
    "feed_fixture":    _FEED_FIXTURE,
    "sitemap_fixture": _SITEMAP_FIXTURE,
    "ignored_query_params": ["utm_source", "utm_medium", "utm_campaign",
                             "fbclid", "gclid"],
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _assert_schema(records: list) -> None:
    """Every record must have exactly the canonical discovery keys."""
    assert len(records) > 0, "Expected at least one record"
    for rec in records:
        assert set(rec.keys()) == DISCOVERY_SCHEMA_KEYS, (
            f"Schema mismatch: got {set(rec.keys())}"
        )


# ===========================================================================
# 1. test_html_discovery
# ===========================================================================

class TestHtmlDiscovery:

    def test_html_discovery_returns_records(self):
        """discover_from_html should return at least one record from fixture."""
        records = discover_from_html(_BASE_CONFIG)
        assert len(records) >= 1

    def test_html_discovery_method_field(self):
        """All HTML records must carry discovery_method == 'html_listing'."""
        records = discover_from_html(_BASE_CONFIG)
        for rec in records:
            assert rec["discovery_method"] == "html_listing"

    def test_html_discovery_schema(self):
        """HTML records must have the canonical 6-key schema."""
        _assert_schema(discover_from_html(_BASE_CONFIG))

    def test_html_discovery_scope_applied(self):
        """Login and external links in the fixture must be filtered out."""
        records = discover_from_html(_BASE_CONFIG)
        urls = [r["discovered_url"] for r in records]
        assert not any("/login" in u for u in urls),       "Login URL leaked through"
        assert not any("twitter.com" in u for u in urls),  "External URL leaked through"

    def test_html_discovery_urls_fully_qualified(self):
        """Relative hrefs must be resolved to absolute URLs."""
        records = discover_from_html(_BASE_CONFIG)
        for rec in records:
            assert rec["discovered_url"].startswith("https://"), (
                f"Not fully qualified: {rec['discovered_url']}"
            )

    def test_html_discovery_source_name(self):
        records = discover_from_html(_BASE_CONFIG)
        for rec in records:
            assert rec["source_name"] == "iima"

    def test_html_discovery_title_extracted(self):
        """Title should be extracted from the anchor text."""
        records = discover_from_html(_BASE_CONFIG)
        assert any(rec["discovered_title"] for rec in records), "No title extracted"

    def test_html_discovery_max_items_limit(self):
        """max_items_per_channel should cap results."""
        cfg = dict(_BASE_CONFIG, max_items_per_channel=1)
        records = discover_from_html(cfg)
        assert len(records) <= 1

    def test_html_discovery_no_source_returns_empty(self):
        """Config with no html_fixture or html_url returns empty list."""
        cfg = {k: v for k, v in _BASE_CONFIG.items()
               if k not in ("html_fixture", "html_url")}
        assert discover_from_html(cfg) == []


# ===========================================================================
# 2. test_feed_discovery
# ===========================================================================

class TestFeedDiscovery:

    def test_feed_discovery_returns_records(self):
        """discover_from_feed should return at least one record."""
        records = discover_from_feed(_BASE_CONFIG)
        assert len(records) >= 1

    def test_feed_discovery_method_field(self):
        """All feed records must carry discovery_method == 'rss'."""
        records = discover_from_feed(_BASE_CONFIG)
        for rec in records:
            assert rec["discovery_method"] == "rss"

    def test_feed_discovery_schema(self):
        """Feed records must have the canonical 6-key schema."""
        _assert_schema(discover_from_feed(_BASE_CONFIG))

    def test_feed_discovery_scope_applied(self):
        """External Eventbrite link in fixture must be filtered out."""
        records = discover_from_feed(_BASE_CONFIG)
        urls = [r["discovered_url"] for r in records]
        assert not any("eventbrite.com" in u for u in urls), (
            "External eventbrite URL leaked through scope filter"
        )

    def test_feed_discovery_source_timestamp_present(self):
        """pubDate should land in source_timestamp field."""
        records = discover_from_feed(_BASE_CONFIG)
        assert any(rec["source_timestamp"] for rec in records), (
            "No source_timestamp found in any feed record"
        )

    def test_feed_discovery_no_source_returns_empty(self):
        cfg = {k: v for k, v in _BASE_CONFIG.items()
               if k not in ("feed_fixture", "feed_url")}
        assert discover_from_feed(cfg) == []


# ===========================================================================
# 3. test_sitemap_discovery
# ===========================================================================

class TestSitemapDiscovery:

    def test_sitemap_discovery_returns_records(self):
        """discover_from_sitemap should return at least one record."""
        records = discover_from_sitemap(_BASE_CONFIG)
        assert len(records) >= 1

    def test_sitemap_discovery_method_field(self):
        """All sitemap records must carry discovery_method == 'sitemap'."""
        records = discover_from_sitemap(_BASE_CONFIG)
        for rec in records:
            assert rec["discovery_method"] == "sitemap"

    def test_sitemap_discovery_schema(self):
        """Sitemap records must have the canonical 6-key schema."""
        _assert_schema(discover_from_sitemap(_BASE_CONFIG))

    def test_sitemap_discovery_scope_applied(self):
        """Out-of-scope URLs (/about/leadership, /search) must be filtered."""
        records = discover_from_sitemap(_BASE_CONFIG)
        urls = [r["discovered_url"] for r in records]
        assert not any("/about/" in u for u in urls),  "/about page leaked"
        assert not any("/search" in u for u in urls),  "/search page leaked"

    def test_sitemap_title_is_none(self):
        """Sitemaps do not carry titles - discovered_title must be None."""
        records = discover_from_sitemap(_BASE_CONFIG)
        for rec in records:
            assert rec["discovered_title"] is None, (
                f"Expected None title, got: {rec['discovered_title']}"
            )

    def test_sitemap_lastmod_in_timestamp(self):
        """lastmod from sitemap XML should appear in source_timestamp."""
        records = discover_from_sitemap(_BASE_CONFIG)
        assert any(rec["source_timestamp"] for rec in records)

    def test_sitemap_discovery_no_source_returns_empty(self):
        cfg = {k: v for k, v in _BASE_CONFIG.items()
               if k not in ("sitemap_fixture", "sitemap_url")}
        assert discover_from_sitemap(cfg) == []


# ===========================================================================
# 4. test_scope_filter  (integration: scope enforced inside discover_items)
# ===========================================================================

class TestScopeFilter:

    def test_scope_rejects_external_from_all_channels(self):
        """discover_items must not return any external URLs."""
        records = discover_items(_BASE_CONFIG)
        for rec in records:
            assert "www.iima.ac.in" in rec["discovered_url"], (
                f"External URL passed scope: {rec['discovered_url']}"
            )

    def test_scope_rejects_excluded_path_prefixes(self):
        """Excluded paths (/login, /search) must not appear in results."""
        records = discover_items(_BASE_CONFIG)
        urls = [r["discovered_url"] for r in records]
        for bad in ("/login", "/search", "/calendar", "/filter"):
            assert not any(bad in u for u in urls), f"{bad!r} URL not filtered"

    def test_scope_allows_only_allowed_prefixes(self):
        """Every accepted URL must start with an allowed path prefix."""
        records = discover_items(_BASE_CONFIG)
        allowed = _BASE_CONFIG["allowed_path_prefixes"]
        for rec in records:
            path = rec["discovered_url"].split("www.iima.ac.in", 1)[-1]
            assert any(path.startswith(p) for p in allowed), (
                f"URL outside allowed prefixes: {rec['discovered_url']}"
            )

    def test_scope_with_no_path_allowlist(self):
        """Without allowed_path_prefixes, any same-host URL is accepted."""
        cfg = dict(_BASE_CONFIG)
        cfg["allowed_path_prefixes"] = []
        cfg["excluded_path_prefixes"] = []
        # Sitemap has /about/leadership — should now pass
        records = discover_from_sitemap(cfg)
        urls = [r["discovered_url"] for r in records]
        assert any("/about/" in u for u in urls), (
            "/about URL should be allowed when no prefix restrictions set"
        )


# ===========================================================================
# 5. test_duplicate_discovery_url
# ===========================================================================

class TestDuplicateDiscoveryUrl:

    def test_no_duplicate_urls_within_single_channel(self):
        """A single channel must not emit the same URL twice."""
        # Feed fixture has 3 valid in-scope items
        records = discover_from_feed(_BASE_CONFIG)
        urls = [r["discovered_url"] for r in records]
        assert len(urls) == len(set(urls)), f"Duplicates within feed: {urls}"

    def test_no_cross_channel_duplicates_in_discover_items(self):
        """discover_items must not emit the same URL from multiple channels.

        The fixture_html, fixture_feed, and fixture_sitemap all share the
        same three event URLs to make cross-channel dedup testable.
        """
        records = discover_items(_BASE_CONFIG)
        urls = [r["discovered_url"] for r in records]
        assert len(urls) == len(set(urls)), (
            f"Cross-channel duplicates detected: {[u for u in urls if urls.count(u) > 1]}"
        )

    def test_fragment_does_not_create_duplicate(self):
        """A URL with #fragment must not be treated as distinct from the base URL."""
        from scope_filter import UrlScopeFilter
        scope_cfg = {
            "allowed_hostname":       "www.iima.ac.in",
            "allowed_path_prefixes":  ["/the-institute/events"],
            "excluded_path_prefixes": [],
            "allow_external":         False,
            "strip_query_params":     False,
            "ignored_query_params":   [],
        }
        scope = UrlScopeFilter(scope_cfg)
        base_url = "https://www.iima.ac.in/the-institute/events/annual-symposium-2026"
        frag_url = base_url + "#schedule"

        r1 = scope.is_allowed(base_url)
        r2 = scope.is_allowed(frag_url)
        assert r1 is True,  "Base URL should be allowed"
        assert r2 is False, "Fragment variant should be rejected as duplicate"

    def test_tracking_param_does_not_create_duplicate(self):
        """URL + utm_source tracking param must collapse to same canonical."""
        from scope_filter import UrlScopeFilter
        scope_cfg = {
            "allowed_hostname":       "www.iima.ac.in",
            "allowed_path_prefixes":  ["/the-institute/events"],
            "excluded_path_prefixes": [],
            "allow_external":         False,
            "strip_query_params":     False,
            "ignored_query_params":   ["utm_source", "utm_campaign"],
        }
        scope = UrlScopeFilter(scope_cfg)
        base  = "https://www.iima.ac.in/the-institute/events/annual-symposium-2026"
        track = base + "?utm_source=newsletter&utm_campaign=oct2026"

        assert scope.is_allowed(base)  is True
        assert scope.is_allowed(track) is False


# ===========================================================================
# 6. Schema consistency — the checkpoint guarantee
# ===========================================================================

class TestSchemaConsistency:

    def test_all_channels_produce_identical_schema(self):
        """HTML, feed, and sitemap records must all share the same 6 keys.

        This is the checkpoint: the same detail parser can consume any record
        regardless of how its URL was discovered.
        """
        html_recs    = discover_from_html(_BASE_CONFIG)
        feed_recs    = discover_from_feed(_BASE_CONFIG)
        sitemap_recs = discover_from_sitemap(_BASE_CONFIG)

        all_recs = html_recs + feed_recs + sitemap_recs
        assert len(all_recs) > 0

        key_sets = {frozenset(rec.keys()) for rec in all_recs}
        assert len(key_sets) == 1, (
            f"Schema divergence across channels: {key_sets}"
        )
        assert key_sets.pop() == DISCOVERY_SCHEMA_KEYS

    def test_discover_items_schema_consistent(self):
        """discover_items (unified) must also produce uniform schema."""
        records = discover_items(_BASE_CONFIG)
        assert len(records) > 0
        key_sets = {frozenset(rec.keys()) for rec in records}
        assert len(key_sets) == 1
        assert key_sets.pop() == DISCOVERY_SCHEMA_KEYS

    def test_discovered_url_always_present(self):
        """discovered_url must be a non-empty string in every record."""
        for rec in discover_items(_BASE_CONFIG):
            assert isinstance(rec["discovered_url"], str)
            assert len(rec["discovered_url"]) > 0

    def test_discovery_method_always_valid(self):
        """discovery_method must be one of the three known values."""
        valid = {"html_listing", "rss", "sitemap"}
        for rec in discover_items(_BASE_CONFIG):
            assert rec["discovery_method"] in valid


# ===========================================================================
# Standalone runner
# ===========================================================================

if __name__ == "__main__":
    import traceback

    test_classes = [
        TestHtmlDiscovery,
        TestFeedDiscovery,
        TestSitemapDiscovery,
        TestScopeFilter,
        TestDuplicateDiscoveryUrl,
        TestSchemaConsistency,
    ]

    passed = failed = 0
    for cls in test_classes:
        inst = cls()
        methods = sorted(m for m in dir(inst) if m.startswith("test_"))
        for method in methods:
            try:
                getattr(inst, method)()
                print(f"  PASS  {cls.__name__}.{method}")
                passed += 1
            except Exception:
                print(f"  FAIL  {cls.__name__}.{method}")
                traceback.print_exc()
                failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    sys.exit(0 if failed == 0 else 1)
