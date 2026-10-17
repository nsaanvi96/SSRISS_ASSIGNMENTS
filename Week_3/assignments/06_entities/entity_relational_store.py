#!/usr/bin/env python3
"""entity_relational_store.py - Entity Storage and Relationships (Assignment 6)

Extends SQLite storage to model many-to-many relationships between Events (Items),
People, and Organizations using dedicated join tables with provenance tracking.

Relational Model
----------------
items (events)           people                 organizations
--------------           ------                 -------------
id (PK)                  id (PK)                id (PK)
item_url (UNIQUE)        normalized_name (UQ)   normalized_name (UQ)
item_type                display_name           display_name
title                    created_at             created_at
source_name
raw_text
created_at
      │                        │                       │
      │ 1                      │ 1                     │ 1
      ├───────────┐            │                       │
      │           │            │                       │
      │ N         │ N          │ N                     │ N
item_people   item_organizations
-----------   ------------------
item_id  (FK) item_id         (FK)
person_id(FK) organization_id (FK)
role          role
affiliation   source_text
source_text
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Enable import of entity extractor from 05_extraction
_HERE = os.path.dirname(os.path.abspath(__file__))
_EXTRACTOR_DIR = os.path.abspath(os.path.join(_HERE, "..", "05_extraction"))
if _EXTRACTOR_DIR not in sys.path:
    sys.path.insert(0, _EXTRACTOR_DIR)

try:
    from entity_extractor import extract_entities
except ImportError:
    extract_entities = None  # type: ignore


# ---------------------------------------------------------------------------
# DDL Definition
# ---------------------------------------------------------------------------

_DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_url    TEXT UNIQUE NOT NULL,
    item_type   TEXT DEFAULT 'event',
    title       TEXT,
    source_name TEXT,
    raw_text    TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS people (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    normalized_name TEXT UNIQUE NOT NULL,
    display_name    TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS organizations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    normalized_name TEXT UNIQUE NOT NULL,
    display_name    TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS item_people (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id         INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    person_id       INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    affiliation_raw TEXT,
    source_text     TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    UNIQUE(item_id, person_id, role)
);

CREATE TABLE IF NOT EXISTS item_organizations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id         INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    source_text     TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    UNIQUE(item_id, organization_id, role)
);

-- Query performance indexes
CREATE INDEX IF NOT EXISTS idx_item_people_person ON item_people(person_id);
CREATE INDEX IF NOT EXISTS idx_item_people_item   ON item_people(item_id);
CREATE INDEX IF NOT EXISTS idx_item_people_role   ON item_people(role);

CREATE INDEX IF NOT EXISTS idx_item_orgs_org      ON item_organizations(organization_id);
CREATE INDEX IF NOT EXISTS idx_item_orgs_item     ON item_organizations(item_id);
CREATE INDEX IF NOT EXISTS idx_item_orgs_role     ON item_organizations(role);
"""


# ---------------------------------------------------------------------------
# Normalization Helper
# ---------------------------------------------------------------------------

_HONORIFIC_PREFIX_REGEX = re.compile(
    r"^(?:dr|prof|professor|mr|ms|mrs|smt|shri|justice)\.?\s+",
    re.IGNORECASE,
)

def normalize_name(raw_name: str) -> str:
    """Return a conservative normalized matching key for person or org names.
    
    Rules:
    - Strips leading/trailing whitespace.
    - Lowers casing.
    - Strips common titles/honorifics (Dr., Prof., Smt., etc.) so that
      'Prof. Arvind Sharma' and 'Dr. Arvind Sharma' share the same matching key.
    - Removes internal duplicate whitespace and punctuation.
    - Preserves distinct names: 'Rajesh Kumar' and 'R. Kumar' remain separate.
    """
    clean = raw_name.strip().lower()
    # Strip honorific prefix
    clean = _HONORIFIC_PREFIX_REGEX.sub("", clean).strip()
    # Replace multiple spaces with a single space
    clean = re.sub(r"\s+", " ", clean)
    return clean


def normalize_org_name(raw_org: str) -> str:
    """Return a normalized matching key for organization names."""
    clean = raw_org.strip().lower()
    clean = re.sub(r"\s+", " ", clean)
    return clean


# ---------------------------------------------------------------------------
# Relational Store
# ---------------------------------------------------------------------------

