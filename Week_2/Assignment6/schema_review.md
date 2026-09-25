# Assignment 6 — Schema Review
**Source:** IISER Pune Events (`/news?category=events`)  
**Records inspected:** 8 from saved fixture (Assignment 5B output); live page as of 25 Sep 2026 contains 15 records

---

## Field-by-Field Review

| Field | Present on how many records? | Raw source representation | Normalized representation | Required or optional? | Source-specific or generic? |
|---|---|---|---|---|---|
| `source_name` | 8 / 8 | Not on page — set in scraper config | `"iiserpune_events"` (string constant) | Required | Source-specific (value); Generic (field) |
| `source_url` | 8 / 8 | Not on page — set in scraper config | `"https://www.iiserpune.ac.in/news?category=events"` | Required | Source-specific (value); Generic (field) |
| `item_url` | 8 / 8 | Relative href on `<a>` inside `li.news-card` | Absolute URL via `urljoin` e.g. `https://www.iiserpune.ac.in/news/post/.../1691` | Required | Generic |
| `item_type` | 8 / 8 | Not on page — hardcoded from source config | `"event"` | Required | Source-specific (value); Generic (field) |
| `title` | 8 / 8 | Plain text inside the anchor tag, e.g. `"Bridging Science and Enterprise: Kiran Mazumdar-Shaw's visit to IISER Pune"` | Same string, `.strip()`-cleaned | Required | Generic |
| `event_start` | 8 / 8 | `"Posted on Jun 15, 2026"` (plain text, no `datetime` attribute) | `"2026-06-15T00:00:00+05:30"` — date only, time assumed midnight IST | Optional | Generic |
| `event_end` | 0 / 8 | Not present on listing page | `null` | Optional | Generic |
| `location` | 0 / 8 | Not present on listing page | `null` | Optional | Generic |
| `speakers` | 0 / 8 | Not present on listing page | `[]` | Optional | Generic |
| `organizations` | 0 / 8 | Not present on listing page | `[]` | Optional | Generic |
| `description` | 0 / 8 | Not present as a distinct field; partial info inside `raw_text` | `null` (not extracted yet; would require detail-page fetch) | Optional | Generic |
| `raw_text` | 8 / 8 | Full visible text of the `li.news-card` element, concatenated, e.g. `"Events Bridging Science and Enterprise: ... Biocon Limited, visited IISER Pune..."` | Same string, whitespace-normalized | Required | Generic |
| `fetched_at` | 8 / 8 | Not on page — set at fetch time | ISO 8601 UTC string e.g. `"2026-09-08T07:56:35.867954+00:00"` | Required | Generic |
| `http_status` | 8 / 8 | HTTP response status code from `requests` | Integer `200` | Required | Generic |
| `first_seen_at` | 0 / 8 | Not on page — set by storage layer on first insert | Not yet implemented in output schema (exists in DB) | Required (for monitoring) | Generic |
| `last_seen_at` | 0 / 8 | Not on page — updated by storage layer on upsert | Not yet implemented in output schema (exists in DB) | Required (for monitoring) | Generic |

---

## End-of-Review Questions

### 1. Which fields genuinely belong in the shared schema?

`source_name`, `source_url`, `item_url`, `item_type`, `title`, `event_start`, `event_end`, `location`, `speakers`, `organizations`, `description`, `raw_text`, `fetched_at`, `http_status`, `first_seen_at`, `last_seen_at` — all of these are generic and institution-independent. Every academic event source would need exactly this set.

### 2. Which fields should remain source-specific?

None of the *fields* are source-specific. The **values** of `source_name`, `source_url`, and `item_type` are source-specific constants set in the source config. The **parsing logic** for `event_start` is source-specific (IISER uses `"Posted on MMM DD, YYYY"` with no time component), but the field itself is shared.

### 3. Which values should be lists?

`speakers` and `organizations` — an event can have multiple speakers or co-organizing bodies, so these are correctly typed as lists even when empty. `research_areas` would also be a list in the faculty schema.

### 4. Which fields are identifiers?

`item_url` — used as the primary key in SQLite for deduplication. `source_url` identifies the listing surface the item was discovered from. Together they form the provenance chain.

### 5. Which fields represent provenance rather than content?

`source_name`, `source_url`, `fetched_at`, `http_status`, `first_seen_at`, `last_seen_at` — these describe *when and where* an item was found, not what the item says. They exist for auditing, change detection, and debugging, not for the end-user briefing.

---

## Notable Gaps in This Source

- **`event_start` has no time component** — the listing page only publishes the post date, not the actual event time. Midnight IST is assumed. This would need to be corrected by fetching detail pages.
- **`event_end`, `location`, `speakers`, `description`** are all absent from the listing page — all four would require detail-page enrichment (Assignment 5, Week 2).
- **`first_seen_at` / `last_seen_at`** live in the SQLite DB (set by `upsert_item`) but are not currently included in the `.jsonl` output. These should be added to the normalized output in Week 2.
- **`raw_text` includes noise** — the listing card text begins with category tags like `"Events"` or `"Events IISER Pune in News"` before the actual title and snippet. A future cleanup pass should strip these prefixes.
- **Multi-category tags** — some cards carry more than one `category-tag` anchor (e.g. one record has `Beyond the Campus`, `Events`, `New in Campus`, `Spotlight` simultaneously). The current scraper captures only the first tag or ignores them entirely. The `organizations` or a dedicated `categories` field (as a list) would be the right place to store these — not shoehorned into a scalar field.
