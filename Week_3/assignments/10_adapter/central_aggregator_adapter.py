#!/usr/bin/env python3
"""central_aggregator_adapter.py - Central Aggregator Implementation (Assignment 10)

Synthesizes Week 3 capabilities into an end-to-end monitored aggregator pipeline:
1. Central Discovery Surface (HTML, RSS, Sitemap)
2. URL Scope Bounding & Deduplication
3. Content Routing (Event vs Announcement vs PDF vs External)
4. Detail Parsing & Canonical Shape Normalization
5. Explicit Entity Extraction (People & Organizations with Provenance)
6. Incremental Change Detection & Relational Storage (SQLite)
7. Source Health Metrics & Standardized Run Summary

Ceiling Control:
- Configured with max_items (20–40) and max_pages (2–5) to prove architecture
  without unbounded scraping.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from bs4 import BeautifulSoup

# Setup import paths across Week 3 modules
_HERE = os.path.dirname(os.path.abspath(__file__))
_ASSIGNMENTS_DIR = os.path.abspath(os.path.join(_HERE, ".."))

for sub in ["02_scope", "03_interface", "04_incremental", "05_extraction", "06_entities", "08_routing", "09_metrics"]:
    path = os.path.join(_ASSIGNMENTS_DIR, sub)
    if path not in sys.path:
        sys.path.insert(0, path)

from scope_filter import UrlScopeFilter, is_allowed_item_url, _canonicalize as canonicalize_url
from aggregator_discovery import discover_from_html, DISCOVERY_SCHEMA_KEYS
from incremental_store import compute_content_hash, ItemStatus
from entity_extractor import extract_entities
from entity_relational_store import EntityRelationalStore
from content_router import classify_discovered_item, ItemType
from run_summary import RunMetrics, RunHealthStatus, persist_metrics_to_db, persist_metrics_to_log


# ---------------------------------------------------------------------------
# Default Config for Central IIMA Aggregator
# ---------------------------------------------------------------------------

DEFAULT_IIMA_CONFIG = {
    "source_name":            "iima_events",
    "allowed_hostname":       "www.iima.ac.in",
    "allowed_path_prefixes":  ["/the-institute/events", "/news"],
    "excluded_path_prefixes": [
        "/login", "/search", "/calendar", "/filter", "/sites/default/files",
    ],
    "allow_external":         False,
    "max_items":              30,      # Ceiling: 20-40 records
    "max_pages":              3,       # Ceiling: 2-5 pages
    "ignored_query_params":   ["utm_source", "utm_medium", "utm_campaign", "fbclid", "gclid"],
}


# ---------------------------------------------------------------------------
# Central Aggregator Adapter
# ---------------------------------------------------------------------------

class CentralAggregatorAdapter:
    """End-to-end monitored aggregator coordinating discovery, scope,
    extraction, incremental storage, and run summary metrics.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        db_path: str = ":memory:",
        log_path: Optional[str] = None,
    ) -> None:
        self.config = config or DEFAULT_IIMA_CONFIG.copy()
        self.db_path = db_path
        self.log_path = log_path
        self.scope_filter = UrlScopeFilter(self.config)
        self.store = EntityRelationalStore(self.db_path)
        self._init_incremental_table()

    def _init_incremental_table(self) -> None:
        """Ensure incremental content hash column and table exist."""
        self.store._conn.execute("""
            CREATE TABLE IF NOT EXISTS item_hashes (
                item_url     TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at  TEXT NOT NULL,
                fetched_at    TEXT NOT NULL
            );
        """)
        self.store._conn.commit()

    # -----------------------------------------------------------------------
    # Main Execution Pipeline
    # -----------------------------------------------------------------------

    def run(
        self,
        html_fixture_path: Optional[str] = None,
        raw_html: Optional[str] = None,
        http_status: int = 200,
    ) -> RunMetrics:
        """Execute a complete aggregator run and generate RunMetrics."""
        started_at = _now_iso()
        source_name = self.config.get("source_name", "iima_events")
        pages_fetched = 1 if http_status == 200 else 0

        # Handle HTTP error immediately
        if http_status >= 400:
            finished_at = _now_iso()
            metrics = RunMetrics(
                source=source_name,
                started_at=started_at,
                finished_at=finished_at,
                http_status=http_status,
                pages_fetched=0,
                failed=1,
            )
            self._persist_metrics(metrics)
            return metrics

        # Read fixture content
        content = raw_html
        if content is None and html_fixture_path and os.path.exists(html_fixture_path):
            with open(html_fixture_path, "r", encoding="utf-8") as f:
                content = f.read()

        if not content:
            finished_at = _now_iso()
            metrics = RunMetrics(
                source=source_name,
                started_at=started_at,
                finished_at=finished_at,
                http_status=http_status,
                pages_fetched=pages_fetched,
                failed=1,
            )
            self._persist_metrics(metrics)
            return metrics

        # -------------------------------------------------------------------
        # Step 1: Central Discovery Surface (HTML Listing / Feed / Sitemap)
        # -------------------------------------------------------------------
        cfg = dict(self.config)
        temp_fixture = None
        if html_fixture_path:
            cfg["html_fixture"] = html_fixture_path
        elif raw_html:
            import tempfile
            with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tf:
                tf.write(raw_html)
                temp_fixture = tf.name
            cfg["html_fixture"] = temp_fixture

        discovered_records = discover_from_html(cfg)
        if temp_fixture and os.path.exists(temp_fixture):
            try:
                os.remove(temp_fixture)
            except Exception:
                pass
        items_discovered = len(discovered_records)

        # -------------------------------------------------------------------
        # Step 2: Scope Filter & Deduplication
        # -------------------------------------------------------------------
        candidate_items: List[Dict[str, Any]] = []
        for rec in discovered_records:
            url = rec["discovered_url"]
            # The discover_from_html already applies scope filter, but we verify
            # ceiling here to strictly obey Assignment 10 max_items ceiling
            if len(candidate_items) >= self.config.get("max_items", 30):
                break
            candidate_items.append(rec)

        # -------------------------------------------------------------------
        # Step 3: Content Routing & Detail Parsing
        # -------------------------------------------------------------------
        soup = BeautifulSoup(content, "html.parser")
        row_elements = soup.find_all("div", class_="views-row")
        summary_lookup: Dict[str, str] = {}

        for row in row_elements:
            a = row.find("a")
            if a and a.get("href"):
                full_u = a["href"]
                if not full_u.startswith("http"):
                    full_u = "https://" + self.config["allowed_hostname"] + full_u
                clean_u = canonicalize_url(full_u, self.config)
                sum_div = row.find(class_="event-summary")
                if sum_div:
                    # Use separator="\n" so distinct child tags or lines are separate lines
                    summary_lookup[clean_u] = sum_div.get_text(separator="\n", strip=True)

        items_parsed = 0
        new_count = 0
        changed_count = 0
        unchanged_count = 0
        failed_count = 0
        people_extracted = 0
        organizations_extracted = 0

        dates_present = 0
        speakers_present = 0
        orgs_present = 0

        now = _now_iso()

        for item in candidate_items:
            try:
                url = item["discovered_url"]
                title = item.get("discovered_title") or ""
                timestamp = item.get("source_timestamp")

                # Content routing
                routed_type = classify_discovered_item(item)
                if routed_type != ItemType.EVENT.value:
                    # Non-event items (PDFs, announcements, etc.) are recorded
                    # without schema coercion
                    self.store.upsert_item(item_url=url, title=title, item_type=routed_type)
                    items_parsed += 1
                    continue

                items_parsed += 1
                if timestamp:
                    dates_present += 1

                # Detail parsing: extract narrative summary & explicit entities
                raw_text = summary_lookup.get(url, title)
                entities = extract_entities(raw_text)

                p_list = entities.get("people", [])
                o_list = entities.get("organizations", [])

                if p_list:
                    speakers_present += 1
                    people_extracted += len(p_list)
                if o_list:
                    orgs_present += 1
                    organizations_extracted += len(o_list)

                # -----------------------------------------------------------
                # Step 4: Incremental Change Detection
                # -----------------------------------------------------------
                content_hash = compute_content_hash(url, title, timestamp)
                cur = self.store._conn.execute(
                    "SELECT content_hash, first_seen_at FROM item_hashes WHERE item_url = ?",
                    (url,),
                )
                existing = cur.fetchone()

                if existing is None:
                    # NEW
                    self.store._conn.execute(
                        "INSERT INTO item_hashes VALUES (?, ?, ?, ?, ?)",
                        (url, content_hash, now, now, now),
                    )
                    new_count += 1
                elif existing["content_hash"] == content_hash:
                    # UNCHANGED
                    self.store._conn.execute(
                        "UPDATE item_hashes SET last_seen_at = ?, fetched_at = ? WHERE item_url = ?",
                        (now, now, url),
                    )
                    unchanged_count += 1
                else:
                    # CHANGED
                    self.store._conn.execute(
                        "UPDATE item_hashes SET content_hash = ?, last_seen_at = ?, fetched_at = ? WHERE item_url = ?",
                        (content_hash, now, now, url),
                    )
                    changed_count += 1

                # -----------------------------------------------------------
                # Step 5: Relational Storage & Entity Linking
                # -----------------------------------------------------------
                self.store.store_event_record(
                    {
                        "source_url": url,
                        "title": title,
                        "raw_text": raw_text,
                        "source_name": source_name,
                        "item_type": "event",
                    },
                    entities=entities,
                )

            except Exception as e:
                failed_count += 1

        self.store._conn.commit()
        finished_at = _now_iso()

        pct_date = (dates_present / items_parsed * 100.0) if items_parsed > 0 else 0.0
        pct_spk  = (speakers_present / items_parsed * 100.0) if items_parsed > 0 else 0.0
        pct_org  = (orgs_present / items_parsed * 100.0) if items_parsed > 0 else 0.0

        metrics = RunMetrics(
            source=source_name,
            started_at=started_at,
            finished_at=finished_at,
            http_status=http_status,
            pages_fetched=pages_fetched,
            items_discovered=items_discovered,
            items_parsed=items_parsed,
            new=new_count,
            changed=changed_count,
            unchanged=unchanged_count,
            failed=failed_count,
            people_extracted=people_extracted,
            organizations_extracted=organizations_extracted,
            pct_with_date=pct_date,
            pct_with_speaker=pct_spk,
            pct_with_organization=pct_org,
        )

        self._persist_metrics(metrics)
        return metrics

    def close(self) -> None:
        """Close the underlying store connection."""
        if hasattr(self, "store") and self.store:
            try:
                self.store.close()
            except Exception:
                pass

    def _persist_metrics(self, metrics: RunMetrics) -> None:
        """Persist metrics to SQLite and log file."""
        try:
            persist_metrics_to_db(metrics, self.db_path)
        except Exception:
            pass

        if self.log_path:
            try:
                persist_metrics_to_log(metrics, self.log_path)
            except Exception:
                pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# CLI Execution Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _HERE = os.path.dirname(os.path.abspath(__file__))
    fixture = os.path.join(_HERE, "fixtures", "central_listing.html")
    log_file = os.path.join(_HERE, "aggregator.log")

    adapter = CentralAggregatorAdapter(
        db_path=":memory:",
        log_path=log_file,
    )

    print("=" * 65)
    print("RUN 1: Initial Central Ingestion Run")
    print("=" * 65)
    m1 = adapter.run(html_fixture_path=fixture)
    print(m1.to_summary_text())

    print("\n" + "=" * 65)
    print("RUN 2: Incremental Run (Simulating Re-crawl)")
    print("=" * 65)
    m2 = adapter.run(html_fixture_path=fixture)
    print(m2.to_summary_text())

    print("\n" + "=" * 65)
    print("RELATIONAL STORE SUMMARY:")
    print(f"Total Stored Items:         {adapter.store.count_items()}")
    print(f"Total Unique People:        {adapter.store.count_people()}")
    print(f"Total Unique Organizations: {adapter.store.count_organizations()}")
    print(f"Event-People Links:         {adapter.store.count_item_people()}")
    print(f"Event-Org Links:            {adapter.store.count_item_organizations()}")
    print("=" * 65)