class EntityRelationalStore:
    """SQLite-backed relational storage for Events, People, and Organizations."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.executescript(_DDL)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Core Entity Upserts
    # ------------------------------------------------------------------

    def upsert_item(
        self,
        item_url: str,
        title: Optional[str] = None,
        source_name: Optional[str] = "iima",
        raw_text: Optional[str] = None,
        item_type: str = "event",
    ) -> int:
        """Insert or retrieve an event item by unique item_url."""
        now = _now_iso()
        cur = self._conn.execute(
            "SELECT id FROM items WHERE item_url = ?",
            (item_url,),
        )
        row = cur.fetchone()
        if row:
            # Update title/raw_text if provided
            self._conn.execute(
                "UPDATE items SET title = COALESCE(?, title), raw_text = COALESCE(?, raw_text) WHERE id = ?",
                (title, raw_text, row["id"]),
            )
            self._conn.commit()
            return row["id"]

        cur = self._conn.execute(
            """INSERT INTO items (item_url, item_type, title, source_name, raw_text, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (item_url, item_type, title, source_name, raw_text, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_or_create_person(self, display_name: str) -> int:
        """Get or create a person record using normalized_name as matching key."""
        now = _now_iso()
        norm = normalize_name(display_name)
        cur = self._conn.execute(
            "SELECT id FROM people WHERE normalized_name = ?",
            (norm,),
        )
        row = cur.fetchone()
        if row:
            return row["id"]

        cur = self._conn.execute(
            "INSERT INTO people (normalized_name, display_name, created_at) VALUES (?, ?, ?)",
            (norm, display_name.strip(), now),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_or_create_organization(self, display_name: str) -> int:
        """Get or create an organization record using normalized_name as matching key."""
        now = _now_iso()
        norm = normalize_org_name(display_name)
        cur = self._conn.execute(
            "SELECT id FROM organizations WHERE normalized_name = ?",
            (norm,),
        )
        row = cur.fetchone()
        if row:
            return row["id"]

        cur = self._conn.execute(
            "INSERT INTO organizations (normalized_name, display_name, created_at) VALUES (?, ?, ?)",
            (norm, display_name.strip(), now),
        )
        self._conn.commit()
        return cur.lastrowid

    # ------------------------------------------------------------------
    # Relationship Linking
    # ------------------------------------------------------------------

    def link_person_to_item(
        self,
        item_id: int,
        person_id: int,
        role: str,
        source_text: str,
        affiliation_raw: Optional[str] = None,
    ) -> int:
        """Create a link between an item and a person with role and provenance."""
        now = _now_iso()
        cur = self._conn.execute(
            """INSERT INTO item_people (item_id, person_id, role, affiliation_raw, source_text, created_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(item_id, person_id, role) DO UPDATE SET
                   affiliation_raw = COALESCE(excluded.affiliation_raw, item_people.affiliation_raw),
                   source_text = excluded.source_text""",
            (item_id, person_id, role, affiliation_raw, source_text, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def link_organization_to_item(
        self,
        item_id: int,
        organization_id: int,
        role: str,
        source_text: str,
    ) -> int:
        """Create a link between an item and an organization with role and provenance."""
        now = _now_iso()
        cur = self._conn.execute(
            """INSERT INTO item_organizations (item_id, organization_id, role, source_text, created_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(item_id, organization_id, role) DO UPDATE SET
                   source_text = excluded.source_text""",
            (item_id, organization_id, role, source_text, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def store_event_record(
        self,
        record: Dict[str, Any],
        entities: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Store an event record and connect all extracted people and organizations."""
        url = record.get("source_url") or record.get("item_url") or record.get("discovered_url")
        if not url:
            raise ValueError("Record must have 'source_url', 'item_url', or 'discovered_url'")

        item_id = self.upsert_item(
            item_url=url,
            title=record.get("title") or record.get("discovered_title"),
            source_name=record.get("source_name", "iima"),
            raw_text=record.get("raw_text") or record.get("description"),
            item_type=record.get("item_type", "event"),
        )

        if entities is None and extract_entities is not None:
            entities = extract_entities(record)

        if entities:
            # Link People
            for p in entities.get("people", []):
                p_id = self.get_or_create_person(p["name"])
                self.link_person_to_item(
                    item_id=item_id,
                    person_id=p_id,
                    role=p["role"],
                    source_text=p["source_text"],
                    affiliation_raw=p.get("affiliation_raw"),
                )

            # Link Organizations
            for o in entities.get("organizations", []):
                o_id = self.get_or_create_organization(o["name"])
                self.link_organization_to_item(
                    item_id=item_id,
                    organization_id=o_id,
                    role=o["role"],
                    source_text=o["source_text"],
                )

        return item_id

    # ------------------------------------------------------------------
    # Required Analysis Queries
    # ------------------------------------------------------------------

    def get_events_by_person_name(self, query_name: str) -> List[Dict[str, Any]]:
        """Query 1: Which events in my local database mention this exact normalized person name?
        
        Performs exact matching on the normalized name key.
        """
        norm = normalize_name(query_name)
        sql = """
        SELECT 
            i.id AS event_id,
            i.item_url,
            i.title AS event_title,
            p.display_name AS person_name,
            p.normalized_name,
            ip.role,
            ip.affiliation_raw,
            ip.source_text
        FROM items i
        JOIN item_people ip ON i.id = ip.item_id
        JOIN people p       ON ip.person_id = p.id
        WHERE p.normalized_name = ?
        ORDER BY i.id ASC;
        """
        cur = self._conn.execute(sql, (norm,))
        return [dict(r) for r in cur.fetchall()]

    def get_organizations_by_role(self, role: str = "organizer") -> List[Dict[str, Any]]:
        """Query 2: Which organizations have appeared as organizers in my collected sample?
        
        Returns distinct organizations with their count of appearances in that role.
        """
        sql = """
        SELECT 
            o.id AS organization_id,
            o.display_name,
            o.normalized_name,
            io.role,
            COUNT(DISTINCT io.item_id) AS event_count,
            GROUP_CONCAT(DISTINCT i.title) AS event_titles
        FROM organizations o
        JOIN item_organizations io ON o.id = io.organization_id
        JOIN items i               ON io.item_id = i.id
        WHERE io.role = ?
        GROUP BY o.id, o.display_name, o.normalized_name, io.role
        ORDER BY event_count DESC, o.display_name ASC;
        """
        cur = self._conn.execute(sql, (role,))
        return [dict(r) for r in cur.fetchall()]

    def get_event_entities(self, item_id: int) -> Dict[str, Any]:
        """Fetch all connected people and organizations for a specific event."""
        people_cur = self._conn.execute(
            """SELECT p.id, p.display_name, p.normalized_name, ip.role, ip.affiliation_raw, ip.source_text
               FROM people p
               JOIN item_people ip ON p.id = ip.person_id
               WHERE ip.item_id = ?
               ORDER BY ip.id ASC""",
            (item_id,),
        )
        orgs_cur = self._conn.execute(
            """SELECT o.id, o.display_name, o.normalized_name, io.role, io.source_text
               FROM organizations o
               JOIN item_organizations io ON o.id = io.organization_id
               WHERE io.item_id = ?
               ORDER BY io.id ASC""",
            (item_id,),
        )
        return {
            "people": [dict(r) for r in people_cur.fetchall()],
            "organizations": [dict(r) for r in orgs_cur.fetchall()],
        }

    # ------------------------------------------------------------------
    # Introspection & Counts
    # ------------------------------------------------------------------

    def count_items(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]

    def count_people(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]

    def count_organizations(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM organizations").fetchone()[0]

    def count_item_people(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM item_people").fetchone()[0]

    def count_item_organizations(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM item_organizations").fetchone()[0]

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# CLI Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    store = EntityRelationalStore(":memory:")

    # Ingest from fixtures
    fixture_path = os.path.join(_EXTRACTOR_DIR, "fixtures", "events_sample.json")
    if os.path.exists(fixture_path):
        with open(fixture_path, "r", encoding="utf-8") as f:
            sample_records = json.load(f)

        print("=" * 60)
        print(f"Ingesting {len(sample_records)} events into Relational Store...")
        print("=" * 60)

        for rec in sample_records:
            store.store_event_record(rec)

        print(f"Items stored:         {store.count_items()}")
        print(f"Unique People:        {store.count_people()}")
        print(f"Unique Organizations: {store.count_organizations()}")
        print(f"Event-People Links:   {store.count_item_people()}")
        print(f"Event-Org Links:      {store.count_item_organizations()}")

        print("\n" + "=" * 60)
        print("QUERY 1: Events mentioning normalized name 'arvind sharma':")
        print("=" * 60)
        q1_results = store.get_events_by_person_name("arvind sharma")
        for res in q1_results:
            print(f"- [{res['role']}] {res['event_title']} (Event ID: {res['event_id']})")
            print(f"  Source: '{res['source_text']}'")

        print("\n" + "=" * 60)
        print("QUERY 2: Organizations that appeared as 'organizer':")
        print("=" * 60)
        q2_results = store.get_organizations_by_role("organizer")
        for res in q2_results:
            print(f"- {res['display_name']} (events: {res['event_count']})")
    else:
        print("Fixture not found at:", fixture_path)
