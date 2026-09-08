# Normalization Notes — IISER Pune Events (Assignment 6)

`normalize_item()` lives in `scraper.py` alongside `parse_items()`, kept as a separate
function so a change in how the page displays something (dates, speakers) doesn't
require touching the extraction logic, and vice versa.

## Assumptions made

1. **Timezone.** The site never states a timezone anywhere on the page or in the date
   text itself. Since IISER Pune is physically in Pune, dates are normalized with a
   hardcoded `+05:30` (IST) offset. If this were ever scraping a source outside India,
   this assumption would need to change.

2. **Date format.** `_parse_posted_date()` assumes every date string matches
   `"Posted on <Mon> <Day>, <Year>"` exactly (e.g. `"Posted on Jun 15, 2026"`) and parses
   it with `strptime(..., "%b %d, %Y")`. If the site ever changes its date phrasing —
   different abbreviation style, added weekday, etc. — this will silently return `None`
   for `event_start` rather than crash, but it also won't parse anything until the format
   string is updated.

3. **"Posted on" date used as `event_start`.** This is actually the date the item was
   *published*, not necessarily the date of the event itself — a few of the raw_text
   bodies mention a different date for when the actual event happened (e.g. the
   convocation post is "Posted on May 29, 2026" but describes an event held on May 29,
   2026 anyway — that one lines up, but "Faculty Get-Together" is posted Apr 23 while
   describing something that happened Apr 21). Since the listing page doesn't expose a
   separate event date, `event_start` is being used as a stand-in for now. Getting the
   real event date would mean visiting the detail page, which is out of scope here.

4. **Missing speaker/location.** `speaker_raw` and `location_raw` come back `None` for
   every single record on this surface (confirmed in Assignment 5B) — not just
   occasionally missing. `normalize_item()` turns a `None` speaker into an empty list
   (`[]`) rather than `[None]`, and leaves `location` as `None` rather than inventing a
   placeholder string.

## Verified

Ran `scraper.py` against `sample_response.html` — all 8 raw items parsed, all 8
normalized without errors, and `iiserpune_normalized.jsonl` conforms to the shared
schema (one JSON object per line, all required keys present).
