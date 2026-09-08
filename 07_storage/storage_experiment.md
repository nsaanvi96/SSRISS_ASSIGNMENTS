# Storage Experiment — IISER Pune Events (Assignment 7)

`storage.py` implements `init_db()`, `upsert_item()`, and `get_item()` against a single
`items` table, keyed on `item_url`. `run_experiment.py` loads the 8 events from
`sample_response.html` (same fixture from Assignment 5B/6), runs them through the
scraper's `parse_items()` + `normalize_item()`, and pushes the normalized items through
`upsert_item()` three times.

## What actually happened

```text
RUN 1: 8 total -> 8 new, 0 unchanged, 0 updated
RUN 2: 8 total -> 0 new, 8 unchanged, 0 updated
RUN 3 (one item modified): 8 total -> 0 new, 7 unchanged, 1 updated
```

Row count in the database after all three runs: **8**. No duplicates.

For Run 3, I modified the first item's `title` in memory (appended " (UPDATED)") without
changing its `item_url`, then re-ran. The stored row picked up the new title, kept its
original `first_seen_at`, and bumped `last_seen_at`.

## Answers

**1. How are duplicates identified?**
By `item_url`, which is the table's primary key. Before inserting, `upsert_item()` does
a `SELECT` on `item_url` — if a row already exists, it's not a duplicate, it's the same
item being seen again.

**2. What happens if the same URL appears twice?**
Nothing gets inserted twice. The second occurrence hits the existing-row branch: if the
content hash matches, only `last_seen_at`/`fetched_at`/`http_status` get touched. If the
hash differs, the row's content columns get updated in place. Either way it's one row,
not two.

**3. What would `first_seen_at` mean?**
The timestamp from the very first time this `item_url` was successfully stored. It's set
once on insert and never touched again — it answers "when did we first discover this."

**4. What would `last_seen_at` mean?**
The timestamp of the most recent run in which this `item_url` showed up on the page
again, whether or not its content changed. It answers "is this still current," and could
later be used to notice items that have quietly disappeared from the source (their
`last_seen_at` stops advancing).

**5. Why might a `content_hash` be useful?**
It's a cheap way to answer "did anything meaningful change?" without manually diffing
every column. The hash here is built only from `title`, `event_start`, `event_end`,
`location`, `speakers`, `organizations`, and `raw_text` — deliberately excluding
`fetched_at` and `http_status`, since those change on every single run regardless of
whether the actual content did. If they were included, every re-run would look like an
"update" even when the page hadn't changed at all.

**6. Why is "scraping the page again" different from "discovering a new item"?**
Scraping the page again just means the crawler ran — it says nothing about whether the
underlying content is new. Discovering a new item means an `item_url` shows up that the
database has never seen before. Running the same fixture twice is "scraping again" with
zero discovery. Run 3 is still "scraping again" for 7 of the 8 items, but a genuine
content change (not a new discovery) for the modified one. Conflating the two would mean
either re-announcing old items as new every run, or missing the fact that an existing
item's content moved.
