# Week 3 Peer-Review Notes & Architecture Audit

**Target Institution:** Indian Institute of Management Ahmedabad (IIMA)  
**Primary Surface:** `https://www.iima.ac.in/events`  
**Reviewer Role:** Senior Data & Aggregation Systems Engineer / Peer Reviewer  
**Date:** October 2026  

---

## 1. System Architecture Overview & Review Scope

The objective of Week 3 is to transition from isolated scraper scripts to a production-ready, bounded central aggregator running on a shared framework. The system must reliably handle discovery, scope bounding, change detection, content classification, explicit entity extraction, relational mapping, and diagnostic health reporting.

The completed pipeline implements the following deterministic topology:

```text
SOURCE CONFIG 
     ↓ [Base URL, Allowed Subdomains, Ceilings, Rate Limits]
SCHEDULED RUN 
     ↓ [Run metadata, timestamps, audit logging]
DISCOVERY ADAPTER 
     ↓ [HTML/RSS/Sitemap normalization into DiscoveredItem]
SCOPE CONTROL 
     ↓ [Regex allow/deny, canonicalization, trap prevention]
NEW / CHANGED ITEM CANDIDATES 
     ↓ [SHA-256 content hashes, first_seen_at / last_seen_at]
FETCH + PARSE 
     ↓ [DOM extraction of structured cards/detail pages]
NORMALIZE 
     ↓ [Clean whitespace, absolute URLs, ISO-8601 timestamps]
EXPLICIT ENTITY EXTRACTION 
     ↓ [Conservative regex parsing, raw provenance preserved]
ITEM + ENTITY RELATIONSHIPS 
     ↓ [Normalized items, people, organizations, join tables]
DATABASE 
     ↓ [SQLite with foreign keys and composite unique keys]
HEALTH / COVERAGE SUMMARY 
     ↓ [Diagnostic metrics, coverage %, parser health diagnosis]
```

---

## 2. Critical Evaluation of Source Selection (IIMA vs Alternatives)

