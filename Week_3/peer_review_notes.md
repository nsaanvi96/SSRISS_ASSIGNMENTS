# Week 3 Peer Review: Mayank's JNU Central Aggregator

**Reviewer:** Saanvi (SSRISS Intern – IISER Pune / IIMA Aggregator)  
**Author:** Mayank (SSRISS Intern – JNU Monitor)  
**Target:** Jawaharlal Nehru University (JNU)  
**Target URL:** https://www.jnu.ac.in/jnuevents and https://www.jnu.ac.in/events-archive  
**Repository:** `SSRISS-main/week_3`  
**Date:** October 2026

## 1. Overview

For the Week 3 peer review, I reviewed Mayank's central aggregator implementation for JNU.

The review covers the code and documentation for all Week 3 assignments. I ran the complete test suite, and all 69 tests pass, which matches the figure stated in the README. I also ran the adapter on several cases that the existing tests do not cover: the Week 2 live snapshots (`jnuevents.html` and `events_archive_page0.html`), an empty page, a page with changed markup, an item disappearing between runs and an item changing between runs.

The review addresses all 10 questions from Section 11 of the Week 3 syllabus, followed by five technical comments on the implementation.

## 2. Review Against the 10 Syllabus Questions

### Question 1: Is the target genuinely high-yield?

**Assessment: Yes**

The JNU events page is a strong choice for a central aggregator. A single request to `/jnuevents` surfaces events from many schools and centres, including SCIS, SIS, CSAS, ZHCES and SoE. Running the discovery adapter on the Week 2 snapshots returned 13 items from the current page and 29 from archive page 0.

The candidate matrix also gives a clear reason for ranking the notices page as the backup target: most of its rows link to PDFs and very few have detail pages.

### Question 2: Is the scope clearly bounded?

**Assessment: Mostly yes**

The source configuration restricts crawling to `www.jnu.ac.in` with the allowed prefixes `/node`, `/jnuevents` and `/events-archive`. It also excludes paths such as `/login`, `/user`, `/admin`, `/search` and `/calendar`, rejects binary file extensions, and sets `allow_external=False`. `scope_cases.md` documents the standard cases.

Two edge cases remain:

- Prefix matching uses a plain `startswith`. As a result, `/node` also permits `/nodes-archive`, and the `/user` exclusion also blocks `/users-guide`. Matching on a path boundary would resolve this.
- A URL with an explicit port, such as `https://www.jnu.ac.in:443/node/5`, fails the hostname check because the port is part of the network location.

### Question 3: Could pagination continue indefinitely?

**Assessment: No, but only because pagination is not implemented**

`max_pages: 3` appears in the configuration, but a search of the whole `week_3` directory shows that it is never read by any code. It is referenced only in a docstring and in the configuration itself. The `run()` method accepts a single HTML string and does not follow `?page=N` links.

`max_items` is enforced. However, `items_discovered` counts all in-scope records found before the ceiling is applied, so that metric can exceed the number of items actually processed.

The risk of an unbounded pagination loop is therefore untested rather than handled.

### Question 4: Are feeds and sitemaps used for discovery rather than treated as complete data?

**Assessment: Yes, at the adapter level**

The HTML, RSS and sitemap adapters all return the same record shape and produce only a URL, title and timestamp. Event details are meant to be extracted later.

It should be noted that `run()` calls only `discover_from_html`. Feed and sitemap discovery are tested independently but are not part of the end-to-end run.

### Question 5: Are item URLs canonicalized consistently?

**Assessment: Partly**

The canonicalization logic lowercases the scheme and hostname, removes fragments, strips `utm_*`, `fbclid` and `gclid`, removes trailing slashes and maps `jnu.ac.in` to `www.jnu.ac.in`.

Testing showed that some variants of the same page still produce different canonical URLs. These are `?ref=home`, differing query parameter order, and `http` versus `https`. They are described in Comment 3.

### Question 6: Does the extractor handle missing fields without crashing?

**Assessment: Yes**

Optional fields such as affiliation resolve to `None`, and titles without a speaker produce empty lists. An empty string and a page containing no event rows were both processed without an exception.

### Question 7: Are extracted speakers and organizations supported by source text?

**Assessment: Partly (see Comment 1)**

Each extracted entity stores a `source_text` value, so it can be traced back to the text that produced it. However, in the adapter the text passed to the extractor consists only of the title and a date line. The explicit "Speaker:" and "Organized by:" patterns therefore never run in the actual pipeline, and all entities come from the title-based fallback expressions, some of which over-extract.

### Question 8: Does entity resolution avoid merging uncertain identities?

**Assessment: Mostly yes, with one false-merge case for organizations (see Comment 5)**

For people, the logic in `entity_matcher.py` is conservative. `A. Rao` against `Prof. Ananya Rao` and `Ananya R.` against `Ananya Rao` are both classified as requiring review, and names with different first names are not matched. `_normalize_person` strips only a single leading honorific, so `Prof. Dr. X Rao` does not match `X Rao`. This results in a false split, which is the safer outcome.

For organizations, a short bracketed word is stripped before the names are compared. This produces automatic matches between organizations that should stay separate (Comment 5).

The matcher is not currently called from the adapter, so it functions as a standalone policy.

### Question 9: Can the logs distinguish between no new events and a broken parser?

**Assessment: Partly (see Comment 2)**

The two cases shown in the demonstration work as intended. A run in which everything is unchanged is reported as HEALTHY, and a page with no matching rows is reported as CRITICAL. However, a completely empty fetch is reported only as a NOTICE rather than as a critical failure.

### Question 10: Can the adapter run repeatedly without creating duplicate records?

**Assessment: Yes for unchanged items, no for changed items (see Comment 4)**

