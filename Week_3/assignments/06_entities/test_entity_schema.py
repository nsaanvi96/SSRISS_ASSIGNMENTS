#!/usr/bin/env python3
"""test_entity_schema.py - Tests for Assignment 6: Entity Storage and Relationships

Run with:   python -m pytest Week_3/assignments/06_entities/test_entity_schema.py -v
        or: python Week_3/assignments/06_entities/test_entity_schema.py
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys

# Allow running from repo root or from inside 06_entities/
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from entity_relational_store import (
    EntityRelationalStore,
    normalize_name,
    normalize_org_name,
)

_FIXTURE_PATH = os.path.abspath(
    os.path.join(_HERE, "..", "05_extraction", "fixtures", "events_sample.json")
)


# ===========================================================================
# 1. Schema & Normalization Unit Tests
# ===========================================================================

class TestSchemaAndNormalization:
    """Tests DDL creation, tables, indexes, and conservative name normalization."""

    def test_tables_created(self):
        store = EntityRelationalStore(":memory:")
        cur = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {r[0] for r in cur.fetchall()}
        expected = {"items", "people", "organizations", "item_people", "item_organizations"}
        assert expected.issubset(tables)

    def test_name_normalization_strips_honorifics_conservatively(self):
        assert normalize_name("Prof. Arvind Sharma") == "arvind sharma"
        assert normalize_name("Dr. Arvind Sharma") == "arvind sharma"
        assert normalize_name("Arvind Sharma") == "arvind sharma"
        assert normalize_name("  Smt. Nirmala Sitharaman ") == "nirmala sitharaman"
        assert normalize_name("Justice (Retd.) S. Muralidhar") == "(retd.) s. muralidhar"

    def test_similar_names_not_merged_by_normalization(self):
        """Rule: Do not merge two people solely because their names look similar."""
        k1 = normalize_name("Dr. Rajesh Kumar")
        k2 = normalize_name("Prof. R. Kumar")
        assert k1 != k2
        assert k1 == "rajesh kumar"
        assert k2 == "r. kumar"

    def test_org_normalization(self):
        assert normalize_org_name(" Centre for ESG Research  ") == "centre for esg research"


# ===========================================================================
# 2. Relational Linking & Many-to-Many Relationships
# ===========================================================================

class TestRelationalLinking:
    """Verifies that events connect to multiple people and organizations,
    and entities link across multiple events without row duplication."""

    def test_one_event_to_multiple_entities(self):
        store = EntityRelationalStore(":memory:")
        event = {
            "source_url": "https://www.iima.ac.in/events/test-1",
            "title": "Decarbonization Pathways",
            "raw_text": "Speaker: Dr. Example, Centre for Example Studies\nOrganized by: Department of Example\nChair: Prof. Sample",
        }
        item_id = store.store_event_record(event)

        entities = store.get_event_entities(item_id)
        assert len(entities["people"]) == 2
        assert len(entities["organizations"]) == 1

        roles = {p["role"] for p in entities["people"]}
        assert roles == {"speaker", "chair"}

        org_roles = {o["role"] for o in entities["organizations"]}
        assert org_roles == {"organizer"}

    def test_same_person_in_multiple_events(self):
        """A person appearing in 2 different events must have ONLY ONE row in `people`."""
        store = EntityRelationalStore(":memory:")
        ev1 = {
            "source_url": "https://www.iima.ac.in/events/ev1",
            "title": "Conference 1",
            "raw_text": "Keynote Speaker: Prof. Arvind Sharma, IIM Ahmedabad",
        }
        ev2 = {
            "source_url": "https://www.iima.ac.in/events/ev2",
            "title": "Conference 2",
            "raw_text": "Speaker: Prof. Arvind Sharma, IIM Ahmedabad",
        }
        id1 = store.store_event_record(ev1)
        id2 = store.store_event_record(ev2)

        # Unique person in database must be exactly 1
        assert store.count_people() == 1
        assert store.count_item_people() == 2

        # Both events must reference the same person_id
        cur = store._conn.execute("SELECT person_id FROM item_people WHERE item_id = ?", (id1,))
        p1 = cur.fetchone()[0]
        cur = store._conn.execute("SELECT person_id FROM item_people WHERE item_id = ?", (id2,))
        p2 = cur.fetchone()[0]
        assert p1 == p2

    def test_same_organization_in_multiple_events(self):
        """An organization appearing in multiple events must have ONLY ONE row in `organizations`."""
        store = EntityRelationalStore(":memory:")
        ev1 = {
            "source_url": "https://www.iima.ac.in/events/ev1",
            "title": "Event 1",
            "raw_text": "Organized by: Centre for Management in Agriculture",
        }
        ev2 = {
            "source_url": "https://www.iima.ac.in/events/ev2",
            "title": "Event 2",
            "raw_text": "Co-organized by: Centre for Management in Agriculture",
        }
        store.store_event_record(ev1)
        store.store_event_record(ev2)

        assert store.count_organizations() == 1
        assert store.count_item_organizations() == 2


# ===========================================================================
# 3. Required Query Tests
# ===========================================================================

class TestRequiredQueries:
    """Tests the two queries explicitly requested in Assignment 6."""

    def test_query_events_by_exact_normalized_person_name(self):
        """Query 1: Which events in my local database mention this exact normalized person name?"""
        store = EntityRelationalStore(":memory:")
        with open(_FIXTURE_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)

        for rec in records:
            store.store_event_record(rec)

        results = store.get_events_by_person_name("arvind sharma")
        assert len(results) == 2, f"Expected 2 events for Arvind Sharma, got {len(results)}"

        titles = [r["event_title"] for r in results]
        assert "Annual Management Research Conference 2026" in titles
        assert "Global Macroeconomics Workshop" in titles

        # Verify provenance is preserved in query output
        for r in results:
            assert "source_text" in r
            assert len(r["source_text"]) > 0

    def test_query_organizations_by_role(self):
        """Query 2: Which organizations have appeared as organizers in my collected sample?"""
        store = EntityRelationalStore(":memory:")
        with open(_FIXTURE_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)

        for rec in records:
            store.store_event_record(rec)

        results = store.get_organizations_by_role("organizer")
        assert len(results) >= 8, f"Expected multiple organizers, got {len(results)}"

        org_names = [r["display_name"] for r in results]
        assert "Centre for Management in Agriculture" in org_names
        assert "CIIE.CO" in org_names
        assert "Research and Publications Office" in org_names
        assert "School of Public Policy and Governance" in org_names


# ===========================================================================
# 4. Checkpoint & Integrity Tests
# ===========================================================================

class TestCheckpointAndIntegrity:
    """Verifies checkpoint: No full person record duplicated in every event row."""

    def test_checkpoint_no_duplicate_person_rows(self):
        store = EntityRelationalStore(":memory:")
        with open(_FIXTURE_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)

        for rec in records:
            store.store_event_record(rec)

        total_people = store.count_people()
        total_links = store.count_item_people()

        # Because people like Arvind Sharma, Rajesh Kumar, etc. appear in multiple links,
        # unique people count must be strictly less than total event links!
        assert total_people < total_links, (
            f"Expected deduplication across join table: people={total_people}, links={total_links}"
        )

    def test_provenance_always_present_in_join_tables(self):
        store = EntityRelationalStore(":memory:")
        with open(_FIXTURE_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)

        for rec in records:
            store.store_event_record(rec)

        cur = store._conn.execute("SELECT source_text FROM item_people WHERE source_text IS NULL OR source_text = ''")
        assert len(cur.fetchall()) == 0

        cur = store._conn.execute("SELECT source_text FROM item_organizations WHERE source_text IS NULL OR source_text = ''")
        assert len(cur.fetchall()) == 0

    def test_cascade_delete_integrity(self):
        """Deleting an item deletes join rows without deleting the person."""
        store = EntityRelationalStore(":memory:")
        ev = {
            "source_url": "https://www.iima.ac.in/events/cascade-test",
            "title": "Cascade Test",
            "raw_text": "Speaker: Prof. Arvind Sharma, IIM Ahmedabad",
        }
        item_id = store.store_event_record(ev)
        assert store.count_items() == 1
        assert store.count_people() == 1
        assert store.count_item_people() == 1

        # Delete the item
        store._conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        store._conn.commit()

        assert store.count_items() == 0
        assert store.count_item_people() == 0   # Cascaded
        assert store.count_people() == 1        # Person entity retained in people table


# ===========================================================================
# Standalone Runner
# ===========================================================================

if __name__ == "__main__":
    import traceback

    test_classes = [
        TestSchemaAndNormalization,
        TestRelationalLinking,
        TestRequiredQueries,
        TestCheckpointAndIntegrity,
    ]

    passed = failed = 0
    print("=" * 60)
    print("Running Assignment 6 Tests: Entity Storage and Relationships")
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
