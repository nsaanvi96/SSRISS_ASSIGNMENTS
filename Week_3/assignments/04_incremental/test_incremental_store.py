#!/usr/bin/env python3
"""test_incremental_store.py - Tests for Assignment 4: Incremental Collection and Change Detection

Run with:   python -m pytest Week_3/assignments/04_incremental/test_incremental_store.py -v
        or: python Week_3/assignments/04_incremental/test_incremental_store.py
"""

from __future__ import annotations

import os
import sys
import time

# Allow running from repo root or from inside 04_incremental/
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from incremental_store import (
    ClassifiedItem,
    IncrementalStore,
    ItemStatus,
    RunSummary,
    _make_record,
    compute_content_hash,
)

BASE_URL = "https://www.iima.ac.in/the-institute/events/"


# ===========================================================================
# 1. Content Hash Unit Tests
# ===========================================================================

class TestContentHash:
    """Verifies content hashing stability, normalization, and exclusion of volatile fields."""

    def test_hash_deterministic(self):
        h1 = compute_content_hash("https://example.com/item1", "Item Title", "2026-10-01")
        h2 = compute_content_hash("https://example.com/item1", "Item Title", "2026-10-01")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex length

    def test_hash_case_and_whitespace_normalization(self):
        h1 = compute_content_hash("https://EXAMPLE.com/Item1 ", "  Item Title ", "2026-10-01")
        h2 = compute_content_hash("https://example.com/item1", "item title", "2026-10-01")
        assert h1 == h2

    def test_hash_none_handling(self):
        h1 = compute_content_hash("https://example.com/item1", None, None)
        h2 = compute_content_hash("https://example.com/item1", "", "")
        assert h1 == h2

    def test_hash_changes_on_title(self):
        h1 = compute_content_hash("https://example.com/item1", "Old Title", "2026-10-01")
        h2 = compute_content_hash("https://example.com/item1", "New Title", "2026-10-01")
        assert h1 != h2

    def test_hash_changes_on_timestamp(self):
        h1 = compute_content_hash("https://example.com/item1", "Title", "2026-10-01")
        h2 = compute_content_hash("https://example.com/item1", "Title", "2026-10-02")
        assert h1 != h2

    def test_hash_changes_on_url(self):
        h1 = compute_content_hash("https://example.com/item1", "Title", "2026-10-01")
        h2 = compute_content_hash("https://example.com/item2", "Title", "2026-10-01")
        assert h1 != h2


# ===========================================================================
# 2. Individual Item Status Tests
# ===========================================================================

