#!/usr/bin/env python3
"""content_router.py - Multi-Content Central Aggregator Router (Assignment 8)

Classifies discovered items from central aggregators into structural content types:
- event
- announcement
- faculty
- pdf_document
- external_link
- unknown

Core Rules:
1. Classify based strictly on structural evidence (URL patterns, category labels,
   MIME types, and section tags).
2. Do NOT classify based on political, topic, or narrative interpretation.
3. Checkpoint: Unsupported items are recorded as 'unknown', preserving discovery
   records rather than silently dropping them or forcing them into the 'event' schema.
"""

from __future__ import annotations

import os
import re
import urllib.parse
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Item Type Enum
# ---------------------------------------------------------------------------

class ItemType(str, Enum):
    EVENT         = "event"
    ANNOUNCEMENT  = "announcement"
    FACULTY       = "faculty"
    PDF_DOCUMENT  = "pdf_document"
    EXTERNAL_LINK = "external_link"
    UNKNOWN       = "unknown"


# ---------------------------------------------------------------------------
# Evidence Keywords & Category Mappings
# ---------------------------------------------------------------------------

EVENT_CATEGORIES = {
    "event", "events", "seminar", "seminars", "conference", "conferences",
    "webinar", "webinars", "workshop", "workshops", "colloquium", "colloquia",
    "symposium", "lecture", "talk",
}

ANNOUNCEMENT_CATEGORIES = {
    "news", "announcement", "announcements", "notice", "notices",
    "press release", "press_release", "press", "tender", "tenders",
    "circular", "circulars", "procurement",
}

FACULTY_CATEGORIES = {
    "faculty", "faculty directory", "faculty profile", "faculty profiles",
    "professor", "professors", "faculty-research", "academic staff",
}

# Known external domains frequently embedded in central aggregator listings
KNOWN_EXTERNAL_DOMAINS = {
    "forms.gle", "docs.google.com", "eventbrite.com", "eventbrite.in",
    "zoom.us", "twitter.com", "x.com", "linkedin.com", "youtube.com",
    "meet.google.com", "teams.microsoft.com",
}

# Standard internal academic hostnames
DEFAULT_ALLOWED_HOSTNAMES = {"www.iima.ac.in", "iima.ac.in"}


# ---------------------------------------------------------------------------
# Core Classification Function
# ---------------------------------------------------------------------------

def classify_discovered_item(
    discovery_record: Dict[str, Any],
    allowed_hostnames: Optional[set[str]] = None,
) -> str:
    """Classify a discovered item using structural evidence.
    
    Parameters
    ----------
    discovery_record : dict
        A discovery dictionary containing fields such as 'discovered_url',
        'category', 'mime_type', 'section', and 'discovered_title'.
    allowed_hostnames : set[str], optional
        Set of primary internal hostnames. URLs pointing outside this set
        are classified as 'external_link'. Defaults to IIMA hostnames.

    Returns
    -------
    str
        One of: 'event', 'announcement', 'faculty', 'pdf_document',
        'external_link', 'unknown'.
    """
    if allowed_hostnames is None:
        allowed_hostnames = DEFAULT_ALLOWED_HOSTNAMES

    url = (
        discovery_record.get("discovered_url")
        or discovery_record.get("item_url")
        or discovery_record.get("url")
        or ""
    ).strip()

    mime_type = (discovery_record.get("mime_type") or "").strip().lower()
    raw_cat = discovery_record.get("category")
    category = raw_cat.strip().lower() if isinstance(raw_cat, str) else ""
    raw_sec = discovery_record.get("section")
    section = raw_sec.strip().lower() if isinstance(raw_sec, str) else ""

    parsed = urllib.parse.urlsplit(url)
    hostname = (parsed.hostname or "").lower()
    path = parsed.path.lower()

    # -----------------------------------------------------------------------
    # Step 1: MIME Type and Binary Document Sniffing
    # -----------------------------------------------------------------------
    if mime_type == "application/pdf" or path.endswith(".pdf"):
        return ItemType.PDF_DOCUMENT.value

    # -----------------------------------------------------------------------
    # Step 2: External Link Detection
    # -----------------------------------------------------------------------
    # Check if host is a known registration / webinar platform
    if any(hostname == ext or hostname.endswith("." + ext) for ext in KNOWN_EXTERNAL_DOMAINS):
        return ItemType.EXTERNAL_LINK.value

    # Check if host belongs outside the allowed institutional scope
    if hostname and hostname not in allowed_hostnames:
        return ItemType.EXTERNAL_LINK.value

    if section in {"external_rsvp", "registration_links"}:
        return ItemType.EXTERNAL_LINK.value

    # -----------------------------------------------------------------------
    # Step 3: Explicit Category Label Matching
    # -----------------------------------------------------------------------
    if category in EVENT_CATEGORIES:
        return ItemType.EVENT.value

    if category in ANNOUNCEMENT_CATEGORIES:
        return ItemType.ANNOUNCEMENT.value

    if category in FACULTY_CATEGORIES:
        return ItemType.FACULTY.value

    # -----------------------------------------------------------------------
    # Step 4: URL Path Structure Matching
    # -----------------------------------------------------------------------
    # Faculty paths
    if any(p in path for p in ["/faculty-research/faculty/", "/people/faculty/", "/faculty/", "/faculty-profiles/"]):
        return ItemType.FACULTY.value

    # Event paths
    if any(p in path for p in ["/the-institute/events", "/events/", "/seminar/", "/seminars/", "/conference/", "/webinar/"]):
        return ItemType.EVENT.value

    # Announcement paths
    if any(p in path for p in ["/news/", "/announcements/", "/announcement/", "/press-release/", "/tenders/", "/circulars/"]):
        return ItemType.ANNOUNCEMENT.value

    # -----------------------------------------------------------------------
    # Step 5: Section Metadata Matching
    # -----------------------------------------------------------------------
    if section in {"events", "academic_seminars", "online_events"}:
        return ItemType.EVENT.value

    if section in {"press_room", "procurement", "news", "announcements"}:
        return ItemType.ANNOUNCEMENT.value

    if section in {"faculty_profiles", "people", "faculty_directory"}:
        return ItemType.FACULTY.value

    # -----------------------------------------------------------------------
    # Step 6: Safe Conservative Fallback (Unknown)
    # -----------------------------------------------------------------------
    # If the item is a photo gallery, search query, working paper, or unclassified
    # administrative page, record as UNKNOWN rather than guessing or forcing into 'event'.
    return ItemType.UNKNOWN.value


