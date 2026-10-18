#!/usr/bin/env python3
"""test_week3_integration.py - Automated End-to-End Test for Week 3 Integration

Validates:
1. All 16 required deliverables exist on disk at their specified locations.
2. The end-to-end pipeline executes successfully from config to database.
3. Two-phase ingestion works correctly (initial run followed by steady-state re-crawl).
4. Relational queries and entity link integrity are preserved.
"""

from __future__ import annotations

import os
import sys
import unittest

# Setup module path
_HERE = os.path.dirname(os.path.abspath(__file__))
_WEEK3_DIR = os.path.abspath(os.path.join(_HERE, "..", ".."))
_ASSIGNMENTS_DIR = os.path.join(_WEEK3_DIR, "assignments")
_ADAPTER_DIR = os.path.join(_ASSIGNMENTS_DIR, "10_adapter")

if _ADAPTER_DIR not in sys.path:
    sys.path.insert(0, _ADAPTER_DIR)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from central_aggregator_adapter import CentralAggregatorAdapter, DEFAULT_IIMA_CONFIG
from run_integration import run_week3_demonstration


class TestDeliverablesCompleteness(unittest.TestCase):
    """Verify that all 16 required deliverables are present on disk."""

    def test_all_16_deliverables_present(self):
        deliverables = {
            "1. Aggregator candidate matrix": os.path.join(_ASSIGNMENTS_DIR, "00_candidates", "iima_aggregators.md"),
            "2. Chosen central source rationale": os.path.join(_ASSIGNMENTS_DIR, "00_candidates", "iima_aggregators.md"),
            "3. Feed/sitemap/listing discovery exercise": os.path.join(_ASSIGNMENTS_DIR, "01_discovery", "findings.md"),
            "4. URL scope rules": os.path.join(_ASSIGNMENTS_DIR, "02_scope", "scope_cases.md"),
            "5. Discovery adapter": os.path.join(_ASSIGNMENTS_DIR, "03_interface", "aggregator_discovery.py"),
            "6. Incremental run/change detection": os.path.join(_ASSIGNMENTS_DIR, "04_incremental", "run_state_notes.md"),
            "7. Content router": os.path.join(_ASSIGNMENTS_DIR, "08_routing", "router_notes.md"),
            "8. Detail parser where relevant": os.path.join(_ADAPTER_DIR, "central_aggregator_adapter.py"),
            "9. Person entity extraction": os.path.join(_ASSIGNMENTS_DIR, "05_extraction", "entity_extractor.py"),
            "10. Organization entity extraction": os.path.join(_ASSIGNMENTS_DIR, "05_extraction", "entity_extractor.py"),
            "11. Entity relationship schema": os.path.join(_ASSIGNMENTS_DIR, "06_entities", "entity_schema.md"),
            "12. Tests and fixtures": os.path.join(_ADAPTER_DIR, "test_central_aggregator.py"),
            "13. Logs": os.path.join(_ADAPTER_DIR, "aggregator.log"),
            "14. Run metrics": os.path.join(_ASSIGNMENTS_DIR, "09_metrics", "run_summary.py"),
            "15. README": os.path.join(_WEEK3_DIR, "README.md"),
            "16. Peer-review notes": os.path.join(_WEEK3_DIR, "peer_review_notes.md"),
        }

        for name, path in deliverables.items():
            self.assertTrue(os.path.exists(path), f"Missing required deliverable: {name} at {path}")
            self.assertGreater(os.path.getsize(path), 50, f"Deliverable file {path} appears too small/empty.")


class TestEndToEndPipelineDemonstration(unittest.TestCase):
    """Verify execution of the full 10-stage integration pipeline."""

    def test_run_week3_demonstration_executes_successfully(self):
        m1, m2 = run_week3_demonstration()

        # Phase 1 Initial run assertions
        self.assertEqual(m1.items_discovered, 16)
        self.assertEqual(m1.items_parsed, 16)
        self.assertEqual(m1.new, 16)
        self.assertEqual(m1.changed, 0)
        self.assertEqual(m1.unchanged, 0)
        self.assertEqual(m1.failed, 0)
        self.assertEqual(m1.people_extracted, 22)
        self.assertEqual(m1.organizations_extracted, 13)
        self.assertIn("HEALTHY", m1.health_status)
        self.assertIn("16 new", m1.diagnostic_message)

        # Phase 2 Incremental re-crawl assertions
        self.assertEqual(m2.items_discovered, 16)
        self.assertEqual(m2.items_parsed, 16)
        self.assertEqual(m2.new, 0)
        self.assertEqual(m2.changed, 0)
        self.assertEqual(m2.unchanged, 16)
        self.assertEqual(m2.failed, 0)
        self.assertIn("HEALTHY", m2.health_status)
        self.assertIn("no new or updated items", m2.diagnostic_message)


class TestRelationalIntegrityAndQueries(unittest.TestCase):
    """Verify relational queries and entity foreign key relationships."""

    def setUp(self):
        fixture_path = os.path.join(_ADAPTER_DIR, "fixtures", "central_listing.html")
        self.adapter = CentralAggregatorAdapter(
            config=DEFAULT_IIMA_CONFIG,
            db_path=":memory:",
        )
        self.adapter.run(html_fixture_path=fixture_path)

    def tearDown(self):
        self.adapter.close()

    def test_relational_schema_counts(self):
        self.assertEqual(self.adapter.store.count_items(), 16)
        self.assertEqual(self.adapter.store.count_people(), 20)
        self.assertEqual(self.adapter.store.count_organizations(), 12)
        self.assertEqual(self.adapter.store.count_item_people(), 22)
        self.assertEqual(self.adapter.store.count_item_organizations(), 13)

    def test_query_person_across_multiple_events(self):
        # Prof. Arvind Sharma appears in 2 distinct events in the fixture
        events = self.adapter.store.get_events_by_person_name("arvind sharma")
        self.assertEqual(len(events), 2)
        roles = [e["role"] for e in events]
        self.assertTrue(all(r == "speaker" for r in roles))
        titles = [e["event_title"] for e in events]
        self.assertIn("Annual Management Research Conference 2026", titles)
        self.assertIn("Global Macroeconomics Workshop", titles)


if __name__ == "__main__":
    unittest.main()