class TestItemClassification:
    """Tests classification into NEW, UNCHANGED, CHANGED, and NOT_SEEN_THIS_RUN."""

    def test_new_item(self):
        """First time a URL appears -> status NEW, row created with timestamps."""
        store = IncrementalStore(":memory:")
        rec = _make_record(BASE_URL + "event-1", title="Event 1", source_timestamp="2026-10-01")

        summary = store.process_run([rec])

        assert summary.new == 1
        assert summary.unchanged == 0
        assert summary.changed == 0
        assert summary.not_seen_this_run == 0

        item = summary.items[0]
        assert item.status == ItemStatus.NEW
        assert item.url == BASE_URL + "event-1"
        assert item.first_seen_at == item.last_seen_at
        assert item.last_seen_at == item.fetched_at

        # Verify DB row
        row = store.get_item(BASE_URL + "event-1")
        assert row is not None
        assert row["url"] == BASE_URL + "event-1"
        assert row["title"] == "Event 1"
        assert row["first_seen_at"] == item.first_seen_at

    def test_unchanged_item(self):
        """Same URL with same content -> status UNCHANGED, last_seen_at updated, first_seen_at preserved."""
        store = IncrementalStore(":memory:")
        rec1 = _make_record(BASE_URL + "event-1", title="Event 1", source_timestamp="2026-10-01")
        summary1 = store.process_run([rec1])
        first_seen_1 = summary1.items[0].first_seen_at

        # Small pause to guarantee timestamp advancement if resolution allows
        time.sleep(0.01)

        rec2 = _make_record(BASE_URL + "event-1", title="Event 1", source_timestamp="2026-10-01")
        summary2 = store.process_run([rec2])

        assert summary2.unchanged == 1
        assert summary2.new == 0
        assert summary2.changed == 0
        assert summary2.not_seen_this_run == 0

        item = summary2.items[0]
        assert item.status == ItemStatus.UNCHANGED
        assert item.first_seen_at == first_seen_1
        assert item.content_hash == summary1.items[0].content_hash

    def test_changed_item_title(self):
        """Same URL with updated title -> status CHANGED, old_hash captured."""
        store = IncrementalStore(":memory:")
        rec1 = _make_record(BASE_URL + "event-1", title="Event 1 (Draft)", source_timestamp="2026-10-01")
        summary1 = store.process_run([rec1])
        old_hash = summary1.items[0].content_hash
        first_seen_1 = summary1.items[0].first_seen_at

        rec2 = _make_record(BASE_URL + "event-1", title="Event 1 (Final)", source_timestamp="2026-10-01")
        summary2 = store.process_run([rec2])

        assert summary2.changed == 1
        assert summary2.new == 0
        assert summary2.unchanged == 0

        item = summary2.items[0]
        assert item.status == ItemStatus.CHANGED
        assert item.old_hash == old_hash
        assert item.content_hash != old_hash
        assert item.first_seen_at == first_seen_1
        assert item.title == "Event 1 (Final)"

        # Verify DB reflects updated title and new hash
        row = store.get_item(BASE_URL + "event-1")
        assert row["title"] == "Event 1 (Final)"
        assert row["content_hash"] == item.content_hash
        assert row["first_seen_at"] == first_seen_1

    def test_changed_item_timestamp(self):
        """Same URL and title with updated source_timestamp -> status CHANGED."""
        store = IncrementalStore(":memory:")
        rec1 = _make_record(BASE_URL + "event-1", title="Event 1", source_timestamp="2026-10-01")
        store.process_run([rec1])

        rec2 = _make_record(BASE_URL + "event-1", title="Event 1", source_timestamp="2026-10-05")
        summary2 = store.process_run([rec2])

        assert summary2.changed == 1
        item = summary2.items[0]
        assert item.status == ItemStatus.CHANGED

    def test_not_seen_this_run(self):
        """URL present in store but absent in current run -> NOT_SEEN_THIS_RUN."""
        store = IncrementalStore(":memory:")
        rec_a = _make_record(BASE_URL + "a", title="A")
        rec_b = _make_record(BASE_URL + "b", title="B")
        store.process_run([rec_a, rec_b])

        # Run 2 only includes 'a'
        summary2 = store.process_run([rec_a])

        assert summary2.unchanged == 1
        assert summary2.not_seen_this_run == 1
        assert summary2.new == 0
        assert summary2.changed == 0

        not_seen = summary2.by_status(ItemStatus.NOT_SEEN_THIS_RUN)
        assert len(not_seen) == 1
        assert not_seen[0].url == BASE_URL + "b"

    def test_absent_item_not_deleted(self):
        """NOT_SEEN_THIS_RUN items must NOT be deleted from the database."""
        store = IncrementalStore(":memory:")
        rec_a = _make_record(BASE_URL + "a", title="A")
        rec_b = _make_record(BASE_URL + "b", title="B")
        rec_c = _make_record(BASE_URL + "c", title="C")
        store.process_run([rec_a, rec_b, rec_c])
        assert store.count() == 3

        # Run 2 has NO items at all
        summary2 = store.process_run([])

        assert summary2.not_seen_this_run == 3
        assert summary2.new == 0
        # Rows must still exist in SQLite
        assert store.count() == 3
        assert store.get_item(BASE_URL + "a") is not None
        assert store.get_item(BASE_URL + "b") is not None
        assert store.get_item(BASE_URL + "c") is not None


# ===========================================================================
# 3. Volatility and Invariance Tests
# ===========================================================================

