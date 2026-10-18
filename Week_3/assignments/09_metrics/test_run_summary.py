#!/usr/bin/env python3
"""test_run_summary.py - Tests for Assignment 9: Source Health and Coverage Metrics

Run with:   python -m pytest Week_3/assignments/09_metrics/test_run_summary.py -v
        or: python Week_3/assignments/09_metrics/test_run_summary.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile

# Allow running from repo root or from inside 09_metrics/
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from run_summary import (
    RunHealthStatus,
    RunMetrics,
    diagnose_health,
    persist_metrics_to_db,
    persist_metrics_to_log,
    run_monitored_pipeline,
)

_VALID_FIXTURE = os.path.join(_HERE, "fixtures", "valid_events.html")
_BROKEN_FIXTURE = os.path.join(_HERE, "fixtures", "broken_events.html")


# ===========================================================================
# 1. Summary Format and Diagnostics Unit Tests
# ===========================================================================

class TestRunSummaryFormatting:
    """Verifies that the summary output strictly adheres to the requested format."""

    def test_summary_text_keys(self):
        m = RunMetrics(
            source="example_events",
            started_at="2026-10-18T10:00:00Z",
            finished_at="2026-10-18T10:00:05Z",
            pages_fetched=3,
            items_discovered=26,
            items_parsed=25,
            new=4,
            changed=2,
            unchanged=19,
            failed=1,
            people_extracted=13,
            organizations_extracted=8,
            pct_with_date=96.0,
            pct_with_speaker=84.0,
            pct_with_organization=72.0,
        )
        text = m.to_summary_text()

        # Required prompt keys
        assert "SOURCE: example_events" in text
        assert "PAGES_FETCHED: 3" in text
        assert "ITEMS_DISCOVERED: 26" in text
        assert "ITEMS_PARSED: 25" in text
        assert "NEW: 4" in text
        assert "CHANGED: 2" in text
        assert "UNCHANGED: 19" in text
        assert "FAILED: 1" in text
        assert "PEOPLE_EXTRACTED: 13" in text
        assert "ORGANIZATIONS_EXTRACTED: 8" in text
        assert "PCT_WITH_DATE: 96.0%" in text


# ===========================================================================
# 2. Checkpoint Verification: No New Content vs. Parser Breakage
# ===========================================================================

class TestCheckpointDistinction:
    """Verifies checkpoint: A reviewer should be able to distinguish
    'source had no new content' from 'parser broke and returned zero content'."""

    def test_distinguish_no_new_content_from_parser_broke(self):
        # Scenario A: Source had no new content (Healthy)
        m_no_new = RunMetrics(
            source="iima_events",
            started_at="2026-10-18T10:00:00Z",
            finished_at="2026-10-18T10:00:02Z",
            pages_fetched=1,
            items_discovered=20,
            items_parsed=20,
            new=0,
            changed=0,
            unchanged=20,
            failed=0,
        )
        status_a, msg_a = diagnose_health(m_no_new)
        assert status_a == RunHealthStatus.HEALTHY_NO_NEW_CONTENT
        assert "no new or updated items" in msg_a

        # Scenario B: Parser broke and returned zero content (Failure)
        m_broken = RunMetrics(
            source="iima_events",
            started_at="2026-10-18T10:00:00Z",
            finished_at="2026-10-18T10:00:02Z",
            pages_fetched=1,
            items_discovered=0,
            items_parsed=0,
            new=0,
            changed=0,
            unchanged=0,
            failed=1,
        )
        status_b, msg_b = diagnose_health(m_broken)
        assert status_b == RunHealthStatus.PARSER_FAILURE
        assert "parser returned 0 items" in msg_b

        # Must be completely distinct diagnoses
        assert status_a != status_b


# ===========================================================================
# 3. Deliberately Broken Fixture Test
# ===========================================================================

class TestBrokenFixtureVisibility:
    """Verifies: Deliberately break one fixture and confirm that the metrics
    make the failure visible."""

    def test_broken_fixture_produces_visible_failure_metric(self):
        with open(_BROKEN_FIXTURE, "r", encoding="utf-8") as f:
            broken_html = f.read()

        metrics = run_monitored_pipeline("iima_events", broken_html)

        # Failure must be explicitly visible in the metrics
        assert metrics.pages_fetched == 1
        assert metrics.items_discovered == 0
        assert metrics.items_parsed == 0
        assert metrics.failed >= 1
        assert metrics.health_status == RunHealthStatus.PARSER_FAILURE.value
        assert "CRITICAL: Page fetched successfully, but parser returned 0 items" in metrics.diagnostic_message


# ===========================================================================
# 4. Valid Fixture Pipeline & Coverage Tests
# ===========================================================================

class TestValidPipelineAndCoverage:
    """Verifies that a healthy run captures all items, extraction counts, and coverage."""

    def test_valid_fixture_run(self):
        with open(_VALID_FIXTURE, "r", encoding="utf-8") as f:
            valid_html = f.read()

        metrics = run_monitored_pipeline("iima_events", valid_html)

        assert metrics.pages_fetched == 1
        assert metrics.items_discovered == 4
        assert metrics.items_parsed == 4
        assert metrics.new == 4
        assert metrics.failed == 0
        assert metrics.people_extracted == 4
        assert metrics.organizations_extracted == 4
        assert metrics.pct_with_date == 100.0
        assert metrics.pct_with_speaker == 100.0
        assert metrics.pct_with_organization == 100.0
        assert metrics.health_status == RunHealthStatus.HEALTHY_NEW_CONTENT.value

    def test_steady_state_run_marks_unchanged(self):
        with open(_VALID_FIXTURE, "r", encoding="utf-8") as f:
            valid_html = f.read()

        # Run 1: Ingest into known set
        known: set[str] = set()
        run_monitored_pipeline("iima_events", valid_html, known_urls=known)

        # Run 2: Same content
        m2 = run_monitored_pipeline("iima_events", valid_html, known_urls=known)

        assert m2.new == 0
        assert m2.unchanged == 4
        assert m2.failed == 0
        assert m2.health_status == RunHealthStatus.HEALTHY_NO_NEW_CONTENT.value


# ===========================================================================
# 5. Persistence Tests (SQLite & Log File)
# ===========================================================================

class TestPersistence:
    """Verifies writing metrics to SQLite and text logs."""

    def test_sqlite_persistence(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            m = RunMetrics(
                source="test_source",
                started_at="2026-10-18T10:00:00Z",
                finished_at="2026-10-18T10:00:02Z",
                pages_fetched=1,
                items_discovered=5,
                items_parsed=5,
                new=5,
                changed=0,
                unchanged=0,
                failed=0,
            )
            row_id = persist_metrics_to_db(m, db_path)
            assert row_id == 1

            conn = sqlite3.connect(db_path)
            row = conn.execute("SELECT source, items_parsed, health_status FROM run_metrics WHERE id = ?", (1,)).fetchone()
            assert row[0] == "test_source"
            assert row[1] == 5
            conn.close()
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_log_file_persistence(self):
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False, mode="w+") as tf:
            log_path = tf.name

        try:
            m = RunMetrics(
                source="log_source",
                started_at="2026-10-18T10:00:00Z",
                finished_at="2026-10-18T10:00:02Z",
                pages_fetched=2,
                items_discovered=10,
                items_parsed=10,
                new=10,
            )
            persist_metrics_to_log(m, log_path)

            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()

            assert "RUN SUMMARY:" in content
            assert "SOURCE: log_source" in content
            assert "PAGES_FETCHED: 2" in content
        finally:
            if os.path.exists(log_path):
                os.remove(log_path)


# ===========================================================================
# Standalone Runner
# ===========================================================================

if __name__ == "__main__":
    import traceback

    test_classes = [
        TestRunSummaryFormatting,
        TestCheckpointDistinction,
        TestBrokenFixtureVisibility,
        TestValidPipelineAndCoverage,
        TestPersistence,
    ]

    passed = failed = 0
    print("=" * 65)
    print("Running Assignment 9 Tests: Source Health and Coverage Metrics")
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
