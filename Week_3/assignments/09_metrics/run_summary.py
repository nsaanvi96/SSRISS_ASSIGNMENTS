#!/usr/bin/env python3
"""run_summary.py - Source Health and Coverage Metrics (Assignment 9)

Collects and formats per-run monitoring quality metrics, diagnostic health
evaluations, and coverage statistics.

Solves the Checkpoint:
- A reviewer can immediately distinguish:
    (1) "Source had no new content" (items discovered, 0 new, unchanged > 0, failed = 0)
    from
    (2) "Parser broke and returned zero content" (pages fetched > 0, 0 items parsed/discovered, failed > 0).
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Health Status Enum
# ---------------------------------------------------------------------------

class RunHealthStatus(str, Enum):
    HEALTHY_NEW_CONTENT    = "HEALTHY: New or changed content collected"
    HEALTHY_NO_NEW_CONTENT = "HEALTHY: Source had no new content (all unchanged)"
    PARSER_FAILURE         = "FAILURE: Parser broke (0 items extracted from fetched page)"
    HTTP_FAILURE           = "FAILURE: HTTP request failed"
    PARTIAL_FAILURE        = "DEGRADED: Partial parse or detail failures detected"


# ---------------------------------------------------------------------------
# Run Metrics Data Model
# ---------------------------------------------------------------------------

@dataclass
class RunMetrics:
    source:                  str
    started_at:              str
    finished_at:             str
    http_status:             Optional[int] = 200
    pages_fetched:           int = 0
    items_discovered:        int = 0
    items_parsed:            int = 0
    new:                     int = 0
    changed:                 int = 0
    unchanged:               int = 0
    failed:                  int = 0
    people_extracted:        int = 0
    organizations_extracted: int = 0
    pct_with_date:           float = 0.0
    pct_with_speaker:        float = 0.0
    pct_with_organization:   float = 0.0
    health_status:           str = ""
    diagnostic_message:      str = ""

    def __post_init__(self):
        if not self.health_status:
            status, msg = diagnose_health(self)
            self.health_status = status.value
            self.diagnostic_message = msg

    def to_summary_text(self) -> str:
        """Generate the canonical key-value summary format required by Assignment 9."""
        lines = [
            f"SOURCE: {self.source}",
            f"PAGES_FETCHED: {self.pages_fetched}",
            f"ITEMS_DISCOVERED: {self.items_discovered}",
            f"ITEMS_PARSED: {self.items_parsed}",
            f"NEW: {self.new}",
            f"CHANGED: {self.changed}",
            f"UNCHANGED: {self.unchanged}",
            f"FAILED: {self.failed}",
            f"PEOPLE_EXTRACTED: {self.people_extracted}",
            f"ORGANIZATIONS_EXTRACTED: {self.organizations_extracted}",
            f"PCT_WITH_DATE: {self.pct_with_date:.1f}%",
            f"PCT_WITH_SPEAKER: {self.pct_with_speaker:.1f}%",
            f"PCT_WITH_ORGANIZATION: {self.pct_with_organization:.1f}%",
            f"STATUS: {self.health_status}",
        ]
        if self.diagnostic_message:
            lines.append(f"DIAGNOSIS: {self.diagnostic_message}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Health Diagnostic Engine
# ---------------------------------------------------------------------------

def diagnose_health(metrics: RunMetrics) -> Tuple[RunHealthStatus, str]:
    """Diagnose the health of an aggregator run.
    
    Strictly distinguishes:
    - 'Source had no new content' (healthy steady state)
    - 'Parser broke and returned zero content' (critical scraper breakage)
    """
    # 1. HTTP failure check
    if metrics.http_status is not None and metrics.http_status >= 400:
        return (
            RunHealthStatus.HTTP_FAILURE,
            f"HTTP request returned error code {metrics.http_status}",
        )

    # 2. Critical Parser Breakage Check (Checkpoint)
    # The monitor fetched pages successfully (HTTP 200), but parsed ZERO items,
    # or all attempts resulted in parse failures.
    if metrics.pages_fetched > 0 and metrics.items_parsed == 0:
        return (
            RunHealthStatus.PARSER_FAILURE,
            "CRITICAL: Page fetched successfully, but parser returned 0 items. "
            "Site markup or CSS selectors likely changed.",
        )

    # 3. Partial Failures
    if metrics.failed > 0:
        return (
            RunHealthStatus.PARTIAL_FAILURE,
            f"{metrics.failed} items failed during parsing or extraction.",
        )

    # 4. Steady State: No New Content (Checkpoint)
    # The parser worked, items were discovered and matched existing database hashes,
    # and exactly 0 items were new or changed.
    if metrics.items_discovered > 0 and metrics.new == 0 and metrics.changed == 0 and metrics.unchanged > 0:
        return (
            RunHealthStatus.HEALTHY_NO_NEW_CONTENT,
            f"Healthy: Source active ({metrics.items_discovered} items visible); "
            "no new or updated items since previous run.",
        )

    # 5. Active Discovery: New or Changed Content
    if metrics.new > 0 or metrics.changed > 0:
        return (
            RunHealthStatus.HEALTHY_NEW_CONTENT,
            f"Healthy: Processed {metrics.new} new and {metrics.changed} updated items.",
        )

    return (RunHealthStatus.HEALTHY_NO_NEW_CONTENT, "Run completed.")


# ---------------------------------------------------------------------------
# SQLite Persistence
# ---------------------------------------------------------------------------

_METRICS_DDL = """
CREATE TABLE IF NOT EXISTS run_metrics (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    source                  TEXT NOT NULL,
    started_at              TEXT NOT NULL,
    finished_at             TEXT NOT NULL,
    http_status             INTEGER,
    pages_fetched           INTEGER NOT NULL,
    items_discovered        INTEGER NOT NULL,
    items_parsed            INTEGER NOT NULL,
    new                     INTEGER NOT NULL,
    changed                 INTEGER NOT NULL,
    unchanged               INTEGER NOT NULL,
    failed                  INTEGER NOT NULL,
    people_extracted        INTEGER NOT NULL,
    organizations_extracted INTEGER NOT NULL,
    pct_with_date           REAL NOT NULL,
    pct_with_speaker        REAL NOT NULL,
    pct_with_organization   REAL NOT NULL,
    health_status           TEXT NOT NULL,
    diagnostic_message      TEXT,
    summary_text            TEXT NOT NULL
);
"""

def persist_metrics_to_db(metrics: RunMetrics, db_path: str) -> int:
    """Store run summary metrics into SQLite run_metrics table."""
    conn = sqlite3.connect(db_path)
    conn.execute(_METRICS_DDL)
    cur = conn.execute(
        """INSERT INTO run_metrics (
            source, started_at, finished_at, http_status, pages_fetched,
            items_discovered, items_parsed, new, changed, unchanged, failed,
            people_extracted, organizations_extracted, pct_with_date,
            pct_with_speaker, pct_with_organization, health_status,
            diagnostic_message, summary_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            metrics.source, metrics.started_at, metrics.finished_at,
            metrics.http_status, metrics.pages_fetched, metrics.items_discovered,
            metrics.items_parsed, metrics.new, metrics.changed, metrics.unchanged,
            metrics.failed, metrics.people_extracted, metrics.organizations_extracted,
            metrics.pct_with_date, metrics.pct_with_speaker, metrics.pct_with_organization,
            metrics.health_status, metrics.diagnostic_message, metrics.to_summary_text(),
        ),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def persist_metrics_to_log(metrics: RunMetrics, log_path: str) -> None:
    """Append structured run metrics block to a log file."""
    block = f"\n{'='*50}\nRUN SUMMARY: {metrics.started_at}\n{'='*50}\n{metrics.to_summary_text()}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(block)


