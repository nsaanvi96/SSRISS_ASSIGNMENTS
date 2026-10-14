# Assignment 4 — Incremental Collection and Change Detection

## Run State & Change Detection Architecture

In a production aggregator or monitoring pipeline, discovery runs execute repeatedly (e.g., hourly, daily). If a monitor treated every run as an isolated batch, it would either re-download everything from scratch or miss critical updates. 

Assignment 4 introduces persistent state backed by SQLite and a content hashing mechanism to partition discovery records into four mutually exclusive operational statuses:

| Status | SQLite Condition | Hash Condition | Action Taken |
|---|---|---|---|
| `NEW` | URL not in DB | N/A | Insert row; record `first_seen_at`, `last_seen_at`, `fetched_at`. |
| `UNCHANGED` | URL in DB | `new_hash == old_hash` | Update `last_seen_at` and `fetched_at`; preserve `first_seen_at`. |
| `CHANGED` | URL in DB | `new_hash != old_hash` | Update row and hash; update `last_seen_at`, `fetched_at`; preserve `first_seen_at`. |
| `NOT_SEEN_THIS_RUN` | URL in DB, absent from run | N/A | Preserve row and `last_seen_at`; update `fetched_at` (do NOT delete). |

---

## Answers to Core Design Questions

### 1. What makes an item "new"?

An item is classified as **`NEW`** if its canonical URL has never been seen in any prior run and does not exist in the persistent store (`items` table).

- **Technical Check**:
  ```python
  existing = self._fetch_row(url)
  if existing is None:
      # ItemStatus.NEW
  ```
- **Lifecycle Action**:
  A new row is inserted into SQLite. All three timestamps (`first_seen_at`, `last_seen_at`, `fetched_at`) are initialized to the current run timestamp. Downstream pipelines schedule this item for initial deep fetching, parsing, and indexing.

---

### 2. What makes an item "changed"?

An item is classified as **`CHANGED`** if its canonical URL already exists in the store, but its substantive content fields have evolved since it was last recorded.

- **Technical Check**:
  ```python
  if existing is not None and existing["content_hash"] != new_hash:
      # ItemStatus.CHANGED
  ```
- **Lifecycle Action**:
  The SQLite row is updated in-place with the new `content_hash`, updated `title`, `source_timestamp`, `last_seen_at`, and `fetched_at`. Crucially, `first_seen_at` is **never overwritten**. 
  
  The system captures `old_hash` alongside `content_hash` on the `ClassifiedItem`, allowing downstream processors to trigger re-extraction or emit differential change events without re-ingesting the item as a duplicate.

---

### 3. What fields contribute to your content hash?

Only fields that represent the **semantic substance** of the item contribute to `compute_content_hash()`:

1. **`url`**: The normalized canonical URL (lowercased and whitespace-trimmed).
2. **`title`**: The normalized headline/title text (lowercased and whitespace-trimmed; empty string if `None`).
3. **`source_timestamp`**: The publication or event date as provided by the original publisher (whitespace-trimmed; empty string if `None`).

#### Canonical Hashing Implementation:
```python
def compute_content_hash(
    url: str,
    title: Optional[str],
    source_timestamp: Optional[str],
) -> str:
    parts = [
        url.strip().lower(),
        (title or "").strip().lower(),
        (source_timestamp or "").strip(),
    ]
    raw = "\x00".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
```
- **Delimiters**: Using NUL (`\x00`) separators prevents ambiguous concatenation collisions (e.g. `ab` + `c` producing the same digest as `a` + `bc`).
- **Normalisation**: Case folding and stripping ensure cosmetic whitespace or URL casing variations do not produce spurious hash divergences.

---

### 4. Which volatile fields should NOT contribute to the content hash?

The following fields are strictly excluded from the content hash calculation:

- **`fetched_at` / `discovered_at`**: Transient runtime timestamps that record when our crawler contacted the server.
- **`last_seen_at`**: Bookkeeping timestamp indicating the latest run in which the URL appeared.
- **`first_seen_at`**: Historical epoch timestamp recording when the item entered the system.
- **`discovery_method`**: The channel via which the item was discovered (`html_listing`, `rss`, or `sitemap`). If an item previously discovered via RSS is later encountered on an HTML listing page, its underlying content has not changed.
- **HTTP headers / Session artifacts**: `ETag`, `Last-Modified`, session cookies, or tracking parameters.

---

### 5. Why should `fetched_at` not make every record appear changed?

`fetched_at` is a property of the **crawler's observation**, not a property of the **publisher's content**.

If `fetched_at` were mixed into the content hash:
1. Every item on an unchanged page or feed would generate a new hash on every execution cycle.
2. The entire dataset would be classified as `CHANGED` on every run (`changed=N`, `unchanged=0`).
3. Caching and deduplication would be completely destroyed.
4. Downstream detail workers would be forced to re-fetch and re-parse every single item indefinitely, causing unnecessary load on target servers and consuming wasteful computational resources.

Excluding `fetched_at` from the content hash maintains the separation of concerns:
- **Hash**: Answers *"Did the content change?"*
- **Timestamps**: Answer *"When did we first see it?", "When was it last visible?", and "When did we last inspect the source?"*

---

### 6. What does absence from a current listing actually prove?

Absence from a current listing proves **only** that the item was not visible on the particular page or feed window evaluated during this run. **It does NOT prove that the item was deleted or unpublished.**

#### Why listings rotate without deletions:
- **Feed Windowing**: RSS and Atom feeds typically publish only the most recent 10 to 50 items. As newer posts are published, older posts roll off the feed even though they remain live on the website.
- **Pagination**: An aggregator monitoring page 1 (`/events?page=1`) will not see items that naturally moved to page 2 as newer events were added.
- **Temporary Upstream Omissions**: Dynamic CMS queries, CDN edge cache delays, or server-side filtering can temporarily drop items from a listing.
- **Sitemap Partitioning**: Sitemaps are frequently split into monthly or yearly archives.

#### Operational Strategy:
- When a stored item does not appear in the current discovery run, it is classified as **`NOT_SEEN_THIS_RUN`**.
- Its row is **preserved** in SQLite (never deleted).
- `last_seen_at` remains unchanged (preserving the timestamp of its last known sighting).
- `fetched_at` is updated to confirm that the monitoring process checked the source.
- An item is only marked as deleted (or tombstoned) when direct evidence is obtained, such as an explicit HTTP `404 Not Found` or `410 Gone` during a detail crawl, or an explicit `<tombstone>` tag in a feed.

---

## Cross-Run Lifecycle Example

```text
Run 1: [Item A, Item B, Item C]
       ├── Item A -> NEW
       ├── Item B -> NEW
       └── Item C -> NEW
       State: 3 rows stored.

Run 2: [Item A (same), Item B (title updated), Item D (brand new)]
       ├── Item A -> UNCHANGED        (last_seen_at updated, hash identical)
       ├── Item B -> CHANGED          (last_seen_at updated, hash updated, old_hash captured)
       ├── Item D -> NEW              (inserted into store)
       └── Item C -> NOT_SEEN_THIS_RUN(retained in DB; last_seen_at untouched)
       State: 4 rows stored (A, B, C, D).

Run 3: [Item C (reappears with original title)]
       └── Item C -> UNCHANGED        (first_seen_at preserved from Run 1!)
       Item C is recognized as a rediscovered item, NOT a new item.
```
