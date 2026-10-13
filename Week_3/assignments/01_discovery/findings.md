# Assignment 1A — Feed & Sitemap Inspection Findings

**Target Institution:** Indian Institute of Management Ahmedabad (IIMA)  
**Domain:** `https://www.iima.ac.in`  
**Focus Area:** Discovery mechanism inspection for public events and institutional updates  

---

## 1. Executive Summary & Target Audit

In Week 1 and Week 2, discovery was conducted via direct HTML scraping and crawling. In Week 3, we examine whether lower-complexity structured public surfaces—specifically **RSS/Atom feeds** and **XML Sitemaps**—exist on our target domain to serve as candidate discovery mechanisms.

| Surface Type | URL / Endpoint | HTTP Status | Content-Type | Usability Status |
| :--- | :--- | :--- | :--- | :--- |
| **RSS 2.0 Feed** | `https://www.iima.ac.in/rss.xml` | **200 OK** | `application/rss+xml; charset=utf-8` | **Production Ready** (Live syndication of 10 latest nodes/events) |
| **Atom Feed** | `https://www.iima.ac.in/atom.xml` | **404 Not Found** | `text/html` | Not exposed (RSS 2.0 serves syndication) |
| **XML Sitemap** | `https://iima.ac.in/sitemap.xml` | **404 Not Found** | `text/html` | Advertised in `robots.txt`, but server returns 404 |
| **XML Sitemap** | `https://www.iima.ac.in/sitemap.xml`| **404 Not Found** | `text/html` | Non-functional endpoint |
| **Sitemap Index**| `https://www.iima.ac.in/sitemap_index.xml` | **404 Not Found** | `text/html` | Non-functional endpoint |
| **HTML Sitemap** | `https://www.iima.ac.in/sitemap` | **200 OK** | `text/html; charset=UTF-8` | Human-facing navigation page (not machine XML) |

### Key Discovery Findings
1. **Live RSS Feed:** The IIMA Drupal CMS actively publishes an RSS 2.0 feed at `/rss.xml`. It serves live updates with `<title>`, `<link>`, `<pubDate>`, and `<guid>` elements, making it an ideal discovery mechanism.
2. **Missing XML Sitemap:** Although `robots.txt` explicitly declares:
   ```text
   Sitemap: https://iima.ac.in/sitemap.xml
   Sitemap: https://iima.ac.in/images_sitemap.xml
   ```
   Both endpoints return HTTP 404 from the web server. Per the assignment instructions (*"If the institution does not expose a usable feed/sitemap for the target content, use a local sample fixture to complete the technical exercise"*), we provide and validate local XML fixtures in `fixtures/sample_sitemap.xml` and `fixtures/sample_sitemap_index.xml`.

---

## 2. Feed Inspection (`inspect_feed.py`)

### Implementation Details
- Uses `feedparser` with an automated fallback to standard library `xml.etree.ElementTree`.
- Supports inspecting live feeds (`--url`), local cached feeds (`--fixture`), or custom files (`--file`).
- Normalizes entry links, titles, published timestamps, and discovery sources.

### Controlled Sample Output (Live Target: `https://www.iima.ac.in/rss.xml`)
```text
======================================================================
FEED INSPECTION REPORT (Assignment 1A)
======================================================================
Source URL / Path : https://www.iima.ac.in/rss.xml
Feed Title        : IIMA
Feed Format       : rss20
Total Items Found : 10
Sample Items Shown: 5
----------------------------------------------------------------------
[1] Candidate Item:
    URL              : http://www.iima.ac.in/node/22422
    Title            : The Role of Bioenergy in Sustainable Energy Transitions: A subregional Modelling assessment towards India’s climate commitments”. Biomass and Bioenergy
    Published/Updated: Mon, 12 Oct 2026 11:22:51 +0000
    Discovery Source : feedparser (rss20)

[2] Candidate Item:
    URL              : http://www.iima.ac.in/node/22420
    Title            : Why India's top 25 B-schools have reported lower admissions this year
    Published/Updated: Sun, 11 Oct 2026 10:25:04 +0000
    Discovery Source : feedparser (rss20)

[3] Candidate Item:
    URL              : http://www.iima.ac.in/eventswebinar-women-applicants
    Title            : Webinar for Women Applicants
    Published/Updated: Fri, 09 Oct 2026 10:11:17 +0000
    Discovery Source : feedparser (rss20)

[4] Candidate Item:
    URL              : http://www.iima.ac.in/node/22416
    Title            : Creation After Destruction? Financial Intermediation and Firm Entry After Bank Cleanups
    Published/Updated: Thu, 08 Oct 2026 03:05:32 +0000
    Discovery Source : feedparser (rss20)

[5] Candidate Item:
    URL              : http://www.iima.ac.in/news/inauguration-20th-batch-armed-forces-programme
    Title            : Inauguration of the 20th batch of the Armed Forces Programme
    Published/Updated: Tue, 06 Oct 2026 11:36:53 +0000
    Discovery Source : feedparser (rss20)
======================================================================
```

