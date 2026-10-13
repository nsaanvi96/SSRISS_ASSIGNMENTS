#!/usr/bin/env python3
"""inspect_feed.py - Feed Discovery Inspector (Assignment 1A)

Inspects an RSS or Atom feed and prints a controlled sample of candidate items:
- Discovered URL
- Item Title
- Published / Updated timestamp
- Discovery source metadata

Target: IIM Ahmedabad Central RSS Feed (https://www.iima.ac.in/rss.xml)
Can also parse local fixtures (fixtures/sample_feed.xml) for offline or reproducible runs.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional
import urllib.request
import xml.etree.ElementTree as ET

try:
    import feedparser  # type: ignore
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False


DEFAULT_FEED_URL = "https://www.iima.ac.in/rss.xml"
DEFAULT_FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "sample_feed.xml"
)


def parse_feed_with_feedparser(
    source_input: str, is_file: bool = False
) -> Dict[str, Any]:
    """Parse feed using feedparser library."""
    if is_file or os.path.exists(source_input):
        parsed = feedparser.parse(source_input)
    else:
        # Pass User-Agent header for remote HTTP fetch
        req = urllib.request.Request(
            source_input, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                content = response.read()
                parsed = feedparser.parse(content)
        except Exception as exc:
            # Fallback to direct parse if request wrapper fails
            parsed = feedparser.parse(source_input)
            if not parsed.entries:
                raise RuntimeError(f"Failed to fetch feed from {source_input}: {exc}") from exc

    feed_version = parsed.get("version", "unknown feed format")
    feed_title = parsed.feed.get("title", "Untitled Feed")

    entries: List[Dict[str, Optional[str]]] = []
    for entry in parsed.entries:
        # Resolve URL (link or id)
        url = entry.get("link")
        if not url and "links" in entry and entry["links"]:
            url = entry["links"][0].get("href")
        if not url:
            url = entry.get("id")

        title = entry.get("title")
        if title:
            title = title.strip().replace("\n", " ")

        # Resolve published / updated timestamp
        published = (
            entry.get("published")
            or entry.get("updated")
            or entry.get("created")
        )

        entries.append(
            {
                "url": url,
                "title": title,
                "published": published,
                "discovery_source": f"feedparser ({feed_version or 'rss/atom'})",
            }
        )

    return {
        "feed_title": feed_title,
        "feed_version": feed_version,
        "total_entries": len(entries),
        "entries": entries,
    }


def parse_feed_with_elementtree(
    source_input: str, is_file: bool = False
) -> Dict[str, Any]:
    """Fallback XML parser using standard library xml.etree.ElementTree."""
    if is_file or os.path.exists(source_input):
        tree = ET.parse(source_input)
        root = tree.getroot()
    else:
        req = urllib.request.Request(
            source_input, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
        root = ET.fromstring(content)

    entries: List[Dict[str, Optional[str]]] = []
    feed_title = "Untitled Feed"
    feed_version = root.tag

    # Check RSS 2.0 / 0.9x (<rss><channel><item>...)
    channel = root.find("channel")
    if channel is not None:
        feed_version = f"rss-{root.attrib.get('version', '2.0')}"
        title_el = channel.find("title")
        if title_el is not None and title_el.text:
            feed_title = title_el.text.strip()

        for item in channel.findall("item"):
            link_el = item.find("link")
            title_el = item.find("title")
            pubdate_el = item.find("pubDate")
            guid_el = item.find("guid")

            url = link_el.text.strip() if link_el is not None and link_el.text else None
            if not url and guid_el is not None and guid_el.text:
                url = guid_el.text.strip()

            title = title_el.text.strip() if title_el is not None and title_el.text else None
            pubdate = pubdate_el.text.strip() if pubdate_el is not None and pubdate_el.text else None

            entries.append(
                {
                    "url": url,
                    "title": title,
                    "published": pubdate,
                    "discovery_source": f"ElementTree ({feed_version})",
                }
            )
    else:
        # Atom feed handling (<feed xmlns="http://www.w3.org/2005/Atom">)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        feed_version = "atom"
        title_el = root.find("atom:title", ns) or root.find("title")
        if title_el is not None and title_el.text:
            feed_title = title_el.text.strip()

        items = root.findall("atom:entry", ns) or root.findall("entry")
        for entry in items:
            link_el = entry.find("atom:link", ns) or entry.find("link")
            url = None
            if link_el is not None:
                url = link_el.attrib.get("href") or link_el.text

            title_el = entry.find("atom:title", ns) or entry.find("title")
            title = title_el.text.strip() if title_el is not None and title_el.text else None

            date_el = (
                entry.find("atom:updated", ns)
                or entry.find("atom:published", ns)
                or entry.find("updated")
                or entry.find("published")
            )
            pubdate = date_el.text.strip() if date_el is not None and date_el.text else None

            entries.append(
                {
                    "url": url,
                    "title": title,
                    "published": pubdate,
                    "discovery_source": "ElementTree (atom)",
                }
            )

    return {
        "feed_title": feed_title,
        "feed_version": feed_version,
        "total_entries": len(entries),
        "entries": entries,
    }


def inspect_feed(
    source: str, sample_size: int = 5, prefer_parser: str = "auto"
) -> Dict[str, Any]:
    """Inspect feed from URL or local path and extract a sample of candidate items."""
    is_file = os.path.isfile(source)

    if prefer_parser == "elementtree" or not HAS_FEEDPARSER:
        data = parse_feed_with_elementtree(source, is_file=is_file)
    else:
        try:
            data = parse_feed_with_feedparser(source, is_file=is_file)
        except Exception as exc:
            # Fallback to ElementTree on error
            sys.stderr.write(f"[WARNING] feedparser encountered error ({exc}), falling back to ElementTree.\n")
            data = parse_feed_with_elementtree(source, is_file=is_file)

    sample = data["entries"][:sample_size]
    return {
        "source": source,
        "is_local_fixture": is_file,
        "feed_title": data["feed_title"],
        "feed_format": data["feed_version"],
        "total_entries": data["total_entries"],
        "sample_size": len(sample),
        "sample": sample,
    }


def print_sample_report(result: Dict[str, Any]) -> None:
    """Print readable report of discovered items."""
    print("=" * 70)
    print("FEED INSPECTION REPORT (Assignment 1A)")
    print("=" * 70)
    print(f"Source URL / Path : {result['source']}")
    print(f"Feed Title        : {result['feed_title']}")
    print(f"Feed Format       : {result['feed_format']}")
    print(f"Total Items Found : {result['total_entries']}")
    print(f"Sample Items Shown: {result['sample_size']}")
    print("-" * 70)

    for idx, item in enumerate(result["sample"], 1):
        print(f"[{idx}] Candidate Item:")
        print(f"    URL              : {item.get('url') or 'N/A'}")
        print(f"    Title            : {item.get('title') or 'N/A'}")
        print(f"    Published/Updated: {item.get('published') or 'N/A'}")
        print(f"    Discovery Source : {item.get('discovery_source') or 'rss/atom'}")
        print()
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect RSS/Atom feed and print controlled sample of candidate items."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_FEED_URL,
        help=f"Feed URL to inspect (default: {DEFAULT_FEED_URL})",
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Use local sample fixture (fixtures/sample_feed.xml) instead of network URL",
    )
    parser.add_argument(
        "--file",
        help="Path to custom local XML feed file",
    )
    parser.add_argument(
        "-n",
        "--sample-size",
        type=int,
        default=5,
        help="Number of candidate items to sample (default: 5)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of human-readable report",
    )
    parser.add_argument(
        "--parser",
        choices=["auto", "feedparser", "elementtree"],
        default="auto",
        help="Parsing engine to use (default: auto)",
    )

    args = parser.parse_args()

    source = args.url
    if args.file:
        source = args.file
    elif args.fixture:
        source = DEFAULT_FIXTURE_PATH

    try:
        results = inspect_feed(
            source=source,
            sample_size=args.sample_size,
            prefer_parser=args.parser,
        )
    except Exception as exc:
        # If network error on remote URL, offer graceful fallback to local fixture
        if not args.fixture and not args.file and os.path.exists(DEFAULT_FIXTURE_PATH):
            sys.stderr.write(
                f"[ERROR] Could not fetch remote feed ({exc}).\n"
                f"[INFO] Falling back to local fixture: {DEFAULT_FIXTURE_PATH}\n\n"
            )
            results = inspect_feed(
                source=DEFAULT_FIXTURE_PATH,
                sample_size=args.sample_size,
                prefer_parser=args.parser,
            )
        else:
            sys.stderr.write(f"Fatal error inspecting feed: {exc}\n")
            sys.exit(1)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_sample_report(results)


if __name__ == "__main__":
    main()
