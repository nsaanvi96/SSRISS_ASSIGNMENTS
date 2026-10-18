# Week 3 Integration Assignment: High-Yield Central Aggregator

**Institution:** Indian Institute of Management Ahmedabad (IIMA)  
**Primary Domain:** `www.iima.ac.in`  
**Aggregator Surface:** IIMA Central Events, Seminars, and Public Research Lectures

---

## 1. Executive Summary & Pipeline Architecture

Week 3 integrates all scraping, discovery, incremental tracking, content classification, and relational entity extraction capabilities developed throughout the week into a single robust pipeline:

```text
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
DATABASE (SQLite)
     ↓
HEALTH / COVERAGE SUMMARY
```

### End-to-End Pipeline Stages

1. **SOURCE CONFIG:** Defines base URL, allowed paths, denylist rules, rate-limiting, and item discovery ceiling (bounded crawl: max 30 items).
2. **SCHEDULED RUN:** Orchestrates the ingestion cycle with start/finish timestamps and structured audit logging.
3. **DISCOVERY ADAPTER:** Ingests HTML listings, RSS 2.0 feeds, and XML sitemaps to discover candidate URLs with publication dates and raw titles.
4. **SCOPE CONTROL:** Enforces canonicalization, subdomain bounding, query/anchor stripping, and anti-trapping rules (rejecting login, admin, calendar navigation loops, and binary downloads).
5. **NEW / CHANGED ITEM CANDIDATES:** Computes SHA-256 content hashes of normalized payloads; compares against database history to classify items as `NEW`, `CHANGED`, or `UNCHANGED`. Disappearance from current listing is tracked via `last_seen_at` without premature deletion claims.
6. **FETCH + PARSE:** Extracts title, date, venue, abstract, speaker block, and organizer block from structured HTML cards.
7. **NORMALIZE:** Strips leading/trailing whitespace, converts relative URLs to absolute HTTPS links, standardizes ISO-8601 dates.
8. **EXPLICIT ENTITY EXTRACTION:** Conservatively parses person names (speakers, chairs, panelists) and organizations (departments, chairs, partner institutes) while strictly preserving verbatim `source_text` provenance.
9. **ITEM + ENTITY RELATIONSHIPS:** Maps events, people, and organizations into normalized relational tables (`items`, `people`, `organizations`, `item_people`, `item_organizations`) with composite unique keys.
10. **DATABASE:** Atomically commits relational data using SQLite foreign-key constraints and ACID transactions.
11. **HEALTH / COVERAGE SUMMARY:** Computes ingestion metrics (items discovered, parsed, new, changed, unchanged, failed) and coverage percentages (dates, speakers, organizations), diagnosing operational status (Healthy vs Broken Parser vs Inactive Source).

---

## 2. Deliverables Matrix (All 16 Requirements)

