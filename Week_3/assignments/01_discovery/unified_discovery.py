#!/usr/bin/env python3
"""unified_discovery.py - Unified Discovery Record Engine (Assignment 1B)

Normalizes candidate event items discovered from disparate channels:
- HTML card listings
- RSS / Atom syndication feeds
- XML Sitemaps / Sitemap indexes

All adapters emit the identical canonical shape:
{
    "source_name": str,
    "discovered_url": str,
    "discovery_method": "html_listing" | "rss" | "sitemap",
    "discovered_title": Optional[str],
    "source_timestamp": Optional[str],
    "discovered_at": str (ISO 8601 UTC)
}

Downstream consumers can process, deduplicate, and route candidate URLs
without needing any awareness of the upstream discovery mechanism.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
import sys
from typing import Any, Dict, List, Optional
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import feedparser  # type: ignore


DEFAULT_SOURCE_NAME = "iima"
DEFAULT_HTML_URL = "https://www.iima.ac.in/the-institute/events"
DEFAULT_RSS_URL = "https://www.iima.ac.in/rss.xml"
DEFAULT_SITEMAP_FIXTURE = os.path.join(
    os.path.dirname(__file__), "fixtures", "sample_sitemap.xml"
)
DEFAULT_HTML_FIXTURE = os.path.join(
    os.path.dirname(__file__), "fixtures", "sample_html_listing.html"
)
DEFAULT_FEED_FIXTURE = os.path.join(
    os.path.dirname(__file__), "fixtures", "sample_feed.xml"
)


@dataclass(frozen=True)
class DiscoveryRecord:
    """Canonical discovery candidate model."""

    source_name: str
    discovered_url: str
    discovery_method: str  # 'html_listing', 'rss', or 'sitemap'
    discovered_title: Optional[str]
    source_timestamp: Optional[str]
    discovered_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to primitive dictionary."""
        return asdict(self)

    @classmethod
    def create(
        cls,
        source_name: str,
        discovered_url: str,
        discovery_method: str,
        discovered_title: Optional[str] = None,
        source_timestamp: Optional[str] = None,
        discovered_at: Optional[str] = None,
    ) -> DiscoveryRecord:
        """Factory creating a validated discovery record."""
        if not discovered_url:
            raise ValueError("discovered_url cannot be empty")
        if discovery_method not in {"html_listing", "rss", "sitemap"}:
            raise ValueError(
                f"Invalid discovery_method '{discovery_method}'. Must be 'html_listing', 'rss', or 'sitemap'."
            )

        now_iso = (
            discovered_at
            if discovered_at
            else datetime.now(timezone.utc).isoformat()
        )

        clean_title = discovered_title.strip() if discovered_title else None
        clean_timestamp = source_timestamp.strip() if source_timestamp else None

        return cls(
            source_name=source_name,
            discovered_url=discovered_url.strip(),
            discovery_method=discovery_method,
            discovered_title=clean_title,
            source_timestamp=clean_timestamp,
            discovered_at=now_iso,
        )


