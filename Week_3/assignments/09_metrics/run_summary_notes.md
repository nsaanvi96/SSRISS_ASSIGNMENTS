# Assignment 9 — Source Health and Coverage Metrics

## Overview

Before introducing AI or downstream analysis, the collection layer must answer a foundational engineering question:

> **Did the monitor actually work?**

Without collection-quality metrics, an empty run is ambiguous: Did the publisher simply not post anything new today, or did the website redesign its HTML structure and break our CSS selectors?

Assignment 9 introduces a structured **Run Summary & Metrics Collector** ([run_summary.py](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/09_metrics/run_summary.py)) that produces standardized per-run health records, persists them to SQLite and log files, and automatically diagnoses the operational health of the aggregator.

---

## 1. Canonical Per-Run Summary Format

At the completion of each aggregator execution, the system emits a standardized key-value summary:

```text
SOURCE: iima_events
PAGES_FETCHED: 1
ITEMS_DISCOVERED: 4
ITEMS_PARSED: 4
NEW: 4
CHANGED: 0
UNCHANGED: 0
FAILED: 0
PEOPLE_EXTRACTED: 4
ORGANIZATIONS_EXTRACTED: 4
PCT_WITH_DATE: 100.0%
PCT_WITH_SPEAKER: 100.0%
PCT_WITH_ORGANIZATION: 100.0%
STATUS: HEALTHY: New or changed content collected
DIAGNOSIS: Healthy: Processed 4 new and 0 updated items.
```

---

## 2. Checkpoint: Distinguishing "No New Content" vs. "Broken Parser"

> **Checkpoint**: A reviewer should be able to distinguish:
> - **Source had no new content**
> from:
> - **Parser broke and returned zero content**

Our diagnostic health engine ([diagnose_health](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/09_metrics/run_summary.py#L90)) applies deterministic boolean rules to evaluate these states:

| Metric Indicator | Scenario A: Steady State (No New Content) | Scenario B: Broken Parser (Scraper Failure) |
|---|---|---|
| **`PAGES_FETCHED`** | `>= 1` (HTTP 200) | `>= 1` (HTTP 200) |
| **`ITEMS_DISCOVERED`** | `> 0` (e.g. 20 items found on page) | **`0`** (selector matched nothing) |
| **`ITEMS_PARSED`** | `> 0` (e.g. 20 items successfully parsed) | **`0`** (zero records created) |
| **`NEW`** | **`0`** (all URLs already in DB) | **`0`** |
| **`UNCHANGED`** | **`> 0`** (hash matches stored rows) | **`0`** |
| **`FAILED`** | **`0`** | **`>= 1`** (selector failure flagged) |
| **`STATUS`** | `HEALTHY: Source had no new content (all unchanged)` | `FAILURE: Parser broke (0 items extracted from fetched page)` |
| **Reviewer Action** | **None**: The aggregator is healthy and doing its job. | **Alert**: CSS selectors or DOM hierarchy broke; scraper needs updating. |

---

## 3. Deliberate Breakage Experiment

To prove that metrics make failures immediately visible, we tested against two local fixtures:

### Run 1: Valid Fixture ([valid_events.html](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/09_metrics/fixtures/valid_events.html))
```text
SOURCE: iima_events
PAGES_FETCHED: 1
ITEMS_DISCOVERED: 4
ITEMS_PARSED: 4
NEW: 4
CHANGED: 0
UNCHANGED: 0
FAILED: 0
PEOPLE_EXTRACTED: 4
ORGANIZATIONS_EXTRACTED: 4
PCT_WITH_DATE: 100.0%
PCT_WITH_SPEAKER: 100.0%
PCT_WITH_ORGANIZATION: 100.0%
STATUS: HEALTHY: New or changed content collected
DIAGNOSIS: Healthy: Processed 4 new and 0 updated items.
```

### Run 2: Second Run on Valid Fixture (Steady State Simulation)
```text
SOURCE: iima_events
PAGES_FETCHED: 1
ITEMS_DISCOVERED: 4
ITEMS_PARSED: 4
NEW: 0
CHANGED: 0
UNCHANGED: 4
FAILED: 0
PEOPLE_EXTRACTED: 4
ORGANIZATIONS_EXTRACTED: 4
PCT_WITH_DATE: 100.0%
PCT_WITH_SPEAKER: 100.0%
PCT_WITH_ORGANIZATION: 100.0%
STATUS: HEALTHY: Source had no new content (all unchanged)
DIAGNOSIS: Healthy: Source active (4 items visible); no new or updated items since previous run.
```

### Run 3: Deliberately Broken Fixture ([broken_events.html](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/09_metrics/fixtures/broken_events.html))
In this fixture, the site was simulated to have undergone a redesign: `.event-card` containers were removed and replaced with generic unstructured divs without anchor tags.
```text
SOURCE: iima_events
PAGES_FETCHED: 1
ITEMS_DISCOVERED: 0
ITEMS_PARSED: 0
NEW: 0
CHANGED: 0
UNCHANGED: 0
FAILED: 1
PEOPLE_EXTRACTED: 0
ORGANIZATIONS_EXTRACTED: 0
PCT_WITH_DATE: 0.0%
PCT_WITH_SPEAKER: 0.0%
PCT_WITH_ORGANIZATION: 0.0%
STATUS: FAILURE: Parser broke (0 items extracted from fetched page)
DIAGNOSIS: CRITICAL: Page fetched successfully, but parser returned 0 items. Site markup or CSS selectors likely changed.
```

The metrics clearly surface the breakage:
- `ITEMS_DISCOVERED: 0` despite `PAGES_FETCHED: 1`.
- `FAILED: 1`.
- `STATUS: FAILURE: Parser broke`.

---

## 4. Persistence Architecture

Every run summary can be stored simultaneously in two persistence targets:

1. **SQLite (`run_metrics` table)**:
   - Stores all integer counters, coverage percentages, and health statuses.
   - Allows monitoring dashboards to query historical scraper health (e.g. `SELECT AVG(pct_with_date), SUM(failed) FROM run_metrics WHERE source='iima_events'`).
2. **Text Log (`run_summary.log`)**:
   - Human-readable block logs appended chronologically with ISO UTC timestamps.
