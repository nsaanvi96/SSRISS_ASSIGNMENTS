# Failure Examples — Logging Output

Each section shows what the log output looks like when a specific failure is triggered.
The stage where failure occurred is always identifiable without opening source code.

---

## Normal run (baseline)

```
2026-09-17T18:21:06  INFO      web_monitor.runner   START source=iiserpune_events
2026-09-17T18:21:06  INFO      web_monitor.storage  STORAGE db_ready path=.../data/iiserpune.db
2026-09-17T18:21:06  INFO      web_monitor.runner   FETCH using fixture path=.../sample_response.html status=200
2026-09-17T18:21:06  INFO      web_monitor.scraper  PARSE records=8
2026-09-17T18:21:06  INFO      web_monitor.runner   NORMALIZE records=8
2026-09-17T18:21:06  INFO      web_monitor.runner   STORE new=8 existing=0 changed=0
2026-09-17T18:21:06  INFO      web_monitor.runner   END source=iiserpune_events duration_ms=15
```

---

## Failure 1 — Invalid URL

**How triggered:** passed `"not-a-valid-url-at-all"` (no scheme) to `fetch()`.

**Stage:** FETCH

```
2026-09-17T18:21:11  ERROR  web_monitor.scraper  FETCH request_error url=not-a-valid-url-at-all duration_ms=1 error=Invalid URL 'not-a-valid-url-at-all': No scheme supplied. Perhaps you meant https://not-a-valid-url-at-all?
```

**What to look for:** `FETCH request_error` + `Invalid URL` in the error message.

---

## Failure 2 — Connection Failure

**How triggered:** passed a non-existent domain `https://this-domain-does-not-exist-9999.ac.in/events` to `fetch()`.

**Stage:** FETCH

```
2026-09-17T18:21:15  ERROR  web_monitor.scraper  FETCH connection_error url=https://this-domain-does-not-exist-9999.ac.in/events duration_ms=67 error=HTTPSConnectionPool(host='this-domain-does-not-exist-9999.ac.in', port=443): Max retries exceeded with url: /events (Caused by NameResolutionError(...Failed to resolve...))
```

**What to look for:** `FETCH connection_error` + `NameResolutionError` or `Max retries exceeded`.

---

## Failure 3 — Parser Receives Unexpected HTML Structure

**How triggered:** passed HTML with no `li.news-card` elements — completely different layout.

**Stage:** PARSE

```
2026-09-17T18:21:20  WARNING  web_monitor.scraper  PARSE no records found — page may be empty or structure changed
2026-09-17T18:21:20  INFO     web_monitor.scraper  PARSE records=0
```

**What to look for:** `PARSE no records found` warning. This is a WARNING (not ERROR) because the
page loaded fine — but zero records likely means the site's HTML structure changed and the
selectors need updating.

---

## Failure 4 — Empty Listing Page

**How triggered:** passed valid HTML with an empty `<ul class="news-list"></ul>` — no event cards.

**Stage:** PARSE

```
2026-09-17T18:21:25  WARNING  web_monitor.scraper  PARSE no records found — page may be empty or structure changed
2026-09-17T18:21:25  INFO     web_monitor.scraper  PARSE records=0
```

**What to look for:** Same WARNING as Failure 3. In practice, distinguish between these two cases
by checking whether the source recently had content — a consistently-zero page is a structure
change; a zero page during a known quiet period is genuine.

---

## Failure 5 — Database Write Problem

**How triggered:** called `upsert_item()` with a DB path pointing at `/proc/readonly.db`
(unwritable filesystem location).

**Stage:** STORE

```
2026-09-17T18:21:30  ERROR  web_monitor.storage  STORAGE upsert_failed item_url=https://test.com/event/1 error=unable to open database file
```

**What to look for:** `STORAGE upsert_failed` + the specific SQLite error message.
The item URL is always logged so you know exactly which record failed.

---

## Summary — How to identify the failure stage from logs alone

| Log pattern | Failure stage |
|---|---|
| `FETCH request_error` / `FETCH connection_error` / `FETCH timeout` / `FETCH http_error` | Fetch |
| `PARSE no records found` (WARNING) | Parse — empty page or selector mismatch |
| `NORMALIZE date_parse_failed` (WARNING) | Normalize — date format changed |
| `STORAGE upsert_failed` (ERROR) | Store — DB write error |
| `STAGE=fetch/parse/store ... error=` in runner | Runner caught an exception at that stage |