# ---------------------------------------------------------------------------
# Routing Dispatch Layer
# ---------------------------------------------------------------------------

@dataclass
class RoutedItem:
    item_url:       str
    classified_type: str
    target_parser:  str
    is_supported:   bool
    raw_record:     Dict[str, Any]


def route_discovered_item(discovery_record: Dict[str, Any]) -> RoutedItem:
    """Route a discovered item to its content-specific pipeline or unsupported bucket."""
    c_type = classify_discovered_item(discovery_record)
    url = discovery_record.get("discovered_url") or discovery_record.get("item_url") or ""

    if c_type == ItemType.EVENT.value:
        parser = "event_detail_parser"
        supported = True
    elif c_type == ItemType.ANNOUNCEMENT.value:
        parser = "announcement_parser"
        supported = True
    elif c_type == ItemType.FACULTY.value:
        parser = "faculty_profile_parser"
        supported = True
    elif c_type == ItemType.PDF_DOCUMENT.value:
        parser = "pdf_metadata_extractor"
        supported = False  # requires binary parsing pipeline
    elif c_type == ItemType.EXTERNAL_LINK.value:
        parser = "external_link_recorder"
        supported = False  # external URL; out of local detail crawl scope
    else:
        parser = "unsupported_item_handler"
        supported = False

    return RoutedItem(
        item_url=url,
        classified_type=c_type,
        target_parser=parser,
        is_supported=supported,
        raw_record=discovery_record,
    )


# ---------------------------------------------------------------------------
# CLI Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    _HERE = os.path.dirname(os.path.abspath(__file__))
    sample_file = os.path.join(_HERE, "fixtures", "mixed_listing_sample.json")

    if os.path.exists(sample_file):
        with open(sample_file, "r", encoding="utf-8") as f:
            records = json.load(f)

        print("=" * 70)
        print("ASSIGNMENT 8 — MULTI-CONTENT CENTRAL ROUTER DEMO")
        print("=" * 70)

        counts: Dict[str, int] = {}
        for rec in records:
            routed = route_discovered_item(rec)
            c_type = routed.classified_type
            counts[c_type] = counts.get(c_type, 0) + 1
            print(f"[{c_type.upper():14s}] -> Parser: {routed.target_parser:26s} | {rec['discovered_title'][:40]}")

        print("\n" + "=" * 70)
        print("CLASSIFICATION SUMMARY:")
        for t, cnt in sorted(counts.items()):
            print(f"  {t:15s}: {cnt}")
        print("=" * 70)
