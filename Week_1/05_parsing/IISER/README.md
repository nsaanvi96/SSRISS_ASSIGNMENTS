# Assignment 5 — Fixture Parser & IISER Pune Events Scraper

This covers both parts of Assignment 5: a parser built against a local fictional fixture (5A), and the first real extraction from IISER Pune's events listing (5B).

## Part 1 — Fixture Parser

**Files:** `fixture_parser.py`, `fixture.html`, `fixture_output.json`

`fixture.html` has 9 fictional event cards, structured as `.event-card` divs each containing a title/link, a date, and (usually) a speaker and location. One card — "Gender and Labor Markets" — deliberately has no speaker, so I could confirm the parser handles missing fields correctly instead of crashing.

`parse_events(html, base_url)` reads through each `.event-card`, pulls out the fields below, and returns a list of dicts:

- `title` — text of the `h2.title a` link
- `item_url` — the link's href, passed through `urljoin` so relative paths become absolute. One card already has a full external URL, and that one just passes through unchanged.
- `date_raw` — text inside the `<time>` element
- `speaker_raw` — text inside `.speaker`, or `None` if the element isn't present
- `location_raw` — text inside `.location`
- `raw_text` — the full text content of the card, kept as a fallback in case something needs re-checking later

Every optional field is guarded with `select_one(...)` returning `None` before calling `.get_text()` on it, so a missing element doesn't throw an `AttributeError`.

**Verified:** running the parser against the fixture returns all 9 events, and the one missing a speaker comes back with `speaker_raw: null` instead of breaking the run.

## Part 2 — IISER Pune Events Scraper

**Files:** `iiserpune/scraper.py`, `iiserpune/sample_response.html`, `iiserpune/output.json`

Target page: `https://www.iiserpune.ac.in/news?category=events`

`scraper.py` keeps fetching and parsing as two separate functions:

- `fetch(url)` — sends the GET request with a timeout and a descriptive `User-Agent`, and raises a clear `RuntimeError` on timeouts, HTTP errors, or other request failures instead of letting an unhandled exception through.
- `parse_items(html, base_url)` — selects every `li.news-card` on the page and extracts the same field set as the fixture parser: `title`, `item_url`, `date_raw`, `speaker_raw`, `location_raw`, `raw_text`.

Keeping these separate matters because they change for different reasons — `fetch()` only needs to change if the request mechanics change (headers, auth, endpoint), while `parse_items()` only needs to change if the page's HTML structure changes. Neither should have to touch the other.

`limit_items(items, limit)` is a small separate helper for trimming the result set. `parse_items()` itself never truncates — it always returns every record it finds on the page. Any cap on how many records to keep is applied afterward, explicitly, rather than being baked silently into the parsing logic.

### What's not available on this page
`speaker_raw` and `location_raw` always come back `None` — confirmed by inspecting the listing page directly that neither field is rendered there. They may exist on individual event detail pages, but pulling those in is out of scope for this assignment.

Dates are kept as plain text exactly as displayed (e.g. `"Posted on Jun 15, 2026"`), since there's no `datetime` attribute anywhere in the markup to rely on. Turning that into an actual parsed date is a normalization step for later, not something this parser handles.

Some cards carry more than one category tag (e.g. both "Events" and "New in Campus"). These aren't extracted right now since they weren't part of the required field set.

### Fixture vs. live
By default the script reads from the saved `sample_response.html` rather than hitting the live site on every run — mainly to avoid repeated requests to IISER Pune's server while testing. To pull fresh data instead, swap the file read in the `__main__` block for a call to `fetch(TARGET_URL)`.

**Verified:** running against the saved fixture returns all 8 event cards present in that file, with correctly resolved absolute URLs and no crashes on the missing speaker/location fields.