---

## 3. Sitemap Inspection (`inspect_sitemap.py`)

### Implementation Details
- Uses Python's standard library `xml.etree.ElementTree`.
- Parses Sitemaps XML namespaces (`http://www.sitemaps.org/schemas/sitemap/0.9`).
- Handles both `<urlset>` (direct page URLs) and `<sitemapindex>` (hierarchical indexes of child sitemaps).
- Gracefully audits the target URL (`https://iima.ac.in/sitemap.xml`), logs the 404 response, and evaluates the local fixture (`fixtures/sample_sitemap.xml`).

### Controlled Sample Output (`<urlset>` Fixture)
```text
[TARGET AUDIT NOTICE] Fetching 'https://iima.ac.in/sitemap.xml' returned HTTP 404: Not Found.
[TARGET AUDIT NOTICE] Target does not expose a functional XML sitemap at this endpoint.
[TARGET AUDIT NOTICE] Loading local technical exercise fixture: fixtures/sample_sitemap.xml

======================================================================
SITEMAP INSPECTION REPORT (Assignment 1A)
======================================================================
Source URL / Path : fixtures/sample_sitemap.xml
Fixture Fallback? : Yes (Local Sample Fixture)
Sitemap Type      : <urlset> (Standard URLSet)
Total Items Found : 5
Sample Items Shown: 5
----------------------------------------------------------------------
[1] Candidate Item:
    URL              : https://www.iima.ac.in/the-institute/events/annual-management-symposium-2026
    Title            : None (Sitemaps protocol omits titles)
    Published/Lastmod: 2026-10-12T14:30:00+05:30
    Discovery Source : sitemap:urlset

[2] Candidate Item:
    URL              : https://www.iima.ac.in/the-institute/events/sustainable-finance-roundtable
    Title            : None (Sitemaps protocol omits titles)
    Published/Lastmod: 2026-10-10T09:15:00+05:30
    Discovery Source : sitemap:urlset

[3] Candidate Item:
    URL              : https://www.iima.ac.in/the-institute/events/ai-in-healthcare-workshop
    Title            : None (Sitemaps protocol omits titles)
    Published/Lastmod: 2026-10-08T18:00:00+05:30
    Discovery Source : sitemap:urlset

[4] Candidate Item:
    URL              : https://www.iima.ac.in/faculty-research/working-paper-series-seminar
    Title            : None (Sitemaps protocol omits titles)
    Published/Lastmod: 2026-10-05T11:00:00+05:30
    Discovery Source : sitemap:urlset

[5] Candidate Item:
    URL              : https://www.iima.ac.in/the-institute/events/pgpx-leadership-speaker-session
    Title            : None (Sitemaps protocol omits titles)
    Published/Lastmod: 2026-09-28T16:45:00+05:30
    Discovery Source : sitemap:urlset
======================================================================
```

### Controlled Sample Output (`<sitemapindex>` Fixture via `--index-fixture`)
```text
======================================================================
SITEMAP INSPECTION REPORT (Assignment 1A)
======================================================================
Source URL / Path : fixtures/sample_sitemap_index.xml
Fixture Fallback? : Yes (Local Sample Fixture)
Sitemap Type      : <sitemapindex> (Sitemap Index)
Total Items Found : 3
Sample Items Shown: 3
----------------------------------------------------------------------
[1] Candidate Item:
    URL              : https://www.iima.ac.in/sitemaps/events-sitemap.xml
    Title            : None (Sitemaps protocol omits titles)
    Published/Lastmod: 2026-10-12T00:00:00+05:30
    Discovery Source : sitemap:sitemapindex

[2] Candidate Item:
    URL              : https://www.iima.ac.in/sitemaps/faculty-sitemap.xml
    Title            : None (Sitemaps protocol omits titles)
    Published/Lastmod: 2026-10-01T00:00:00+05:30
    Discovery Source : sitemap:sitemapindex
======================================================================
```

---

## 4. Architectural Comparison: Discovery Channels

| Dimension | RSS / Atom Feed | XML Sitemap (`<urlset>`) | HTML Central Listing |
| :--- | :--- | :--- | :--- |
| **Primary Intent** | Content syndication / new event announcements | Search engine indexation / site crawler navigation | Human browsing & visual scanning |
| **URL Field** | `<link>` or `<guid isPermaLink="true">` | `<loc>` | `<a href="...">` in card DOM |
| **Item Title** | Explicitly available via `<title>` | **Not available** (omitted in protocol) | Available in card headings |
| **Timestamp Semantics** | Published/broadcast date (`<pubDate>`) | Content modification time (`<lastmod>`) | Stated event start date (often not modification time) |
| **Payload Size** | Lightweight (~10–30 KB) | Small to Medium (~5–500 KB) | Heavy (~100 KB–1 MB with markup/scripts) |
| **Change Detection** | High (check latest `pubDate` or feed hash) | High (compare `<lastmod>` header) | Low (must diff full HTML DOM) |

