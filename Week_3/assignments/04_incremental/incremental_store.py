#!/usr/bin/env python3
"""incremental_store.py - Incremental Collection and Change Detection (Assignment 4)

Tracks discovery records across multiple runs using SQLite.

Core idea
---------
Each URL is stored once.  Every subsequent run updates metadata but does NOT
create a duplicate row.  A content hash over stable fields lets us distinguish:

    Status               Meaning
    --------             --------
    NEW                  URL never seen before this run
    UNCHANGED            URL seen before, content hash identical
    CHANGED              URL seen before, content hash differs
    NOT_SEEN_THIS_RUN    URL in the store but absent from the current listing

Absence from the current listing does NOT mean deletion.  The item may have
scrolled off the first page, the feed may have rotated, or the sitemap may
have pruned old entries.  We preserve the row and simply note it was not seen.

Fields stored per item
----------------------
    url               TEXT PRIMARY KEY
    source_name       TEXT
    discovery_method  TEXT
    title             TEXT
    source_timestamp  TEXT       -- as found in source (string, not parsed)
    content_hash      TEXT       -- sha256 over stable fields
    first_seen_at     TEXT       -- ISO-8601 UTC, set once, never updated
    last_seen_at      TEXT       -- ISO-8601 UTC, updated every run it appears
    fetched_at        TEXT       -- ISO-8601 UTC, updated every run regardless

Content hash inputs (stable, meaningful)
----------------------------------------
    url + title + source_timestamp

Fields excluded from hash (volatile / bookkeeping)
---------------------------------------------------
    fetched_at        -- changes every run by definition; must NOT affect hash
    last_seen_at      -- bookkeeping; changes every run; must NOT affect hash
    first_seen_at     -- set once; irrelevant to content change detection
    discovery_method  -- the same URL could be rediscovered via a different
                         channel; we care about content, not discovery path
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------

class ItemStatus(str, Enum):
    NEW              = "new"
    UNCHANGED        = "unchanged"
    CHANGED          = "changed"
    NOT_SEEN_THIS_RUN = "not_seen_this_run"


# ---------------------------------------------------------------------------
# Result container for a single classified item
# ---------------------------------------------------------------------------

@dataclass
class ClassifiedItem:
    url:              str
    status:           ItemStatus
    source_name:      str
    discovery_method: str
    title:            Optional[str]
    source_timestamp: Optional[str]
    content_hash:     str
    first_seen_at:    str
    last_seen_at:     str
    fetched_at:       str
    old_hash:         Optional[str] = field(default=None, repr=False)  # only on CHANGED


# ---------------------------------------------------------------------------
# Run summary
# ---------------------------------------------------------------------------

@dataclass
class RunSummary:
    new:               int = 0
    unchanged:         int = 0
    changed:           int = 0
    not_seen_this_run: int = 0
    items:             List[ClassifiedItem] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"new={self.new}  changed={self.changed}  "
            f"unchanged={self.unchanged}  not_seen_this_run={self.not_seen_this_run}"
        )

    def by_status(self, status: ItemStatus) -> List[ClassifiedItem]:
        return [i for i in self.items if i.status == status]


# ---------------------------------------------------------------------------
# Content hash
# ---------------------------------------------------------------------------

def compute_content_hash(
    url: str,
    title: Optional[str],
    source_timestamp: Optional[str],
) -> str:
    """Return a stable SHA-256 hex digest over meaningful content fields.

    Only fields that reflect *what the item is about* contribute to the hash.
    Bookkeeping timestamps (fetched_at, last_seen_at, first_seen_at) are
    deliberately excluded so that re-fetching an unchanged item does not
    generate a false CHANGED signal.
    """
    parts = [
        url.strip().lower(),                         # canonical URL
        (title or "").strip().lower(),               # normalised title
        (source_timestamp or "").strip(),            # as-is date string
    ]
    raw = "\x00".join(parts).encode("utf-8")         # NUL-separated for safety
    return hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------
# SQLite-backed store
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS items (
    url               TEXT PRIMARY KEY,
    source_name       TEXT NOT NULL,
    discovery_method  TEXT NOT NULL,
    title             TEXT,
    source_timestamp  TEXT,
    content_hash      TEXT NOT NULL,
    first_seen_at     TEXT NOT NULL,
    last_seen_at      TEXT NOT NULL,
    fetched_at        TEXT NOT NULL
);
"""