| # | Required Deliverable | Primary File Location(s) | Description |
|---|----------------------|--------------------------|-------------|
| **1** | **Aggregator candidate matrix** | [`assignments/00_candidates/iima_aggregators.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/00_candidates/iima_aggregators.md) | Evaluates 4 candidate institutional aggregator surfaces (IIMA, IISER Pune, JNU, CPR) across yield, structure, updates, and accessibility. |
| **2** | **Chosen central source rationale** | [`assignments/00_candidates/iima_aggregators.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/00_candidates/iima_aggregators.md) | Explicit justification for selecting IIMA (`www.iima.ac.in/events`) as the primary central aggregator. |
| **3** | **Feed/sitemap/listing discovery exercise** | [`assignments/01_discovery/findings.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/01_discovery/findings.md)<br>[`assignments/01_discovery/unified_discovery.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/01_discovery/unified_discovery.py) | Comparative analysis of RSS feeds, XML sitemaps, and HTML event listings with automated extractor. |
| **4** | **URL scope rules** | [`assignments/02_scope/scope_cases.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/02_scope/scope_cases.md)<br>[`assignments/02_scope/scope_filter.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/02_scope/scope_filter.py) | Exact regex patterns, host boundary validation, path allowlists/denylists, tracking-parameter stripping, and trap guards. |
| **5** | **Discovery adapter** | [`assignments/03_interface/aggregator_discovery.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/03_interface/aggregator_discovery.py) | Abstract interface `BaseDiscoveryAdapter` and concrete `UnifiedAggregatorDiscovery` yielding normalized `DiscoveredItem` records. |
| **6** | **Incremental run/change detection** | [`assignments/04_incremental/run_state_notes.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/04_incremental/run_state_notes.md)<br>[`assignments/04_incremental/incremental_store.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/04_incremental/incremental_store.py) | State transitions (`NEW`, `UNCHANGED`, `CHANGED`, `NO_LONGER_VISIBLE`), `first_seen_at`, `last_seen_at`, and SHA-256 content hashing. |
| **7** | **Content router** | [`assignments/08_routing/router_notes.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/08_routing/router_notes.md)<br>[`assignments/08_routing/content_router.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/08_routing/content_router.py) | Structural classification into `event`, `announcement`, `faculty`, `pdf_document`, `external_link`, and `unknown` without political/topic bias. |
| **8** | **Detail parser where relevant** | [`assignments/10_adapter/central_aggregator_adapter.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/10_adapter/central_aggregator_adapter.py) | Dedicated event item parsing logic extracting title, date, venue, abstract, speaker, and organizer sections. |
| **9** | **Person entity extraction** | [`assignments/05_extraction/extraction_notes.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/05_extraction/extraction_notes.md)<br>[`assignments/05_extraction/entity_extractor.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/05_extraction/entity_extractor.py) | Parses names, roles (speaker, chair, panelist), and affiliations strictly from explicit text with verbatim provenance. |
| **10** | **Organization entity extraction** | [`assignments/05_extraction/extraction_notes.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/05_extraction/extraction_notes.md)<br>[`assignments/05_extraction/entity_extractor.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/05_extraction/entity_extractor.py) | Extracts departments, centers, chairs, and partner institutes without inferring implicit affiliations. |
| **11** | **Entity relationship schema** | [`assignments/06_entities/entity_schema.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/06_entities/entity_schema.md)<br>[`assignments/06_entities/entity_relational_store.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/06_entities/entity_relational_store.py) | SQLite relational model (`items`, `people`, `organizations`, `item_people`, `item_organizations`) with role and provenance attributes. |
| **12** | **Tests and fixtures** | All `assignments/*/test_*.py` files & `fixtures/` directories | 10 independent test suites with offline HTML/RSS/JSON fixtures covering 160+ test cases. |
| **13** | **Logs** | [`assignments/10_adapter/aggregator.log`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/10_adapter/aggregator.log)<br>[`assignments/12_integration/integration_run.log`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/12_integration/integration_run.log) | Structured audit log records with millisecond timestamps, run phases, scope decisions, and extraction counts. |
| **14** | **Run metrics** | [`assignments/09_metrics/run_summary_notes.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/09_metrics/run_summary_notes.md)<br>[`assignments/09_metrics/run_summary.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/09_metrics/run_summary.py) | Structured run health summary distinguishing healthy steady-state runs from parser failures. |
| **15** | **README** | [`Week_3/README.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/README.md) | This complete integration guide, architecture breakdown, and execution documentation. |
| **16** | **Peer-review notes** | [`Week_3/peer_review_notes.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/peer_review_notes.md) | Architectural critique, failure-mode analysis, design trade-offs, and rubric verification checklist. |

---

## 3. Quickstart & Verification Commands

### Run End-to-End Integration Demonstration
Execute the two-phase integration run (initial ingestion followed by incremental re-crawl):
```bash
python Week_3/assignments/12_integration/run_integration.py
```

### Run Entire Week 3 Automated Test Suite
Run all unit and integration test suites using pytest:
```bash
python -m pytest Week_3/assignments/ -v
```

---

## 4. Key Architectural Decisions & Safeguards

1. **Conservative Entity Resolution (False Split Over False Merge):**
   - Weak similarity (e.g., "A. Rao" vs "Prof. Ananya Rao") is never merged automatically into an authoritative identity claim.
   - Punctuation, honorific variants ("Dr.", "Prof."), and case insensitive matching are permitted for deduplication, but surname/initial overlaps are categorized as `REVIEW_REQUIRED`.

2. **Listing Disappearance != Deletion:**
   - If an event is no longer on the front page listing, it is marked with an updated `last_seen_at` without deleting the database record, avoiding recrawl data loss.

3. **Content Classification Before Parsing:**
   - Unsupported or mixed items (PDF downloads, external registration links, faculty profiles) are recorded as `pdf_document`, `external_link`, or `unknown` rather than forced into an `event` schema.

4. **Parser Failure Visibility:**
   - If a source returns items but 0 parse successfully, the run summary classifies the status as `CRITICAL: Broken parser suspected` rather than reporting zero new items.