---

## 5. Checkpoint: Discovering a URL vs. Extracting a Complete Event Record

A central lesson of pipeline architecture is the clear division of labor between **Discovery** and **Extraction**.

### Phase 1: Discovering a URL
- **What it does:** Identifies candidate web identifiers (URLs) that *might* contain an event record, along with discovery provenance (`discovered_url`, `discovery_method`, `source_timestamp`, `discovered_at`).
- **Resource cost:** Extremely light. It operates on cheap surfaces (RSS feeds, XML sitemaps, or index card listings).
- **Scope of knowledge:** Thin and incomplete. A discovery record often lacks the event's start/end times, venue, speakers, registration links, or full agenda. In sitemaps, it does not even include an event title.
- **Role in pipeline:** Acts as a **deduplication filter** and a **work queue generator**. It answers: *"Have we seen this URL before? Has it been modified since our last crawl?"* If not, the URL is enqueued for extraction; if yes, it is ignored without downloading the detail page.

### Phase 2: Extracting a Complete Event Record
- **What it does:** Fetches the specific detail page identified during discovery, runs structured parsing (DOM extraction, JSON-LD schema extraction, microdata, or regex heuristics), and validates complete business entities.
- **Resource cost:** Expensive. Requires fetching individual full-page HTML payloads, downloading assets, or running headless browsers if hydration is required.
- **Scope of knowledge:** Rich and exhaustive. Produces a validated record containing:
  - Canonical Event Title
  - Event Start and End Timestamps (with normalized Timezones)
  - Location / Physical Venue / Virtual Meeting Link
  - Keynote Speakers & Affiliations
  - Event Description & Abstract
  - Sponsoring Department / Center
- **Role in pipeline:** Serves as the **ingestion & storage payload** for downstream databases, calendars, and end-user feeds.

### Why Conflating the Two is an Anti-Pattern
1. **Unnecessary Load:** Attempting extraction during discovery couples rapid link-finding with slow page downloads, causing crawler bottlenecks.
2. **Crawler Drift:** Without an initial discovery queue, crawlers wander into peripheral pages (faculty profiles, past press releases, campus galleries) trying to extract events where none exist.
3. **Pipeline Inflexibility:** Downstream extractors should only care about receiving a normalized candidate URL, regardless of whether that URL originated from an RSS feed, an XML sitemap, or an HTML card listing.

---

## 6. Verification and Reproducibility

To run the Assignment 1A inspectors:

```powershell
# 1. Inspect live IIMA RSS feed
python Week_3/assignments/01_discovery/inspect_feed.py -n 3

# 2. Inspect RSS feed using offline fixture
python Week_3/assignments/01_discovery/inspect_feed.py --fixture -n 3

# 3. Inspect XML Sitemap (audits remote URL, logs 404, evaluates fixture)
python Week_3/assignments/01_discovery/inspect_sitemap.py -n 3

# 4. Inspect XML Sitemap Index fixture
python Week_3/assignments/01_discovery/inspect_sitemap.py --index-fixture -n 3
```

---

## 7. Assignment 1B — Unified Discovery Record

### Architecture & Canonical Schema
Assignment 1B solves channel divergence by mapping heterogeneous discovery formats (**HTML Listings**, **RSS 2.0 Feeds**, and **XML Sitemaps**) into an identical canonical data contract:

```json
{
  "source_name": "iima",
  "discovered_url": "https://www.iima.ac.in/events/india-management-research-conference-2026",
  "discovery_method": "html_listing",
  "discovered_title": "India Management Research Conference 2026",
  "source_timestamp": "Dec 2026 04",
  "discovered_at": "2026-10-13T15:52:23.545231+00:00"
}
```

### Adapters Implemented in `unified_discovery.py`
1. **`HtmlListingAdapter`**:
   - Parses `.views-row` card elements from `https://www.iima.ac.in/the-institute/events` (or `fixtures/sample_html_listing.html`).
   - Normalizes relative URLs (`/events/...`) to canonical absolute URLs.
   - Extracts candidate event title and date card labels.
   - Tags record with `"discovery_method": "html_listing"`.

2. **`RssFeedAdapter`**:
   - Parses items from `https://www.iima.ac.in/rss.xml` (or `fixtures/sample_feed.xml`).
   - Maps `<link>` / `<guid>` to `discovered_url`, `<title>` to `discovered_title`, and `<pubDate>` to `source_timestamp`.
   - Tags record with `"discovery_method": "rss"`.