def _fetch_content(source_or_url: str) -> bytes:
    """Fetch content from local file or HTTP URL."""
    if os.path.isfile(source_or_url):
        with open(source_or_url, "rb") as f:
            return f.read()

    req = urllib.request.Request(
        source_or_url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


class DiscoveryAdapter:
    """Base class for discovery adapters."""

    def __init__(self, source_name: str = DEFAULT_SOURCE_NAME):
        self.source_name = source_name

    def discover(self, source_input: str, limit: Optional[int] = None) -> List[DiscoveryRecord]:
        raise NotImplementedError


class HtmlListingAdapter(DiscoveryAdapter):
    """Discovers items from server-rendered HTML listing cards."""

    def __init__(
        self,
        source_name: str = DEFAULT_SOURCE_NAME,
        base_url: str = "https://www.iima.ac.in",
    ):
        super().__init__(source_name)
        self.base_url = base_url

    def discover(self, source_input: str, limit: Optional[int] = None) -> List[DiscoveryRecord]:
        html_bytes = _fetch_content(source_input)
        soup = BeautifulSoup(html_bytes.decode("utf-8", errors="ignore"), "html.parser")
        now_iso = datetime.now(timezone.utc).isoformat()

        records: List[DiscoveryRecord] = []
        rows = soup.select(".views-row")

        for row in rows:
            # Find candidate anchor tag
            a_tag = row.find("a")
            if not a_tag or not a_tag.get("href"):
                continue

            href = a_tag["href"].strip()
            # Normalize to fully-qualified URL
            canonical_url = urllib.parse.urljoin(self.base_url, href)

            title = a_tag.get_text(strip=True) or None

            # Optional: Extract date text if present in card
            date_elem = row.select_one(".events-style-1-date, .date, time")
            source_ts = None
            if date_elem:
                source_ts = " ".join(date_elem.stripped_strings)

            record = DiscoveryRecord.create(
                source_name=self.source_name,
                discovered_url=canonical_url,
                discovery_method="html_listing",
                discovered_title=title,
                source_timestamp=source_ts,
                discovered_at=now_iso,
            )
            records.append(record)
            if limit and len(records) >= limit:
                break

        return records


class RssFeedAdapter(DiscoveryAdapter):
    """Discovers items from RSS / Atom syndication feeds."""

    def discover(self, source_input: str, limit: Optional[int] = None) -> List[DiscoveryRecord]:
        feed_bytes = _fetch_content(source_input)
        parsed = feedparser.parse(feed_bytes)
        now_iso = datetime.now(timezone.utc).isoformat()

        records: List[DiscoveryRecord] = []
        for entry in parsed.entries:
            # Resolve link
            url = entry.get("link")
            if not url and "links" in entry and entry["links"]:
                url = entry["links"][0].get("href")
            if not url:
                url = entry.get("id")

            if not url:
                continue

            title = entry.get("title")
            published = (
                entry.get("published")
                or entry.get("updated")
                or entry.get("created")
            )

            record = DiscoveryRecord.create(
                source_name=self.source_name,
                discovered_url=url,
                discovery_method="rss",
                discovered_title=title,
                source_timestamp=published,
                discovered_at=now_iso,
            )
            records.append(record)
            if limit and len(records) >= limit:
                break

        return records


class SitemapAdapter(DiscoveryAdapter):
    """Discovers items from XML Sitemaps conforming to sitemaps.org protocol."""

    @staticmethod
    def _strip_ns(tag: str) -> str:
        return tag.split("}", 1)[1] if "}" in tag else tag

    def discover(self, source_input: str, limit: Optional[int] = None) -> List[DiscoveryRecord]:
        xml_bytes = _fetch_content(source_input)
        root = ET.fromstring(xml_bytes)
        now_iso = datetime.now(timezone.utc).isoformat()

        records: List[DiscoveryRecord] = []
        for child in root:
            tag_name = self._strip_ns(child.tag).lower()
            if tag_name in {"url", "sitemap"}:
                loc_val = None
                lastmod_val = None
                for sub in child:
                    sub_tag = self._strip_ns(sub.tag).lower()
                    if sub_tag == "loc" and sub.text:
                        loc_val = sub.text.strip()
                    elif sub_tag == "lastmod" and sub.text:
                        lastmod_val = sub.text.strip()

                if loc_val:
                    # Sitemaps omit titles by protocol design
                    record = DiscoveryRecord.create(
                        source_name=self.source_name,
                        discovered_url=loc_val,
                        discovery_method="sitemap",
                        discovered_title=None,
                        source_timestamp=lastmod_val,
                        discovered_at=now_iso,
                    )
                    records.append(record)
                    if limit and len(records) >= limit:
                        break

        return records


def run_discovery_pipeline(
    source_name: str = DEFAULT_SOURCE_NAME,
    limit: int = 3,
    use_fixtures: bool = False,
) -> Dict[str, List[Dict[str, Any]]]:
    """Execute all discovery adapters and return unified records."""
    html_src = DEFAULT_HTML_FIXTURE if use_fixtures else DEFAULT_HTML_URL
    rss_src = DEFAULT_FEED_FIXTURE if use_fixtures else DEFAULT_RSS_URL
    sitemap_src = DEFAULT_SITEMAP_FIXTURE  # Target lacks XML sitemap, uses protocol fixture

    html_adapter = HtmlListingAdapter(source_name=source_name)
    rss_adapter = RssFeedAdapter(source_name=source_name)
    sitemap_adapter = SitemapAdapter(source_name=source_name)

    results: Dict[str, List[Dict[str, Any]]] = {}

    try:
        html_records = html_adapter.discover(html_src, limit=limit)
        results["html_listing"] = [r.to_dict() for r in html_records]
    except Exception as exc:
        results["html_listing"] = []
        sys.stderr.write(f"[WARNING] HTML Discovery failed ({exc}), falling back to fixture.\n")
        html_records = html_adapter.discover(DEFAULT_HTML_FIXTURE, limit=limit)
        results["html_listing"] = [r.to_dict() for r in html_records]

    try:
        rss_records = rss_adapter.discover(rss_src, limit=limit)
        results["rss"] = [r.to_dict() for r in rss_records]
    except Exception as exc:
        results["rss"] = []
        sys.stderr.write(f"[WARNING] RSS Discovery failed ({exc}), falling back to fixture.\n")
        rss_records = rss_adapter.discover(DEFAULT_FEED_FIXTURE, limit=limit)
        results["rss"] = [r.to_dict() for r in rss_records]

    sitemap_records = sitemap_adapter.discover(sitemap_src, limit=limit)
    results["sitemap"] = [r.to_dict() for r in sitemap_records]

    return results


def print_unified_report(results: Dict[str, List[Dict[str, Any]]]) -> None:
    """Print comparative report displaying normalized discovery records."""
    print("=" * 80)
    print("UNIFIED DISCOVERY RECORD REPORT (Assignment 1B)")
    print("=" * 80)
    print(
        "Demonstrating consistent record normalization across disparate discovery channels:\n"
        "- HTML Card Listing\n"
        "- RSS 2.0 Feed\n"
        "- XML Sitemap (<urlset>)"
    )
    print("=" * 80)

    for method, records in results.items():
        print(f"\n>>> CHANNEL: [{method.upper()}] ({len(records)} candidate items)")
        print("-" * 80)
        for idx, rec in enumerate(records, 1):
            print(f"Record {idx}:")
            print(json.dumps(rec, indent=2))
        print()

    print("=" * 80)
    print("CHECKPOINT VERIFICATION:")
    print("Downstream consumer verification:")
    all_records = [rec for recs in results.values() for rec in recs]
    print(f"Total unified candidate records collected: {len(all_records)}")
    all_keys = {tuple(sorted(rec.keys())) for rec in all_records}
    print(f"Schema consistency: {len(all_keys) == 1} (All records share exact keys: {all_keys.pop()})")
    print("=" * 80)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unified Discovery Record Generator (Assignment 1B)"
    )
    parser.add_argument(
        "--source-name",
        default=DEFAULT_SOURCE_NAME,
        help="Source identifier (default: iima)",
    )
    parser.add_argument(
        "--channel",
        choices=["all", "html", "rss", "sitemap"],
        default="all",
        help="Discovery channel to execute (default: all)",
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=3,
        help="Max items to sample per channel (default: 3)",
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Run entirely using local offline fixtures",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON array of records",
    )

    args = parser.parse_args()

    results = run_discovery_pipeline(
        source_name=args.source_name,
        limit=args.limit,
        use_fixtures=args.fixture,
    )

    if args.channel != "all":
        key = "html_listing" if args.channel == "html" else args.channel
        results = {key: results.get(key, [])}

    if args.json:
        # Flatten all unified records into a single list
        flattened = [rec for recs in results.values() for rec in recs]
        print(json.dumps(flattened, indent=2))
    else:
        print_unified_report(results)


if __name__ == "__main__":
    main()
