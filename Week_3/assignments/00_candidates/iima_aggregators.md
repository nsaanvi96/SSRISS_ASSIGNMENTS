# Assignment 0 — Aggregator Candidate Matrix: IIM Ahmedabad

Looking for a proper high-yield central aggregator for Week 3. In Week 2 we used IISER Pune, but that site has broken feeds and JS-rendered seminars that make automated discovery painful without browser automation. Switching to IIM Ahmedabad (`iima.ac.in`) gives us real, active central feeds and multi-department listings that work directly with plain HTTP requests.

---

## Candidate 1: IIMA Central Events Listing & RSS Feed

- **Name:** IIMA Central Events & Public Engagements
- **URL:** 
  - HTML listing: `https://www.iima.ac.in/the-institute/events`
  - RSS feed: `https://www.iima.ac.in/rss.xml`
- **Institution/organization:** Indian Institute of Management Ahmedabad
- **Surface type:** Central aggregator (server-rendered HTML listing + live RSS 2.0 feed)
- **HTML / RSS / Atom / sitemap / other:** HTML (`.views-row` card layout) + RSS 2.0 XML
- **Content types:** Research conferences (like India Management Research Conference), admissions webinars (PGPX, PhD), public endowment lectures, and academic workshops
- **Approximate update frequency:** Multiple times a week / active in October 2026
- **Departments/units represented:** School of AI, Centre for ESG Research, India Gold Policy Centre, PGPX Admissions, and central institute administration
- **Detail-page links?:** Yes, clean canonical links to `/events/<slug>` and `/node/<id>`
- **Pagination/archive?:** Yes, standard Drupal views pagination and past event archives
- **Speaker information?:** Available on detail pages (keynotes, session chairs, presenters)
- **Organization information?:** Clearly tagged with the organizing center or program
- **Access considerations:** 
  - Plain `requests.get` returns full HTML (HTTP 200, ~468 KB).
  - `/rss.xml` is live and returns HTTP 200 with valid XML.
  - `robots.txt` has no blocking rules for these paths. Fast response times, no bot protection/Cloudflare blocking.
- **Why this is high-yield or low-yield:** **High-yield.** One single page captures events across multiple schools and research centers. The matching RSS feed makes it even better because we can do change detection without constantly parsing full HTML pages.

---

## Candidate 2: IIMA Research Centres Directory

- **Name:** IIMA Research Centres Directory
- **URL:** `https://www.iima.ac.in/faculty-research/centers`
- **Institution/organization:** Indian Institute of Management Ahmedabad
- **Surface type:** HTML directory / index page
- **HTML / RSS / Atom / sitemap / other:** Server-rendered HTML
- **Content types:** Center-specific working papers, policy roundtables, specialized seminars
- **Approximate update frequency:** Around once every 2–4 weeks per center
- **Departments/units represented:** 9 individual centers (Transportation and Logistics, Digital Transformation, ESG, CIIE, etc.)
- **Detail-page links?:** Yes, links out to each center's sub-page
- **Pagination/archive?:** Inconsistent across the different center sub-pages
- **Speaker information?:** Sometimes in the body text of specific notices
- **Organization information?:** Organized by center name
- **Access considerations:** Open access, plain HTML, no login needed.
- **Why this is high-yield or low-yield:** **Lower-yield.** The content is good, but it's scattered across 9 separate center sub-pages. Scraping this means writing custom logic for multiple sub-pages that barely update, leading to lots of wasted HTTP requests.

---

## Candidate 3: IISER Pune Events & Seminars Surface (Week 2 Baseline)

- **Name:** IISER Pune Events & Seminars Portal
- **URL:** 
  - Events: `https://www.iiserpune.ac.in/news?category=events`
  - Seminars: `https://www.iiserpune.ac.in/events/seminars`
  - Feed: `https://www.iiserpune.ac.in/news/feed`
- **Institution/organization:** Indian Institute of Science Education and Research Pune
- **Surface type:** Fragmented (HTML news listing + Vue.js client-side SPA)
- **HTML / RSS / Atom / sitemap / other:** HTML listing + client-rendered JS + broken RSS feed
- **Content types:** Seminars, colloquia, conferences, campus news
- **Approximate update frequency:** 2–4 items per week
- **Departments/units represented:** Natural sciences (Biology, Chemistry, Physics, Math)
- **Detail-page links?:** Yes for `/news?category=events`, but seminars use client-rendered JS routes
- **Pagination/archive?:** Archive buttons exist, but pagination is minimal
- **Speaker information?:** Missing on listing cards, buried inside detail page text
- **Organization information?:** Institute-level only
- **Access considerations:** 
  - The main seminars page (`/events/seminars`) returns unrendered Vue template placeholders (`{{Item.Title}}`, `{{Item.StartDateTime}}`) in raw HTML. Standard `requests.get` gets no usable event data without running a full browser like Playwright.
  - The advertised RSS feed at `/news/feed` returns a 500 server error every time.
  - `/sitemap.xml` returns 404.
- **Why this is high-yield or low-yield:** **Low-yield.** Between the broken RSS feed and the client-side SPA rendering, automated scraping requires too many workarounds or mock fixtures for very few event records.

---

## Ranking

1. **Best target:** IIMA Central Events Listing & RSS Feed (`/the-institute/events` & `/rss.xml`)
2. **Backup target:** IIMA Research Centres Directory (`/faculty-research/centers`)
3. **Not recommended:** IISER Pune Events & Seminars (`/events/seminars`)

### Why this ranking?

- **Candidate 1 is clearly the best** because it gives us two live, working channels right out of the box: a clean server-rendered HTML listing and a live RSS feed that actually returns HTTP 200 with new items this week. It covers multiple departments and centers, doesn't need browser automation, and doesn't force us to use fake fixtures for feed discovery.
- **Candidate 2 is the backup** because while it has real HTML data, it's fragmented. We'd have to crawl 9 different center sub-pages individually, which is slower, harder to maintain, and yields far fewer updates per request.
- **Candidate 3 is not recommended** because of technical blockers. We verified that its RSS feed crashes with a 500 error, and its seminar listings are pure Vue.js templates in raw HTML. It fails the criteria for a reliable, low-complexity aggregation target.

---

## Checkpoint: Why one central page is more valuable than crawling ten unrelated low-yield pages

Crawling ten individual department pages might seem like a way to get data, but in practice it creates major engineering headaches:

1. **Wasted network traffic and server load:** Department pages don't update very often—maybe once or twice a month. Hitting 10 separate pages on every run means 90% of our HTTP requests return zero new items. A central page aggregates all campus updates in one place, so a single polite GET request pulls all recent activity across the whole institute.
2. **Brittle scraper maintenance:** Every department site usually has its own HTML structure, CSS classes, and layouts. If you write 10 parsers for 10 pages, you have 10 different points of failure whenever a department redesigns its site. A central aggregator gives us one consistent DOM structure (`.views-row` or RSS `<item>`) to maintain.
3. **Standardized metadata:** Central aggregators usually enforce a common format for dates, event titles, categories, and hosting units. Department pages often leave out obvious context (like forgetting to mention which department the talk belongs to because it's already on their own website).
4. **Preventing crawler drift:** When navigating across individual departmental sites, crawlers easily get lost following links into course timetables, faculty bios, or external links. A central events page sets clear boundaries where every link is a real event record.
