#!/usr/bin/env python3
"""test_scope_filter.py - Tests for Assignment 2: URL Scope Filter

Run with:   python -m pytest assignments/02_scope/test_scope_filter.py -v
        or: python assignments/02_scope/test_scope_filter.py
"""

import sys
import os

# Allow running from any working directory
sys.path.insert(0, os.path.dirname(__file__))

from scope_filter import is_allowed_item_url, UrlScopeFilter


# ---------------------------------------------------------------------------
# Shared test config (mirrors the IIMA scenario)
# ---------------------------------------------------------------------------

BASE_CONFIG = {
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


# ---------------------------------------------------------------------------
# Helper: always uses a fresh visited set (stateless per call)
# ---------------------------------------------------------------------------

def check(url: str, config: dict = BASE_CONFIG) -> bool:
    return is_allowed_item_url(url, config)


# ===========================================================================
# 1. VALID ALLOWED URLs
# ===========================================================================

class TestValidAllowed:

    def test_valid_event_detail(self):
        """A deep event detail page should be allowed."""
        url = "https://www.iima.ac.in/the-institute/events/annual-management-retreat-2026"
        assert check(url) is True

    def test_valid_news_detail(self):
        """A news article under /news should be allowed."""
        url = "https://www.iima.ac.in/news/iima-ranked-1-in-india-2026"
        assert check(url) is True

    def test_valid_research_publication(self):
        """Research publication under allowed prefix should be allowed."""
        url = "https://www.iima.ac.in/research/publications/working-paper-2026-01"
        assert check(url) is True

    def test_valid_event_with_non_tracking_query(self):
        """An event URL with a non-tracking query param should be kept (non-ignored param)."""
        url = "https://www.iima.ac.in/the-institute/events/seminar?page=2"
        assert check(url) is True


# ===========================================================================
# 2. EXTERNAL / SAME-SITE BOUNDARY
# ===========================================================================

class TestExternalLinks:

    def test_external_registration_site_rejected(self):
        """Eventbrite link must be rejected when allow_external=False."""
        url = "https://www.eventbrite.com/e/iima-annual-retreat-tickets-123456"
        assert check(url) is False

    def test_social_media_link_rejected(self):
        """Twitter/X link must be rejected."""
        url = "https://twitter.com/IIMAhmedabad/status/1776543210987654321"
        assert check(url) is False

    def test_subdomain_treated_as_external(self):
        """alumni.iima.ac.in is a different hostname - rejected when allow_external=False."""
        url = "https://alumni.iima.ac.in/events/homecoming-2026"
        assert check(url) is False

    def test_external_link_allowed_when_config_permits(self):
        """With allow_external=True an off-domain URL should not be rejected for hostname alone."""
        # NOTE: it still needs to pass path-prefix checks etc.
        config = dict(BASE_CONFIG)
        config["allow_external"] = True
        config["allowed_path_prefixes"] = []   # no path restriction
        url = "https://www.eventbrite.com/e/iima-retreat"
        assert is_allowed_item_url(url, config) is True


# ===========================================================================
# 3. EXCLUDED PATH PREFIXES
# ===========================================================================

class TestExcludedPaths:

    def test_login_url_rejected(self):
        """Login page must be rejected."""
        url = "https://www.iima.ac.in/login?destination=/events"
        assert check(url) is False

    def test_search_url_rejected(self):
        """Search page must be rejected (infinite URL space risk)."""
        url = "https://www.iima.ac.in/search?q=conference"
        assert check(url) is False

    def test_calendar_url_rejected(self):
        """Calendar pages generate infinite month/day URLs - must be rejected."""
        url = "https://www.iima.ac.in/calendar/2026-10"
        assert check(url) is False

    def test_filter_url_rejected(self):
        """Filter URLs create combinatorial explosion - must be rejected."""
        url = "https://www.iima.ac.in/filter/events?type=seminar&month=10"
        assert check(url) is False

    def test_admin_url_rejected(self):
        """Admin path must be rejected."""
        url = "https://www.iima.ac.in/admin/content"
        assert check(url) is False


# ===========================================================================
# 4. BINARY / NON-HTML RESOURCES
# ===========================================================================

class TestBinaryExtensions:

    def test_pdf_rejected(self):
        """PDF links must be rejected (binary extension filter)."""
        url = "https://www.iima.ac.in/sites/default/files/brochure.pdf"
        assert check(url) is False

    def test_pdf_under_allowed_prefix_still_rejected(self):
        """A PDF under an allowed prefix must still be rejected via extension check."""
        url = "https://www.iima.ac.in/the-institute/events/agenda.pdf"
        assert check(url) is False

    def test_docx_rejected(self):
        url = "https://www.iima.ac.in/news/report.docx"
        assert check(url) is False

    def test_image_rejected(self):
        url = "https://www.iima.ac.in/the-institute/events/banner.jpg"
        assert check(url) is False


# ===========================================================================
# 5. PATH-PREFIX ALLOWLIST (out-of-scope internal pages)
# ===========================================================================

class TestPathPrefixAllowlist:

    def test_about_leadership_rejected(self):
        """Internal page outside allowed prefixes must be rejected."""
        url = "https://www.iima.ac.in/about/leadership"
        assert check(url) is False

    def test_programs_rejected(self):
        """Programs page not in allowed prefixes must be rejected."""
        url = "https://www.iima.ac.in/programmes/pgp"
        assert check(url) is False

    def test_no_allowlist_accepts_all_same_host(self):
        """When allowed_path_prefixes is empty, any same-host path is in scope."""
        config = dict(BASE_CONFIG)
        config["allowed_path_prefixes"] = []
        config["excluded_path_prefixes"] = []
        url = "https://www.iima.ac.in/about/leadership"
        assert is_allowed_item_url(url, config) is True


# ===========================================================================
# 6. URL CANONICALIZATION AND DEDUPLICATION
# ===========================================================================

class TestCanonicalizationAndDedup:

    def test_fragment_stripped_for_dedup(self):
        """Two URLs differing only by fragment should be treated as one."""
        visited = set()
        url_base = "https://www.iima.ac.in/the-institute/events/retreat-2026"
        url_frag = "https://www.iima.ac.in/the-institute/events/retreat-2026#agenda"

        # First call - fresh URL, allowed
        r1 = is_allowed_item_url(url_base, BASE_CONFIG, visited)
        assert r1 is True

        # Second call with fragment - canonical is same as base, must be rejected as duplicate
        r2 = is_allowed_item_url(url_frag, BASE_CONFIG, visited)
        assert r2 is False

    def test_tracking_param_stripped_for_dedup(self):
        """utm_source tracking param should be stripped so the URL counts as seen."""
        visited = set()
        url_clean = "https://www.iima.ac.in/the-institute/events/retreat-2026"
        url_tracked = "https://www.iima.ac.in/the-institute/events/retreat-2026?utm_source=newsletter"

        r1 = is_allowed_item_url(url_clean, BASE_CONFIG, visited)
        assert r1 is True

        r2 = is_allowed_item_url(url_tracked, BASE_CONFIG, visited)
        assert r2 is False

    def test_multiple_tracking_params_stripped(self):
        """Multiple tracking params all stripped - counts as duplicate of clean URL."""
        visited = set()
        url_clean = "https://www.iima.ac.in/news/iima-ranked-1"
        url_tracked = "https://www.iima.ac.in/news/iima-ranked-1?utm_source=email&utm_campaign=weekly&fbclid=abc123"

        is_allowed_item_url(url_clean, BASE_CONFIG, visited)
        r2 = is_allowed_item_url(url_tracked, BASE_CONFIG, visited)
        assert r2 is False

    def test_non_tracking_query_not_collapsed(self):
        """A genuine non-tracking query param must NOT be stripped - treated as distinct URL."""
        visited = set()
        url_p1 = "https://www.iima.ac.in/the-institute/events?page=1"
        url_p2 = "https://www.iima.ac.in/the-institute/events?page=2"

        r1 = is_allowed_item_url(url_p1, BASE_CONFIG, visited)
        r2 = is_allowed_item_url(url_p2, BASE_CONFIG, visited)
        assert r1 is True
        assert r2 is True

    def test_exact_duplicate_rejected(self):
        """Exact same URL submitted twice - second must be rejected."""
        visited = set()
        url = "https://www.iima.ac.in/news/iima-ranked-1"
        r1 = is_allowed_item_url(url, BASE_CONFIG, visited)
        r2 = is_allowed_item_url(url, BASE_CONFIG, visited)
        assert r1 is True
        assert r2 is False

    def test_strip_query_params_config(self):
        """With strip_query_params=True, all params are stripped before dedup."""
        config = dict(BASE_CONFIG)
        config["strip_query_params"] = True

        visited = set()
        url_p1 = "https://www.iima.ac.in/the-institute/events?page=1"
        url_p2 = "https://www.iima.ac.in/the-institute/events?page=2"

        r1 = is_allowed_item_url(url_p1, config, visited)
        r2 = is_allowed_item_url(url_p2, config, visited)
        assert r1 is True
        assert r2 is False  # collapsed to same canonical


# ===========================================================================
# 7. SCHEME CHECKS
# ===========================================================================

class TestSchemeChecks:

    def test_http_allowed(self):
        config = dict(BASE_CONFIG)
        config["allowed_path_prefixes"] = []
        url = "http://www.iima.ac.in/the-institute/events/retreat-2026"
        assert is_allowed_item_url(url, config) is True

    def test_ftp_rejected(self):
        url = "ftp://www.iima.ac.in/files/report.pdf"
        assert check(url) is False

    def test_mailto_rejected(self):
        url = "mailto:events@iima.ac.in"
        assert check(url) is False

    def test_javascript_rejected(self):
        url = "javascript:void(0)"
        assert check(url) is False


# ===========================================================================
# 8. STATEFUL UrlScopeFilter CLASS
# ===========================================================================

class TestUrlScopeFilter:

    def test_stateful_dedup_across_calls(self):
        """The class should remember visited URLs across is_allowed() calls."""
        scope = UrlScopeFilter(BASE_CONFIG)
        url = "https://www.iima.ac.in/the-institute/events/retreat-2026"
        assert scope.is_allowed(url) is True
        assert scope.is_allowed(url) is False  # seen on second call

    def test_reset_visited_clears_memory(self):
        """reset_visited() should allow the same URL to be seen again."""
        scope = UrlScopeFilter(BASE_CONFIG)
        url = "https://www.iima.ac.in/the-institute/events/retreat-2026"
        scope.is_allowed(url)
        scope.reset_visited()
        assert scope.is_allowed(url) is True

    def test_visited_count_increments(self):
        scope = UrlScopeFilter(BASE_CONFIG)
        urls = [
            "https://www.iima.ac.in/the-institute/events/event-a",
            "https://www.iima.ac.in/the-institute/events/event-b",
            "https://www.iima.ac.in/news/news-a",
        ]
        for url in urls:
            scope.is_allowed(url)
        assert scope.visited_count == 3


# ===========================================================================
# Standalone runner (no pytest required)
# ===========================================================================

if __name__ == "__main__":
    import traceback

    test_classes = [
        TestValidAllowed,
        TestExternalLinks,
        TestExcludedPaths,
        TestBinaryExtensions,
        TestPathPrefixAllowlist,
        TestCanonicalizationAndDedup,
        TestSchemeChecks,
        TestUrlScopeFilter,
    ]

    passed = 0
    failed = 0

    for cls in test_classes:
        instance = cls()
        methods = [m for m in dir(instance) if m.startswith("test_")]
        for method in methods:
            try:
                getattr(instance, method)()
                print(f"  PASS  {cls.__name__}.{method}")
                passed += 1
            except Exception as exc:
                print(f"  FAIL  {cls.__name__}.{method}")
                traceback.print_exc()
                failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    sys.exit(0 if failed == 0 else 1)
