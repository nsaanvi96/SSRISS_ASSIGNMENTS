#!/usr/bin/env python3
"""inspect_sitemap.py - Sitemap & Sitemap Index Inspector (Assignment 1A)

Parses an XML sitemap or sitemap index using Python's xml.etree.ElementTree and
prints a controlled sample of candidate items:
- Discovered URL (<loc>)
- Title (N/A in Sitemaps protocol)
- Published / Updated / Last modification (<lastmod>)
- Discovery source metadata (<urlset> vs <sitemapindex>)

Target: IIM Ahmedabad (https://iima.ac.in/sitemap.xml)
Note: robots.txt declares https://iima.ac.in/sitemap.xml, but the remote server returns 404.
The script gracefully detects this condition and uses local fixtures
(fixtures/sample_sitemap.xml and fixtures/sample_sitemap_index.xml) per assignment instructions.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET


DEFAULT_REMOTE_URL = "https://iima.ac.in/sitemap.xml"
DEFAULT_FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "sample_sitemap.xml"
)
DEFAULT_INDEX_FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "sample_sitemap_index.xml"
)

# Standard Sitemaps XML schema namespaces
SITEMAP_NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
}


def fetch_xml_content(source: str) -> bytes:
    """Fetch raw XML bytes from either a local file path or remote HTTP(S) URL."""
    if os.path.isfile(source):
        with open(source, "rb") as f:
            return f.read()

    req = urllib.request.Request(
        source,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


def strip_tag_namespace(tag: str) -> str:
    """Remove XML namespace URI prefix, e.g., '{http://...}url' -> 'url'."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_sitemap_xml(xml_bytes: bytes, source_label: str) -> Dict[str, Any]:
    """Parse sitemap XML content supporting both <urlset> and <sitemapindex> roots."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"XML parse error in {source_label}: {exc}") from exc

    root_tag = strip_tag_namespace(root.tag).lower()
    entries: List[Dict[str, Optional[str]]] = []

    if root_tag == "urlset":
        discovery_source = "sitemap:urlset"
        # Find all <url> children regardless of namespace prefix
        for child in root:
            if strip_tag_namespace(child.tag).lower() == "url":
                loc_val: Optional[str] = None
                lastmod_val: Optional[str] = None

                for elem in child:
                    tag_name = strip_tag_namespace(elem.tag).lower()
                    if tag_name == "loc" and elem.text:
                        loc_val = elem.text.strip()
                    elif tag_name == "lastmod" and elem.text:
                        lastmod_val = elem.text.strip()

                if loc_val:
                    entries.append(
                        {
                            "url": loc_val,
                            "title": None,  # Sitemaps protocol does not include title tags
                            "lastmod": lastmod_val,
                            "discovery_source": discovery_source,
                        }
                    )

    elif root_tag == "sitemapindex":
        discovery_source = "sitemap:sitemapindex"
        # Find all <sitemap> children in index
        for child in root:
            if strip_tag_namespace(child.tag).lower() == "sitemap":
                loc_val = None
                lastmod_val = None

                for elem in child:
                    tag_name = strip_tag_namespace(elem.tag).lower()
                    if tag_name == "loc" and elem.text:
                        loc_val = elem.text.strip()
                    elif tag_name == "lastmod" and elem.text:
                        lastmod_val = elem.text.strip()

                if loc_val:
                    entries.append(
                        {
                            "url": loc_val,
                            "title": None,  # Child sitemap pointer, no title
                            "lastmod": lastmod_val,
                            "discovery_source": discovery_source,
                        }
                    )
    else:
        raise ValueError(
            f"Unrecognized sitemap root element '{root.tag}'. Expected <urlset> or <sitemapindex>."
        )

    return {
        "source": source_label,
        "root_type": root_tag,
        "total_entries": len(entries),
        "entries": entries,
    }


def inspect_sitemap(
    source: str, sample_size: int = 5
) -> Dict[str, Any]:
    """Inspect a sitemap from URL or file, returning parsed sample records."""
    is_file = os.path.isfile(source)
    xml_bytes = fetch_xml_content(source)
    parsed = parse_sitemap_xml(xml_bytes, source_label=source)

    sample = parsed["entries"][:sample_size]
    return {
        "source": source,
        "is_local_fixture": is_file,
        "root_type": parsed["root_type"],
        "total_entries": parsed["total_entries"],
        "sample_size": len(sample),
        "sample": sample,
    }


def print_sitemap_report(result: Dict[str, Any]) -> None:
    """Print readable report of discovered sitemap items."""
    print("=" * 70)
    print("SITEMAP INSPECTION REPORT (Assignment 1A)")
    print("=" * 70)
    print(f"Source URL / Path : {result['source']}")
    print(f"Fixture Fallback? : {'Yes (Local Sample Fixture)' if result['is_local_fixture'] else 'No (Live Remote URL)'}")
    print(f"Sitemap Type      : <{result['root_type']}> ({'Standard URLSet' if result['root_type'] == 'urlset' else 'Sitemap Index'})")
    print(f"Total Items Found : {result['total_entries']}")
    print(f"Sample Items Shown: {result['sample_size']}")
    print("-" * 70)

    for idx, item in enumerate(result["sample"], 1):
        print(f"[{idx}] Candidate Item:")
        print(f"    URL              : {item.get('url') or 'N/A'}")
        print(f"    Title            : {item.get('title') if item.get('title') is not None else 'None (Sitemaps protocol omits titles)'}")
        print(f"    Published/Lastmod: {item.get('lastmod') or 'None (optional in protocol)'}")
        print(f"    Discovery Source : {item.get('discovery_source') or 'sitemap'}")
        print()
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect XML Sitemap or Sitemap Index using xml.etree.ElementTree."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_REMOTE_URL,
        help=f"Sitemap URL to inspect (default: {DEFAULT_REMOTE_URL})",
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Use local sample sitemap fixture (fixtures/sample_sitemap.xml)",
    )
    parser.add_argument(
        "--index-fixture",
        action="store_true",
        help="Use local sample sitemap index fixture (fixtures/sample_sitemap_index.xml)",
    )
    parser.add_argument(
        "--file",
        help="Path to custom local XML sitemap file",
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

    args = parser.parse_args()

    # Determine source to parse
    if args.file:
        source = args.file
    elif args.index_fixture:
        source = DEFAULT_INDEX_FIXTURE_PATH
    elif args.fixture:
        source = DEFAULT_FIXTURE_PATH
    else:
        source = args.url

    try:
        results = inspect_sitemap(source=source, sample_size=args.sample_size)
    except urllib.error.HTTPError as http_err:
        # Expected case for targets like IIMA where robots.txt advertises sitemap.xml but server returns 404
        print(f"[TARGET AUDIT NOTICE] Fetching '{source}' returned HTTP {http_err.code}: {http_err.reason}.")
        print("[TARGET AUDIT NOTICE] Target does not expose a functional XML sitemap at this endpoint.")
        print(f"[TARGET AUDIT NOTICE] Loading local technical exercise fixture: {DEFAULT_FIXTURE_PATH}\n")
        results = inspect_sitemap(source=DEFAULT_FIXTURE_PATH, sample_size=args.sample_size)
    except Exception as exc:
        print(f"[TARGET AUDIT NOTICE] Error fetching '{source}': {exc}")
        print(f"[TARGET AUDIT NOTICE] Loading local technical exercise fixture: {DEFAULT_FIXTURE_PATH}\n")
        results = inspect_sitemap(source=DEFAULT_FIXTURE_PATH, sample_size=args.sample_size)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_sitemap_report(results)


if __name__ == "__main__":
    main()
