#!/usr/bin/env python3
"""test_content_router.py - Tests for Assignment 8: Multi-Content Central Router

Run with:   python -m pytest Week_3/assignments/08_routing/test_content_router.py -v
        or: python Week_3/assignments/08_routing/test_content_router.py
"""

from __future__ import annotations

import json
import os
import sys

# Allow running from repo root or from inside 08_routing/
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from content_router import (
    ItemType,
    RoutedItem,
    classify_discovered_item,
    route_discovered_item,
)

_FIXTURE_PATH = os.path.join(_HERE, "fixtures", "mixed_listing_sample.json")


# ===========================================================================
# 1. Structural Type Classification Tests
# ===========================================================================

class TestStructuralClassification:
    """Verifies that items are classified based on structural signals."""

    def test_classify_event_via_path(self):
        rec = {
            "discovered_url": "https://www.iima.ac.in/the-institute/events/annual-retreat",
            "discovered_title": "Annual Retreat 2026",
        }
        assert classify_discovered_item(rec) == ItemType.EVENT.value

    def test_classify_event_via_category(self):
        rec = {
            "discovered_url": "https://www.iima.ac.in/seminar/monetary-policy",
            "category": "Seminar",
        }
        assert classify_discovered_item(rec) == ItemType.EVENT.value

    def test_classify_announcement_via_path_and_section(self):
        rec = {
            "discovered_url": "https://www.iima.ac.in/news/new-dean-appointment",
            "category": "News",
            "section": "press_room",
        }
        assert classify_discovered_item(rec) == ItemType.ANNOUNCEMENT.value

    def test_classify_faculty_profile(self):
        rec = {
            "discovered_url": "https://www.iima.ac.in/faculty-research/faculty/arvind-sharma",
            "category": "Faculty Directory",
        }
        assert classify_discovered_item(rec) == ItemType.FACULTY.value

    def test_classify_pdf_via_extension(self):
        rec = {
            "discovered_url": "https://www.iima.ac.in/documents/annual-report.pdf",
        }
        assert classify_discovered_item(rec) == ItemType.PDF_DOCUMENT.value

    def test_classify_pdf_via_mime_type(self):
        rec = {
            "discovered_url": "https://www.iima.ac.in/download-paper?id=99",
            "mime_type": "application/pdf",
        }
        assert classify_discovered_item(rec) == ItemType.PDF_DOCUMENT.value

    def test_classify_external_link_via_host(self):
        rec = {
            "discovered_url": "https://forms.gle/xK9z8Q2nB1yPq5",
            "discovered_title": "Register on Google Forms",
        }
        assert classify_discovered_item(rec) == ItemType.EXTERNAL_LINK.value

    def test_classify_external_registration_platform(self):
        rec = {
            "discovered_url": "https://www.eventbrite.com/e/tickets-12345",
        }
        assert classify_discovered_item(rec) == ItemType.EXTERNAL_LINK.value


# ===========================================================================
# 2. Rule & Checkpoint Verification: No Narrative Forcing & Preservation
# ===========================================================================

class TestPolicyAndCheckpoint:
    """Verifies that political/topic text is ignored and unknowns are preserved."""

    def test_do_not_classify_based_on_topic_or_politics(self):
        """A news article discussing political debate must NOT be coerced into 'event'."""
        rec = {
            "discovered_url": "https://www.iima.ac.in/news/electoral-reform-analysis",
            "discovered_title": "Expert Commentary on Parliamentary Elections & Policy Debates",
            "category": "News",
        }
        # Path and category say news/announcement, despite 'Policy Debates' in title
        assert classify_discovered_item(rec) == ItemType.ANNOUNCEMENT.value

    def test_checkpoint_unsupported_not_forced_into_event(self):
        """Unsupported content types (e.g. photo galleries, working papers) must
        classify as UNKNOWN rather than being forced into 'event'."""
        gallery_rec = {
            "discovered_url": "https://www.iima.ac.in/campus-life/photo-gallery-autumn",
            "category": "Gallery",
            "discovered_title": "Campus Life Photo Gallery",
        }
        wp_rec = {
            "discovered_url": "https://www.iima.ac.in/research/working-papers/wp-2026-08",
            "category": "Working Paper",
            "discovered_title": "Working Paper on Econometrics",
        }

        assert classify_discovered_item(gallery_rec) == ItemType.UNKNOWN.value
        assert classify_discovered_item(wp_rec) == ItemType.UNKNOWN.value

    def test_checkpoint_unsupported_record_is_preserved_in_routing(self):
        """Routing an unknown item marks it as unsupported but preserves the raw record."""
        rec = {
            "discovered_url": "https://www.iima.ac.in/about/virtual-campus-tour",
            "discovered_title": "Virtual Campus 360 Tour",
            "category": None,
        }
        routed = route_discovered_item(rec)

        assert routed.classified_type == ItemType.UNKNOWN.value
        assert routed.is_supported is False
        assert routed.target_parser == "unsupported_item_handler"
        # The record was NOT silently dropped
        assert routed.raw_record == rec


# ===========================================================================
# 3. Fixture Batch Verification
# ===========================================================================

class TestFixtureBatch:
    """Verifies all 18 items in the mixed listing fixture match their expected type."""

    def test_all_18_fixture_items_classified_correctly(self):
        with open(_FIXTURE_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)

        assert len(records) == 18, "Expected 18 fixture records"

        for rec in records:
            classified = classify_discovered_item(rec)
            expected = rec["expected_type"]
            assert classified == expected, (
                f"Mismatch for item {rec['id']} ('{rec['discovered_title']}'):\n"
                f"  Got:      {classified}\n"
                f"  Expected: {expected}\n"
                f"  URL:      {rec['discovered_url']}"
            )


# ===========================================================================
# Standalone Runner
# ===========================================================================

if __name__ == "__main__":
    import traceback

    test_classes = [
        TestStructuralClassification,
        TestPolicyAndCheckpoint,
        TestFixtureBatch,
    ]

    passed = failed = 0
    print("=" * 65)
    print("Running Assignment 8 Tests: Multi-Content Central Router")
    print("=" * 65)

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

    print("\n" + "=" * 65)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 65)
    sys.exit(0 if failed == 0 else 1)