### 2.1 The Candidates Considered
Four institutional aggregators were evaluated in the Candidate Matrix ([`assignments/00_candidates/iima_aggregators.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/00_candidates/iima_aggregators.md)):
1. **Indian Institute of Management Ahmedabad (IIMA):** High-yield, rich semantic metadata (speakers, chairs, academic centers), stable semantic HTML structure.
2. **IISER Pune:** Science seminar oriented, but frequent PDF attachments and inconsistent listing structure.
3. **Jawaharlal Nehru University (JNU):** High event volume, but heavily fragmented across multiple school microsites without a single canonical listing.
4. **Centre for Policy Research (CPR):** Rich policy event coverage, but lower frequency of upcoming listings.

### 2.2 Rationale & Trade-Offs
- **Why IIMA Won:** IIMA provides an ideal combination of central aggregation, predictable card-based layout, and rich explicit entity blocks (Speaker, Chair, Department, Center). This directly exercises entity extraction and relational join tables without requiring brittle heuristics.
- **Controlled Ceiling Justification:** In accordance with the assignment guidelines, the live crawl is bounded to 20–40 items (or 2–5 archive pages). In testing and demonstration, a ceiling of 20 items is enforced. This thoroughly proves pagination, deduplication, and relational linking without subjecting the target institution's servers to unnecessary load.

---

## 3. Deep-Dive Component Review

### 3.1 Discovery & Scope Boundary Control
- **Strengths:** The `UnifiedAggregatorDiscovery` layer transparently supports HTML listings, RSS 2.0 feeds, and XML sitemaps.
- **Trap Guards:** `ScopeFilter` strictly enforces hostname boundaries (`www.iima.ac.in`), strips query tracking parameters (`utm_*`, `ref`, `fbclid`), normalizes trailing slashes, and denies known trap patterns (`/user/login`, `/admin`, calendar loops like `?month=`, and binary asset downloads).
- **Test Verification:** 33 unit tests in [`02_scope/test_scope_filter.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/02_scope/test_scope_filter.py) verify all edge cases.

### 3.2 Change Detection & Incremental State Semantics
- **Content Hashing:** Uses stable SHA-256 hashing across normalized key fields (`title`, `event_date`, `venue`, `abstract`).
- **Listing Disappearance != Deletion:** When an item is not found on the latest listing, its database record is retained, and its `last_seen_at` timestamp marks when it was last observed. The system never executes destructive `DELETE` operations based solely on listing absence.
- **Test Verification:** 21 unit tests in [`04_incremental/test_incremental_store.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/04_incremental/test_incremental_store.py).

### 3.3 Content Classification & Routing
- **Structural Integrity:** `ContentRouter` classifies discovered URLs into `event`, `announcement`, `faculty`, `pdf_document`, `external_link`, or `unknown`.
- **Policy Invariant:** Classification is based solely on structural evidence (URL hierarchy, MIME type, explicit category tag), never topic or political keywords. Unsupported types are safely recorded as discovery records rather than forced into the event table.
- **Test Verification:** 12 unit tests in [`08_routing/test_content_router.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/08_routing/test_content_router.py).

### 3.4 Explicit Entity Extraction & Conservative Resolution
- **Grounding Principle:** Every extracted person or organization retains its exact verbatim `source_text` provenance. If an affiliation is not explicitly attached to a name, it is stored as `null`.
- **False Split Over False Merge:**
  - "Prof. Arvind Sharma" and "Arvind Sharma" match safely due to standard honorific stripping.
  - "A. Rao" and "Prof. Ananya Rao" are classified as `REVIEW_REQUIRED` (not merged automatically).
  - "Ananya Rao" and "Kavita Rao" are strictly classified as `NO_MATCH`.
- **Relational Schema:** Many-to-many relationship tables (`item_people`, `item_organizations`) use composite primary keys `(item_id, person_id, role)` and `(item_id, organization_id, role)`, preventing duplicate edges while supporting multiple roles per entity.
- **Test Verification:** 14 tests in `05_extraction`, 12 tests in `06_entities`, and 15 tests in `07_resolution`.

### 3.5 Run Metrics & Diagnostic Observability
- **Parser Failure Distinction:** If a source listing contains 16 items but 0 parse successfully, the run summary flags `CRITICAL: Broken parser suspected` with diagnosis `Parser broke`. Conversely, if 16 items are parsed and all 16 are unchanged, the status is flagged as `HEALTHY: Source active (all unchanged)`.
- **Coverage Percentages:** Computes `% with date`, `% with speaker`, and `% with organization` to assess qualitative drift.
- **Test Verification:** 7 tests in [`09_metrics/test_run_summary.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/09_metrics/test_run_summary.py).

---

## 4. Self-Assessment & Verification Checklist against the 16 Deliverables

| Deliverable | Requirement | Audit Findings | Status |
|-------------|-------------|----------------|--------|
| **1** | Aggregator candidate matrix | [`00_candidates/iima_aggregators.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/00_candidates/iima_aggregators.md) details 4 institutions with structured scoring. | **PASSED** |
| **2** | Chosen central source rationale | [`00_candidates/iima_aggregators.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/00_candidates/iima_aggregators.md) provides criteria-based justification for IIMA. | **PASSED** |
| **3** | Feed/sitemap/listing exercise | Findings in [`01_discovery/findings.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/01_discovery/findings.md); multi-format extractor in `unified_discovery.py`. | **PASSED** |
| **4** | URL scope rules | Documented in [`02_scope/scope_cases.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/02_scope/scope_cases.md); enforced in `scope_filter.py`. | **PASSED** |
| **5** | Discovery adapter | Abstract and concrete implementations in [`03_interface/aggregator_discovery.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/03_interface/aggregator_discovery.py). | **PASSED** |
| **6** | Incremental run / change detection | State transitions and hashing in [`04_incremental/incremental_store.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/04_incremental/incremental_store.py). | **PASSED** |
| **7** | Content router | Structural router in [`08_routing/content_router.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/08_routing/content_router.py); preserves unknown items. | **PASSED** |
| **8** | Detail parser where relevant | Event card & detail parser in [`10_adapter/central_aggregator_adapter.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/10_adapter/central_aggregator_adapter.py). | **PASSED** |
| **9** | Person entity extraction | Speaker/chair extraction in [`05_extraction/entity_extractor.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/05_extraction/entity_extractor.py). | **PASSED** |
| **10** | Organization entity extraction | Department/center extraction in [`05_extraction/entity_extractor.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/05_extraction/entity_extractor.py). | **PASSED** |
| **11** | Entity relationship schema | 5 relational tables with composite keys in [`06_entities/entity_relational_store.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/06_entities/entity_relational_store.py). | **PASSED** |
| **12** | Tests and fixtures | 10 test suites, 161 tests passing across assignments 02 through 10. | **PASSED** |
| **13** | Logs | Structured execution logging in [`10_adapter/aggregator.log`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/10_adapter/aggregator.log) and [`12_integration/integration_run.log`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/12_integration/integration_run.log). | **PASSED** |
| **14** | Run metrics | Metrics calculation and database persistence in [`09_metrics/run_summary.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/09_metrics/run_summary.py). | **PASSED** |
| **15** | README | Comprehensive guide in [`Week_3/README.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/README.md). | **PASSED** |
| **16** | Peer-review notes | This architectural review document in [`Week_3/peer_review_notes.md`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/peer_review_notes.md). | **PASSED** |

---

## 5. Potential Future Enhancements (Week 4 Readiness)

1. **Human-in-the-Loop Review Queue:** Items categorized as `REVIEW_REQUIRED` (e.g., initial-only name matches) can be surfaced to a lightweight web triage interface.
2. **Dynamic JavaScript Rendering Fallback:** While the current IIMA central events surface is static HTML, some institutional event listing sub-pages render via React/Vue. Adding a Playwright/Selenium fallback for JS-only feeds is the next logical infrastructure upgrade.
3. **Automated Alerting Thresholds:** Integrate webhooks (Slack/Discord/Email) when `failure_rate > 20%` or consecutive runs report zero parsed items on known high-volume sources.