# ---------------------------------------------------------------------------
# Simulated Execution Pipeline with Metrics
# ---------------------------------------------------------------------------

def run_monitored_pipeline(
    source_name: str,
    html_content: str,
    http_status: int = 200,
    known_urls: Optional[set[str]] = None,
) -> RunMetrics:
    """Execute an aggregator parsing run against HTML content, collecting full metrics.
    
    Parses `.event-card` elements, extracts fields, checks novelty against `known_urls`,
    and computes coverage metrics.
    """
    started_at = _now_iso()
    if known_urls is None:
        known_urls = set()

    pages_fetched = 1 if http_status == 200 else 0
    if http_status >= 400 or not html_content:
        finished_at = _now_iso()
        return RunMetrics(
            source=source_name,
            started_at=started_at,
            finished_at=finished_at,
            http_status=http_status,
            pages_fetched=pages_fetched,
            failed=1 if http_status >= 400 else 0,
        )

    soup = BeautifulSoup(html_content, "html.parser")
    cards = soup.find_all("article", class_="event-card")

    items_discovered = len(cards)
    items_parsed = 0
    failed = 0
    new_count = 0
    unchanged_count = 0

    people_count = 0
    org_count = 0

    dates_present = 0
    speakers_present = 0
    orgs_present = 0

    # If cards is empty, check if body had content that failed to match selectors
    if items_discovered == 0:
        # Check if the page had meaningful text that we failed to parse
        body_text = soup.get_text().strip()
        if len(body_text) > 50:
            failed = 1  # Unmatched page content indicates selector failure

    for card in cards:
        try:
            title_tag = card.find(class_="event-title")
            a_tag = title_tag.find("a") if title_tag else None
            if not a_tag or not a_tag.get("href"):
                failed += 1
                continue

            url = a_tag["href"]
            title = a_tag.get_text(strip=True)
            items_parsed += 1

            # Date coverage
            date_tag = card.find(class_="event-date")
            if date_tag and (date_tag.get("datetime") or date_tag.get_text(strip=True)):
                dates_present += 1

            # Speaker coverage
            speaker_tag = card.find(class_="event-speaker")
            if speaker_tag and "Speaker:" in speaker_tag.get_text():
                speakers_present += 1
                people_count += 1

            # Org coverage
            org_tag = card.find(class_="event-org")
            if org_tag and "Organized by:" in org_tag.get_text():
                orgs_present += 1
                org_count += 1

            # Incremental novelty check
            if url in known_urls:
                unchanged_count += 1
            else:
                new_count += 1
                known_urls.add(url)

        except Exception:
            failed += 1

    finished_at = _now_iso()

    pct_date = (dates_present / items_parsed * 100.0) if items_parsed > 0 else 0.0
    pct_spk  = (speakers_present / items_parsed * 100.0) if items_parsed > 0 else 0.0
    pct_org  = (orgs_present / items_parsed * 100.0) if items_parsed > 0 else 0.0

    return RunMetrics(
        source=source_name,
        started_at=started_at,
        finished_at=finished_at,
        http_status=http_status,
        pages_fetched=pages_fetched,
        items_discovered=items_discovered,
        items_parsed=items_parsed,
        new=new_count,
        changed=0,
        unchanged=unchanged_count,
        failed=failed,
        people_extracted=people_count,
        organizations_extracted=org_count,
        pct_with_date=pct_date,
        pct_with_speaker=pct_spk,
        pct_with_organization=pct_org,
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# CLI Demo: Healthy vs Broken Fixture Demonstration
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _HERE = os.path.dirname(os.path.abspath(__file__))
    valid_file = os.path.join(_HERE, "fixtures", "valid_events.html")
    broken_file = os.path.join(_HERE, "fixtures", "broken_events.html")

    print("=" * 65)
    print("RUN 1: Healthy Valid Fixture (First Ingestion)")
    print("=" * 65)
    with open(valid_file, "r", encoding="utf-8") as f:
        valid_html = f.read()

    known: set[str] = set()
    m1 = run_monitored_pipeline("iima_events", valid_html, known_urls=known)
    print(m1.to_summary_text())

    print("\n" + "=" * 65)
    print("RUN 2: Healthy Valid Fixture (Second Ingestion - No New Content)")
    print("=" * 65)
    m2 = run_monitored_pipeline("iima_events", valid_html, known_urls=known)
    print(m2.to_summary_text())

    print("\n" + "=" * 65)
    print("RUN 3: Deliberately Broken Fixture (Site Redesign / Selector Break)")
    print("=" * 65)
    with open(broken_file, "r", encoding="utf-8") as f:
        broken_html = f.read()

    m3 = run_monitored_pipeline("iima_events", broken_html)
    print(m3.to_summary_text())