class TestVolatilityAndInvariance:
    """Verifies that volatile fields do not cause false change signals, and invariants hold."""

    def test_fetched_at_does_not_trigger_changed(self):
        """Running the same record with a newer discovered_at must yield UNCHANGED."""
        store = IncrementalStore(":memory:")
        rec1 = _make_record(BASE_URL + "item-1", title="Title", source_timestamp="2026-10-01")
        rec1["discovered_at"] = "2026-10-01T00:00:00Z"
        store.process_run([rec1])

        time.sleep(0.01)

        rec2 = _make_record(BASE_URL + "item-1", title="Title", source_timestamp="2026-10-01")
        rec2["discovered_at"] = "2026-10-14T23:59:59Z"
        summary2 = store.process_run([rec2])

        assert summary2.unchanged == 1
        assert summary2.changed == 0
        assert summary2.items[0].status == ItemStatus.UNCHANGED

    def test_discovery_method_change_does_not_trigger_changed(self):
        """Item discovered via rss in run 1 and html_listing in run 2 remains UNCHANGED if content is same."""
        store = IncrementalStore(":memory:")
        rec1 = _make_record(BASE_URL + "item-1", title="Title", discovery_method="rss")
        store.process_run([rec1])

        rec2 = _make_record(BASE_URL + "item-1", title="Title", discovery_method="html_listing")
        summary2 = store.process_run([rec2])

        assert summary2.unchanged == 1
        assert summary2.changed == 0

    def test_first_seen_at_never_changes(self):
        """first_seen_at remains strictly identical across NEW, UNCHANGED, and CHANGED runs."""
        store = IncrementalStore(":memory:")
        rec = _make_record(BASE_URL + "item-1", title="Initial Title", source_timestamp="2026-10-01")
        s1 = store.process_run([rec])
        initial_first_seen = s1.items[0].first_seen_at

        time.sleep(0.01)
        # Run 2: Unchanged
        s2 = store.process_run([rec])
        assert s2.items[0].first_seen_at == initial_first_seen

        time.sleep(0.01)
        # Run 3: Absent
        s3 = store.process_run([])
        assert s3.items[0].first_seen_at == initial_first_seen

        time.sleep(0.01)
        # Run 4: Changed
        rec_changed = _make_record(BASE_URL + "item-1", title="Updated Title", source_timestamp="2026-10-10")
        s4 = store.process_run([rec_changed])
        assert s4.items[0].first_seen_at == initial_first_seen

        row = store.get_item(BASE_URL + "item-1")
        assert row["first_seen_at"] == initial_first_seen

    def test_last_seen_at_preserved_when_not_seen(self):
        """When an item is NOT_SEEN_THIS_RUN, its last_seen_at remains unchanged, but fetched_at updates."""
        store = IncrementalStore(":memory:")
        rec = _make_record(BASE_URL + "item-1", title="Title")
        s1 = store.process_run([rec])
        run1_last_seen = s1.items[0].last_seen_at

        time.sleep(0.01)
        s2 = store.process_run([])  # item not in this run

        not_seen_item = s2.items[0]
        assert not_seen_item.status == ItemStatus.NOT_SEEN_THIS_RUN
        assert not_seen_item.last_seen_at == run1_last_seen
        assert not_seen_item.fetched_at > run1_last_seen


# ===========================================================================
# 4. Rediscovery and Multi-Run Lifecycle Tests
# ===========================================================================

