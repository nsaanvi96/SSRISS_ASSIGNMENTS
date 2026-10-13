"""test_unified_discovery.py - Test suite for Assignment 1B Unified Discovery Record.

Verifies that HTML listings, RSS feeds, and XML sitemaps all produce the identical
normalized DiscoveryRecord schema for downstream processing.
"""

import os
from typing import List

import pytest

from unified_discovery import (
    DEFAULT_FEED_FIXTURE,
    DEFAULT_HTML_FIXTURE,
    DEFAULT_SITEMAP_FIXTURE,
    DiscoveryRecord,
    HtmlListingAdapter,
    RssFeedAdapter,
    SitemapAdapter,
)

EXPECTED_SCHEMA_KEYS = {
    "source_name",
    "discovered_url",
    "discovery_method",
    "discovered_title",
    "source_timestamp",
    "discovered_at",
}


def test_html_adapter_produces_unified_shape():
    """Verify HtmlListingAdapter produces canonical records."""
    assert os.path.exists(DEFAULT_HTML_FIXTURE), "HTML fixture must exist"
    adapter = HtmlListingAdapter(source_name="iima")
    records = adapter.discover(DEFAULT_HTML_FIXTURE, limit=5)

    assert len(records) == 5
    for rec in records:
        assert isinstance(rec, DiscoveryRecord)
        d = rec.to_dict()
        assert set(d.keys()) == EXPECTED_SCHEMA_KEYS
        assert d["source_name"] == "iima"
        assert d["discovery_method"] == "html_listing"
        assert d["discovered_url"].startswith("http")
        assert d["discovered_title"] is not None
        assert d["discovered_at"] is not None


def test_rss_adapter_produces_unified_shape():
    """Verify RssFeedAdapter produces canonical records."""
    assert os.path.exists(DEFAULT_FEED_FIXTURE), "Feed fixture must exist"
    adapter = RssFeedAdapter(source_name="iima")
    records = adapter.discover(DEFAULT_FEED_FIXTURE, limit=5)

    assert len(records) == 5
    for rec in records:
        assert isinstance(rec, DiscoveryRecord)
        d = rec.to_dict()
        assert set(d.keys()) == EXPECTED_SCHEMA_KEYS
        assert d["source_name"] == "iima"
        assert d["discovery_method"] == "rss"
        assert d["discovered_url"].startswith("http")
        assert d["discovered_title"] is not None
        assert d["discovered_at"] is not None


def test_sitemap_adapter_produces_unified_shape():
    """Verify SitemapAdapter produces canonical records with None title."""
    assert os.path.exists(DEFAULT_SITEMAP_FIXTURE), "Sitemap fixture must exist"
    adapter = SitemapAdapter(source_name="iima")
    records = adapter.discover(DEFAULT_SITEMAP_FIXTURE, limit=5)

    assert len(records) == 5
    for rec in records:
        assert isinstance(rec, DiscoveryRecord)
        d = rec.to_dict()
        assert set(d.keys()) == EXPECTED_SCHEMA_KEYS
        assert d["source_name"] == "iima"
        assert d["discovery_method"] == "sitemap"
        assert d["discovered_url"].startswith("http")
        # In sitemaps, titles are not provided by specification
        assert d["discovered_title"] is None
        assert d["source_timestamp"] is not None  # lastmod is present
        assert d["discovered_at"] is not None


def test_checkpoint_downstream_consumer_pipeline_agnostic():
    """Checkpoint: Downstream pipeline functions uniformly regardless of origin."""
    html_records = HtmlListingAdapter().discover(DEFAULT_HTML_FIXTURE, limit=2)
    rss_records = RssFeedAdapter().discover(DEFAULT_FEED_FIXTURE, limit=2)
    sitemap_records = SitemapAdapter().discover(DEFAULT_SITEMAP_FIXTURE, limit=2)

    all_records: List[DiscoveryRecord] = html_records + rss_records + sitemap_records
    assert len(all_records) == 6

    # Downstream consumer deduplicates and enqueues tasks based solely on discovered_url
    def downstream_crawl_queue(items: List[DiscoveryRecord]) -> List[str]:
        seen = set()
        queue = []
        for item in items:
            # Downstream consumer relies on canonical attributes without checking method
            url = item.discovered_url
            if url not in seen:
                seen.add(url)
                queue.append(url)
        return queue

    queue = downstream_crawl_queue(all_records)
    assert len(queue) == 6
    for url in queue:
        assert url.startswith("http")


def test_invalid_discovery_method_raises():
    """Verify validation guards on DiscoveryRecord creation."""
    with pytest.raises(ValueError, match="Invalid discovery_method"):
        DiscoveryRecord.create(
            source_name="test",
            discovered_url="https://example.com/item",
            discovery_method="unsupported_method",
        )

    with pytest.raises(ValueError, match="discovered_url cannot be empty"):
        DiscoveryRecord.create(
            source_name="test",
            discovered_url="",
            discovery_method="rss",
        )
