#!/usr/bin/env python3
"""run_integration.py - Week 3 Final Integration Runner (Assignment 12)

Demonstrates the final Week 3 end-to-end architecture:
SOURCE CONFIG
     ↓
SCHEDULED RUN
     ↓
DISCOVERY ADAPTER
     ↓
SCOPE CONTROL
     ↓
NEW / CHANGED ITEM CANDIDATES
     ↓
FETCH + PARSE
     ↓
NORMALIZE
     ↓
EXPLICIT ENTITY EXTRACTION
     ↓
ITEM + ENTITY RELATIONSHIPS
     ↓
DATABASE
     ↓
HEALTH / COVERAGE SUMMARY
"""

from __future__ import annotations

import os
import sys

# Setup imports across Week 3 modules
_HERE = os.path.dirname(os.path.abspath(__file__))
_ASSIGNMENTS_DIR = os.path.abspath(os.path.join(_HERE, ".."))
_ADAPTER_DIR = os.path.join(_ASSIGNMENTS_DIR, "10_adapter")
if _ADAPTER_DIR not in sys.path:
    sys.path.insert(0, _ADAPTER_DIR)

from central_aggregator_adapter import CentralAggregatorAdapter, DEFAULT_IIMA_CONFIG


def run_week3_demonstration():
    fixture_path = os.path.join(_ADAPTER_DIR, "fixtures", "central_listing.html")
    log_path = os.path.join(_HERE, "integration_run.log")

    print("=" * 72)
    print("WEEK 3 FINAL INTEGRATION: HIGH-YIELD CENTRAL AGGREGATOR")
    print("Institution: Indian Institute of Management Ahmedabad (www.iima.ac.in)")
    print("=" * 72)

    adapter = CentralAggregatorAdapter(
        config=DEFAULT_IIMA_CONFIG,
        db_path=":memory:",
        log_path=log_path,
    )

    print("\n[PHASE 1] Initial Ingestion Run (Simulating First Scheduled Cycle)...")
    m1 = adapter.run(html_fixture_path=fixture_path)
    print(m1.to_summary_text())

    print("\n" + "-" * 72)
    print("[PHASE 2] Incremental Re-crawl Run (Simulating Second Scheduled Cycle)...")
    m2 = adapter.run(html_fixture_path=fixture_path)
    print(m2.to_summary_text())

    print("\n" + "-" * 72)
    print("[PHASE 3] Database Relational Entity Verification:")
    print(f"  Total Stored Event Items:        {adapter.store.count_items()}")
    print(f"  Total Unique People Profiles:    {adapter.store.count_people()}")
    print(f"  Total Unique Organizations:      {adapter.store.count_organizations()}")
    print(f"  Many-to-Many Event-People Links: {adapter.store.count_item_people()}")
    print(f"  Many-to-Many Event-Org Links:    {adapter.store.count_item_organizations()}")

    print("\n" + "-" * 72)
    print("[PHASE 4] Relational Query Capability:")
    print("  Query: Which events mention 'arvind sharma'?")
    events = adapter.store.get_events_by_person_name("arvind sharma")
    for ev in events:
        print(f"  - [{ev['role']}] {ev['event_title']}")
        print(f"    Source text: '{ev['source_text']}'")

    print("\n" + "=" * 72)
    print("INTEGRATION DEMONSTRATION COMPLETE: ALL SYSTEMS HEALTHY")
    print("=" * 72)

    adapter.close()
    return m1, m2


if __name__ == "__main__":
    run_week3_demonstration()
