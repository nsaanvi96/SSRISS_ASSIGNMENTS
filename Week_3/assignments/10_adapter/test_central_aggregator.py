#!/usr/bin/env python3
"""test_central_aggregator.py - Tests for Assignment 10: Central Aggregator Adapter

Run with:   python -m pytest Week_3/assignments/10_adapter/test_central_aggregator.py -v
        or: python Week_3/assignments/10_adapter/test_central_aggregator.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile

# Allow running from repo root or from inside 10_adapter/
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from central_aggregator_adapter import (
    CentralAggregatorAdapter,
    DEFAULT_IIMA_CONFIG,
)
from run_summary import RunHealthStatus

_FIXTURE_PATH = os.path.join(_HERE, "fixtures", "central_listing.html")


# ===========================================================================
# 1. Bounded Scope & Deduplication Tests
# ===========================================================================

class TestScopeBoundingAndDeduplication:
    """Verifies that the central aggregator enforces scope bounding,
    rejects out-of-scope assets, and deduplicates tracking variants."""

    def test_scope_filters_out_login_pdf_and_external(self):
        adapter = CentralAggregatorAdapter(db_path=":memory:")
        metrics = adapter.run(html_fixture_path=_FIXTURE_PATH)

        # Raw fixture has 20 items:
        # - 16 valid event items
        # - 1 binary PDF (/the-institute/events/conference-brochure.pdf)
        # - 1 login page (/login?destination=/events)
        # - 1 external Google Form (https://forms.gle/...)
        # - 1 duplicate with utm query parameters
        # Scope filter must admit exactly 16 items
        assert metrics.items_discovered == 16
        assert metrics.items_parsed == 16
        assert adapter.store.count_items() == 16

    def test_ceiling_enforcement(self):
        """Ceiling control: Restricting max_items stops collection at the ceiling."""
        custom_cfg = dict(DEFAULT_IIMA_CONFIG)
        custom_cfg["max_items"] = 5

        adapter = CentralAggregatorAdapter(config=custom_cfg, db_path=":memory:")
        metrics = adapter.run(html_fixture_path=_FIXTURE_PATH)

        assert metrics.items_parsed == 5
        assert adapter.store.count_items() == 5


# ===========================================================================
# 2. Entity Extraction & Relational Storage Tests
# ===========================================================================

class TestRelationalStorageAndEntities:
    """Verifies explicit entity extraction and relational many-to-many linking."""

    def test_people_and_org_extraction_counts(self):
        adapter = CentralAggregatorAdapter(db_path=":memory:")
        metrics = adapter.run(html_fixture_path=_FIXTURE_PATH)

        assert metrics.people_extracted >= 20
        assert metrics.organizations_extracted >= 10
        assert metrics.pct_with_date == 100.0
        assert metrics.pct_with_speaker == 100.0
        assert metrics.pct_with_organization > 75.0

    def test_relational_entity_deduplication(self):
        """Verifies checkpoint: Unique people < item_people links (entities are shared, not duplicated)."""
        adapter = CentralAggregatorAdapter(db_path=":memory:")
        adapter.run(html_fixture_path=_FIXTURE_PATH)

        people_count = adapter.store.count_people()
        item_people_count = adapter.store.count_item_people()
        assert people_count < item_people_count, (
            f"Expected many-to-many sharing: people={people_count}, links={item_people_count}"
        )

        org_count = adapter.store.count_organizations()
        item_org_count = adapter.store.count_item_organizations()
        assert org_count < item_org_count, (
            f"Expected many-to-many sharing: orgs={org_count}, links={item_org_count}"
        )

    def test_provenance_stored_on_all_links(self):
        adapter = CentralAggregatorAdapter(db_path=":memory:")
        adapter.run(html_fixture_path=_FIXTURE_PATH)

        cur = adapter.store._conn.execute(
            "SELECT source_text FROM item_people WHERE source_text IS NULL OR source_text = ''"
        )
        assert len(cur.fetchall()) == 0


# ===========================================================================
# 3. Incremental Change Detection & Run Health Tests
# ===========================================================================

class TestIncrementalRunsAndHealth:
    """Verifies incremental execution, change detection, and health diagnosis."""

    def test_two_consecutive_runs_steady_state(self):
        adapter = CentralAggregatorAdapter(db_path=":memory:")

        # Run 1: Initial Ingestion
        m1 = adapter.run(html_fixture_path=_FIXTURE_PATH)
        assert m1.new == 16
        assert m1.unchanged == 0
        assert m1.failed == 0
        assert m1.health_status == RunHealthStatus.HEALTHY_NEW_CONTENT.value

        # Run 2: Re-crawl of unchanged fixture
        m2 = adapter.run(html_fixture_path=_FIXTURE_PATH)
        assert m2.new == 0
        assert m2.unchanged == 16
        assert m2.failed == 0
        assert m2.health_status == RunHealthStatus.HEALTHY_NO_NEW_CONTENT.value
        assert "no new or updated items" in m2.diagnostic_message

    def test_http_failure_surfacing(self):
        adapter = CentralAggregatorAdapter(db_path=":memory:")
        m = adapter.run(raw_html="", http_status=503)

        assert m.http_status == 503
        assert m.pages_fetched == 0
        assert m.failed == 1
        assert m.health_status == RunHealthStatus.HTTP_FAILURE.value


# ===========================================================================
# 4. Persistence & Log Verification
# ===========================================================================

class TestPersistenceAndLogs:
    """Verifies SQLite and text log persistence."""

    def test_persistence_to_sqlite_and_log(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf_db:
            db_path = tf_db.name
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False, mode="w+") as tf_log:
            log_path = tf_log.name

        adapter = None
        try:
            adapter = CentralAggregatorAdapter(db_path=db_path, log_path=log_path)
            metrics = adapter.run(html_fixture_path=_FIXTURE_PATH)

            # 1. SQLite verification
            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT source, items_parsed, health_status FROM run_metrics WHERE id = 1").fetchone()
            assert row[0] == "iima_events"
            assert row[1] == 16
            conn.close()

            # 2. Log verification
            with open(log_path, "r", encoding="utf-8") as f:
                log_content = f.read()

            assert "RUN SUMMARY:" in log_content
            assert "SOURCE: iima_events" in log_content
            assert "ITEMS_PARSED: 16" in log_content
        finally:
            if adapter:
                adapter.close()
            if os.path.exists(db_path):
                try:
                    os.remove(db_path)
                except Exception:
                    pass
            if os.path.exists(log_path):
                try:
                    os.remove(log_path)
                except Exception:
                    pass


# ===========================================================================
# Standalone Runner
# ===========================================================================

if __name__ == "__main__":
    import traceback

    test_classes = [
        TestScopeBoundingAndDeduplication,
        TestRelationalStorageAndEntities,
        TestIncrementalRunsAndHealth,
        TestPersistenceAndLogs,
    ]

    passed = failed = 0
    print("=" * 65)
    print("Running Assignment 10 Tests: Central Aggregator Adapter")
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