_INSERT = """
INSERT INTO items
    (url, source_name, discovery_method, title, source_timestamp,
     content_hash, first_seen_at, last_seen_at, fetched_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

_UPDATE = """
UPDATE items
SET source_name      = ?,
    discovery_method = ?,
    title            = ?,
    source_timestamp = ?,
    content_hash     = ?,
    last_seen_at     = ?,
    fetched_at       = ?
WHERE url = ?;
"""

_TOUCH_FETCHED = """
UPDATE items SET fetched_at = ? WHERE url = ?;
"""


class IncrementalStore:
    """SQLite-backed persistent state for incremental discovery runs.

    Parameters
    ----------
    db_path : str
        Path to the SQLite database file.  Use ``":memory:"`` for tests.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute(_DDL)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Core run method
    # ------------------------------------------------------------------

    def process_run(self, discovery_records: List[Dict[str, Any]]) -> RunSummary:
        """Classify a list of discovery records and persist state.

        Algorithm
        ~~~~~~~~~
        1. Compute content hash for every incoming record.
        2. Look up the URL in the store.
        3. Classify as NEW / UNCHANGED / CHANGED.
        4. For every URL already in the store that was NOT in this run,
           add a NOT_SEEN_THIS_RUN entry to the summary (but do NOT delete).
        5. Commit within a single transaction.

        Parameters
        ----------
        discovery_records : list[dict]
            Records in the canonical discovery shape from Assignment 3.

        Returns
        -------
        RunSummary
        """
        now = _now_iso()
        summary = RunSummary()
        seen_urls: set[str] = set()

        with self._conn:                             # auto-commit / rollback
            for rec in discovery_records:
                url       = rec["discovered_url"]
                src_name  = rec.get("source_name", "")
                method    = rec.get("discovery_method", "")
                title     = rec.get("discovered_title")
                ts        = rec.get("source_timestamp")
                new_hash  = compute_content_hash(url, title, ts)
                seen_urls.add(url)

                existing = self._fetch_row(url)

                if existing is None:
                    # ── NEW ───────────────────────────────────────────
                    self._conn.execute(_INSERT, (
                        url, src_name, method, title, ts,
                        new_hash, now, now, now,
                    ))
                    ci = ClassifiedItem(
                        url=url, status=ItemStatus.NEW,
                        source_name=src_name, discovery_method=method,
                        title=title, source_timestamp=ts,
                        content_hash=new_hash,
                        first_seen_at=now, last_seen_at=now, fetched_at=now,
                    )
                    summary.new += 1

                elif existing["content_hash"] == new_hash:
                    # ── UNCHANGED ─────────────────────────────────────
                    self._conn.execute(_TOUCH_FETCHED, (now, url))
                    # Update last_seen_at too (it was seen this run)
                    self._conn.execute(
                        "UPDATE items SET last_seen_at=?, fetched_at=? WHERE url=?",
                        (now, now, url),
                    )
                    ci = ClassifiedItem(
                        url=url, status=ItemStatus.UNCHANGED,
                        source_name=existing["source_name"],
                        discovery_method=existing["discovery_method"],
                        title=existing["title"],
                        source_timestamp=existing["source_timestamp"],
                        content_hash=new_hash,
                        first_seen_at=existing["first_seen_at"],
                        last_seen_at=now,
                        fetched_at=now,
                    )
                    summary.unchanged += 1

                else:
                    # ── CHANGED ───────────────────────────────────────
                    old_hash = existing["content_hash"]
                    self._conn.execute(_UPDATE, (
                        src_name, method, title, ts,
                        new_hash, now, now, url,
                    ))
                    ci = ClassifiedItem(
                        url=url, status=ItemStatus.CHANGED,
                        source_name=src_name, discovery_method=method,
                        title=title, source_timestamp=ts,
                        content_hash=new_hash,
                        first_seen_at=existing["first_seen_at"],
                        last_seen_at=now,
                        fetched_at=now,
                        old_hash=old_hash,
                    )
                    summary.changed += 1

                summary.items.append(ci)

            # ── NOT_SEEN_THIS_RUN ─────────────────────────────────────
            # Update fetched_at for all stored URLs not in current run,
            # but do NOT change last_seen_at or delete them.
            all_stored = self._all_urls()
            for stored_url in all_stored:
                if stored_url not in seen_urls:
                    self._conn.execute(_TOUCH_FETCHED, (now, stored_url))
                    row = self._fetch_row(stored_url)
                    ci = ClassifiedItem(
                        url=stored_url, status=ItemStatus.NOT_SEEN_THIS_RUN,
                        source_name=row["source_name"],
                        discovery_method=row["discovery_method"],
                        title=row["title"],
                        source_timestamp=row["source_timestamp"],
                        content_hash=row["content_hash"],
                        first_seen_at=row["first_seen_at"],
                        last_seen_at=row["last_seen_at"],
                        fetched_at=now,
                    )
                    summary.not_seen_this_run += 1
                    summary.items.append(ci)

        return summary

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_item(self, url: str) -> Optional[sqlite3.Row]:
        return self._fetch_row(url)

    def all_items(self) -> List[sqlite3.Row]:
        cur = self._conn.execute("SELECT * FROM items ORDER BY first_seen_at")
        return cur.fetchall()

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _fetch_row(self, url: str) -> Optional[sqlite3.Row]:
        cur = self._conn.execute("SELECT * FROM items WHERE url = ?", (url,))
        return cur.fetchone()

    def _all_urls(self) -> List[str]:
        cur = self._conn.execute("SELECT url FROM items")
        return [r[0] for r in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_record(
    url: str,
    title: Optional[str] = None,
    source_timestamp: Optional[str] = None,
    source_name: str = "test_source",
    discovery_method: str = "html_listing",
) -> Dict[str, Any]:
    """Convenience factory matching the Assignment 3 canonical shape."""
    return {
        "discovered_url":   url,
        "discovered_title": title,
        "source_timestamp": source_timestamp,
        "source_name":      source_name,
        "discovery_method": discovery_method,
        "discovered_at":    _now_iso(),
    }


# ---------------------------------------------------------------------------
# CLI demo  (simulates the Run1 / Run2 scenario from the assignment)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    BASE = "https://www.iima.ac.in/the-institute/events/"

    RUN1 = [
        _make_record(BASE + "item-a", title="Item A",         source_timestamp="2026-10-01"),
        _make_record(BASE + "item-b", title="Item B",         source_timestamp="2026-10-02"),
        _make_record(BASE + "item-c", title="Item C",         source_timestamp="2026-10-03"),
    ]

    RUN2 = [
        _make_record(BASE + "item-a", title="Item A",         source_timestamp="2026-10-01"),  # unchanged
        _make_record(BASE + "item-b", title="Item B Updated", source_timestamp="2026-10-10"),  # changed title
        # item-c absent from this run — NOT deleted
        _make_record(BASE + "item-d", title="Item D",         source_timestamp="2026-10-11"),  # new
    ]

    store = IncrementalStore(":memory:")

    print("=" * 60)
    print("RUN 1  (A, B, C)")
    print("=" * 60)
    s1 = store.process_run(RUN1)
    print(s1)
    for item in s1.items:
        print(f"  [{item.status.value:20s}]  {item.url.split('/')[-1]}")

    print()
    print("=" * 60)
    print("RUN 2  (A unchanged, B changed, C absent, D new)")
    print("=" * 60)
    s2 = store.process_run(RUN2)
    print(s2)
    for item in s2.items:
        print(f"  [{item.status.value:20s}]  {item.url.split('/')[-1]}", end="")
        if item.status == ItemStatus.CHANGED:
            print(f"  (hash {item.old_hash[:8]}... -> {item.content_hash[:8]}...)", end="")
        print()

    print()
    print("Store now holds", store.count(), "rows (C is preserved, not deleted)")