3. **`SitemapAdapter`**:
   - Traverses `<urlset>` items from `fixtures/sample_sitemap.xml`.
   - Maps `<loc>` to `discovered_url` and `<lastmod>` to `source_timestamp`.
   - Explicitly records `discovered_title: null` (reflecting Sitemaps protocol standard).
   - Tags record with `"discovery_method": "sitemap"`.

### Execution Output Across All Three Channels
```text
================================================================================
UNIFIED DISCOVERY RECORD REPORT (Assignment 1B)
================================================================================
>>> CHANNEL: [HTML_LISTING] (2 candidate items)
--------------------------------------------------------------------------------
{
  "source_name": "iima",
  "discovered_url": "https://www.iima.ac.in/events/india-management-research-conference-2026",
  "discovery_method": "html_listing",
  "discovered_title": "India Management Research Conference 2026",
  "source_timestamp": "Dec 2026 04",
  "discovered_at": "2026-10-13T15:52:23.545231+00:00"
}
{
  "source_name": "iima",
  "discovered_url": "https://www.iima.ac.in/events/last-minute-q-pgpx-admissions-team.",
  "discovery_method": "html_listing",
  "discovered_title": "Last Minute Q & A with PGPX Admissions Team",
  "source_timestamp": "Nov 2026 23",
  "discovered_at": "2026-10-13T15:52:23.545231+00:00"
}

>>> CHANNEL: [RSS] (2 candidate items)
--------------------------------------------------------------------------------
{
  "source_name": "iima",
  "discovered_url": "http://www.iima.ac.in/node/22422",
  "discovery_method": "rss",
  "discovered_title": "The Role of Bioenergy in Sustainable Energy Transitions...",
  "source_timestamp": "Mon, 12 Oct 2026 11:22:51 +0000",
  "discovered_at": "2026-10-13T15:52:23.743852+00:00"
}
{
  "source_name": "iima",
  "discovered_url": "http://www.iima.ac.in/node/22420",
  "discovery_method": "rss",
  "discovered_title": "Why India's top 25 B-schools have reported lower admissions this year",
  "source_timestamp": "Sun, 11 Oct 2026 10:25:04 +0000",
  "discovered_at": "2026-10-13T15:52:23.743852+00:00"
}

>>> CHANNEL: [SITEMAP] (2 candidate items)
--------------------------------------------------------------------------------
{
  "source_name": "iima",
  "discovered_url": "https://www.iima.ac.in/the-institute/events/annual-management-symposium-2026",
  "discovery_method": "sitemap",
  "discovered_title": null,
  "source_timestamp": "2026-10-12T14:30:00+05:30",
  "discovered_at": "2026-10-13T15:52:23.744434+00:00"
}
{
  "source_name": "iima",
  "discovered_url": "https://www.iima.ac.in/the-institute/events/sustainable-finance-roundtable",
  "discovery_method": "sitemap",
  "discovered_title": null,
  "source_timestamp": "2026-10-10T09:15:00+05:30",
  "discovered_at": "2026-10-13T15:52:23.744434+00:00"
}
```

### Checkpoint Analysis: Pipeline Source Agnosticism
**Core Principle:** *The downstream pipeline should not have to care whether an item URL was first found through HTML, RSS, or a sitemap.*

1. **Decoupled Architecture:**
   The crawl scheduler, deduplication cache (e.g. SQLite or Redis), and detail-page extractor only inspect `discovered_url` and `source_timestamp`. They do not parse RSS XML, HTML DOM cards, or sitemaps.
2. **Channel Pluggability:**
   If a website's RSS feed goes down, an administrator can configure a Sitemap or HTML listing adapter without changing a single line of downstream worker code.
3. **Automated Verification:**
   The test suite [`test_unified_discovery.py`](file:///c:/Users/Saanvi/Documents/SAANVI/SSRISS_ASSIGNMENTS-1/Week_3/assignments/01_discovery/test_unified_discovery.py) includes `test_checkpoint_downstream_consumer_pipeline_agnostic()`, which routes records from HTML, RSS, and Sitemap through a shared deduplicating queue function, proving complete interoperability (5 passed tests).

To run Assignment 1B:
```powershell
# Run all adapters and print unified report
python Week_3/assignments/01_discovery/unified_discovery.py -n 2

# Run all adapters in pure offline fixture mode
python Week_3/assignments/01_discovery/unified_discovery.py --fixture -n 2

# Output unified JSON records
python Week_3/assignments/01_discovery/unified_discovery.py -n 2 --json

# Run unit tests
python -m pytest Week_3/assignments/01_discovery/test_unified_discovery.py
```