class TestMultiRunLifecycle:
    """Tests complex lifecycles including rediscovery and multiple sequential runs."""

    def test_cross_run_scenario(self):
        """Full scenario:
        Run 1: A, B, C -> 3 NEW
        Run 2: A (same), B (changed), C (absent), D (new) -> 1 NEW, 1 CHANGED, 1 UNCHANGED, 1 NOT_SEEN
        """
        store = IncrementalStore(":memory:")

        run1 = [
            _make_record(BASE_URL + "item-a", title="Item A", source_timestamp="2026-10-01"),
            _make_record(BASE_URL + "item-b", title="Item B", source_timestamp="2026-10-02"),
            _make_record(BASE_URL + "item-c", title="Item C", source_timestamp="2026-10-03"),
        ]
        s1 = store.process_run(run1)
        assert s1.new == 3
        assert s1.unchanged == 0
        assert s1.changed == 0
        assert s1.not_seen_this_run == 0
        assert store.count() == 3

        run2 = [
            _make_record(BASE_URL + "item-a", title="Item A",         source_timestamp="2026-10-01"),
            _make_record(BASE_URL + "item-b", title="Item B Updated", source_timestamp="2026-10-10"),
            _make_record(BASE_URL + "item-d", title="Item D",         source_timestamp="2026-10-11"),
        ]
        s2 = store.process_run(run2)
        assert s2.new == 1               # D
        assert s2.changed == 1           # B
        assert s2.unchanged == 1         # A
        assert s2.not_seen_this_run == 1 # C
        assert store.count() == 4        # A, B, C, D all in store

        assert s2.by_status(ItemStatus.NEW)[0].url == BASE_URL + "item-d"
        assert s2.by_status(ItemStatus.CHANGED)[0].url == BASE_URL + "item-b"
        assert s2.by_status(ItemStatus.UNCHANGED)[0].url == BASE_URL + "item-a"
        assert s2.by_status(ItemStatus.NOT_SEEN_THIS_RUN)[0].url == BASE_URL + "item-c"

    def test_rediscovered_item_is_not_new(self):
        """Item absent in Run 2 that reappears in Run 3 must be UNCHANGED (not NEW)."""
        store = IncrementalStore(":memory:")
        rec_a = _make_record(BASE_URL + "item-a", title="Item A", source_timestamp="2026-10-01")
        s1 = store.process_run([rec_a])
        first_seen = s1.items[0].first_seen_at

        # Run 2: absent
        s2 = store.process_run([])
        assert s2.not_seen_this_run == 1

        # Run 3: reappears unchanged
        s3 = store.process_run([rec_a])
        assert s3.new == 0
        assert s3.unchanged == 1
        assert s3.items[0].status == ItemStatus.UNCHANGED
        assert s3.items[0].first_seen_at == first_seen

    def test_rediscovered_item_changed(self):
        """Item absent in Run 2 that reappears in Run 3 with modifications must be CHANGED (not NEW)."""
        store = IncrementalStore(":memory:")
        rec_a = _make_record(BASE_URL + "item-a", title="Item A", source_timestamp="2026-10-01")
        s1 = store.process_run([rec_a])
        first_seen = s1.items[0].first_seen_at

        # Run 2: absent
        store.process_run([])

        # Run 3: reappears with changed title
        rec_a_mod = _make_record(BASE_URL + "item-a", title="Item A Mod", source_timestamp="2026-10-01")
        s3 = store.process_run([rec_a_mod])
        assert s3.new == 0
        assert s3.changed == 1
        assert s3.items[0].status == ItemStatus.CHANGED
        assert s3.items[0].first_seen_at == first_seen


# ===========================================================================
# 5. Run Summary and Query Helpers Tests
# ===========================================================================

class TestRunSummaryAndHelpers:
    """Tests summary statistics, filtering, string format, and store query helpers."""

    def test_run_summary_counts_and_by_status(self):
        summary = RunSummary(
            new=2, unchanged=3, changed=1, not_seen_this_run=4,
            items=[]
        )
        assert summary.new == 2
        assert summary.unchanged == 3
        assert summary.changed == 1
        assert summary.not_seen_this_run == 4
        assert "new=2" in str(summary)
        assert "changed=1" in str(summary)
        assert "unchanged=3" in str(summary)
        assert "not_seen_this_run=4" in str(summary)

    def test_store_query_helpers(self):
        store = IncrementalStore(":memory:")
        store.process_run([
            _make_record(BASE_URL + "1", title="One"),
            _make_record(BASE_URL + "2", title="Two"),
        ])

        assert store.count() == 2
        all_rows = store.all_items()
        assert len(all_rows) == 2
        urls = [r["url"] for r in all_rows]
        assert BASE_URL + "1" in urls
        assert BASE_URL + "2" in urls

        # Non-existent item
        assert store.get_item("https://unknown.com") is None


# ===========================================================================
# Standalone runner
# ===========================================================================

if __name__ == "__main__":
    import traceback

    test_classes = [
        TestContentHash,
        TestItemClassification,
        TestVolatilityAndInvariance,
        TestMultiRunLifecycle,
        TestRunSummaryAndHelpers,
    ]

    passed = failed = 0
    print("=" * 60)
    print("Running Assignment 4 Tests: Incremental Collection & Store")
    print("=" * 60)

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

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)