Two consecutive runs on the same page produce 6 new items followed by 6 unchanged items, with no duplicate rows. An item that disappears from the listing keeps its stored row. When an item changes, however, the stored data is not updated to match.

## 3. Technical Comments and Recommendations

### Comment 1: Entity extraction uses only the title and no detail page is fetched

In `central_aggregator_adapter.py`, the extractor receives the following input:

```python
"raw_text": f"Title: {rec['discovered_title']}\nDate: {rec.get('source_timestamp') or ''}"
```

This means the explicit-field extraction from Assignment 5 does not run in the real pipeline, and the FETCH + PARSE stage shown in the README architecture is not present in the code. The Week 2 snapshots, such as `node_159898390.html`, show that detail pages are available.

On real JNU titles the title-based approach performs well because the titles are formulaic, for example "SCIS organises a lecture by Dr. X". Twelve titles from `events_archive_page0` were tested and most were extracted correctly. However, the speaker pattern treats everything after any occurrence of "by" as a speaker, which produced incorrect results:

- "Workshop on Data Analysis organised by SCIS" returns speaker `SCIS`
- "Panel Discussion on Policy by Design" returns speaker `Design`
- "Annual Day celebrated by all" returns speaker `all`

In addition, "ZHCES, JNU in collaboration with Heidelberg University, Germany organises..." is stored as a single organization whose name is the whole phrase, although it refers to more than one organization.

I recommend fetching the detail page and applying the existing line-based extractor to its body, keeping the title patterns only as a fallback. If the title is used, the speaker pattern should apply only after a trigger such as "lecture by", "seminar by" or "talk by".

### Comment 2: Some health metrics are hardcoded and two README claims are not supported by the adapter

- `http_status` is set to 200 when the HTML string is non-empty and 500 otherwise, and `pages_fetched` is set to 1 or 0. These are not measured values because the adapter does not perform a fetch.
- When an empty page is supplied, `pages_fetched` is 0, so `diagnose_health()` bypasses the CRITICAL condition and returns "NOTICE: Run complete with zero new records". A failed fetch is the case that most needs to be reported clearly.
- The README states that listing disappearance is tagged `not_seen_this_run`. `incremental_store.py` supports this, but the adapter does not use it. The adapter builds `current_run_urls` without reading it and maintains its own `item_hashes` table. When a row was removed between runs, the summary reported 5 unchanged items and did not mention the missing one. The stored row was correctly retained, but the absence is not visible in the run summary.

I suggest adding `not_seen_this_run` to `RunMetrics`, computed from `current_run_urls` against `item_hashes`, and treating `pages_fetched == 0` or a non-200 status as CRITICAL.

### Comment 3: Canonicalization gaps can create duplicate records

`DEFAULT_JNU_CONFIG` sets `ignored_query_params` to a list of five parameters, which replaces the longer default list in `scope_filter.py`. As a result, `/node/5?ref=home` remains distinct from `/node/5`. The following variants of the same page also produce different canonical URLs:

- `?a=1&b=2` and `?b=2&a=1`
- `http://` and `https://`
- an explicit `:443` port, which also fails the hostname check

I suggest sorting the query parameters, forcing `https` for the allowed host, removing default ports, and merging the configured list with the defaults instead of replacing them. Adding a test for each case in `test_scope_filter.py` would prevent regressions.

### Comment 4: A changed item is detected but the stored record is not updated

A speaker name in the fixture was changed between two runs. The run correctly reported `changed=1`, but afterwards:

- the `items` row retained the old title ("...by Dr. Divya P. Kumar")
- the old person link remained and a new one was added, so the event was linked to both speakers (people increased from 4 to 5 and `item_people` from 4 to 5)

Change detection therefore works at the hash level, but the relational data becomes stale and accumulates outdated links. When the status is CHANGED, the item row should be updated and that item's `item_people` and `item_organizations` links should be replaced within a single transaction. This is important because queries such as "which events mention person X" would otherwise return incorrect results over time.

### Comment 5: Bracketed words in organization names can cause false merges

In `_normalize_org`, any trailing bracketed text of six letters or fewer that is purely alphabetic is treated as an acronym and removed before comparison:

```python
if len(inner) <= 6 and inner.isalpha():
    extracted_acronym = inner.lower()
    clean = clean[:paren_match.start()].strip()
```

The text is removed without checking that it is actually an acronym of the name. After removal, the remaining names are compared directly, and the following pairs all came back as `safe automatic match`:

- `Department of Economics (Pune)` and `Department of Economics`
- `Centre for Research (East)` and `Centre for Research`
- `Department of Economics (Pune)` and `Department of Economics (Delhi)`

The last pair is two different departments, so this is a false merge, which the policy document says should be avoided. I suggest keeping the bracketed text only when it equals the initials of the remaining name (for example `Centre for Policy Research (CPR)`), and leaving it in the name otherwise so that such pairs fall through to review or no match.

## 4. Overall Conclusion

Overall, Mayank's submission is well organised and all 69 tests pass. The individual components from Assignments 0 to 9, namely the scope filter, discovery adapters, hashing, router, matcher and metrics, are each reasonable on their own.

The main gaps are in the integration stage. The adapter does not fetch detail pages or follow pagination, extraction depends on titles only, `max_pages` is never used, and changed items leave stale rows and links. In addition, no module in `week_3` imports from the Week 2 framework (fetch, storage, scheduler and logging), which Definition of Done point 12 requires.

My suggested order of priority is: (1) update the stored item and its links when an item is CHANGED, (2) add detail-page fetching and tighten the title patterns, (3) report an empty fetch as CRITICAL and include `not_seen_this_run` in the metrics, (4) close the canonicalization gaps, and (5) tighten the acronym handling in the organization matcher.
