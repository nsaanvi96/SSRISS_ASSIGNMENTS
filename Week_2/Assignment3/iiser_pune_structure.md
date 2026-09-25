# IISER Pune — Structural Map
## Assignment 3 | Week 2

---

## Surface 1: News > Events Listing

**URL:** https://www.iiserpune.ac.in/news?category=events  
**Record type:** News/event post  
**Listing → detail?:** Yes — each card links to a detail page e.g. `/news/post/slug/1691`  
**Pagination?:** No — all records on one page (~15 visible)  
**Archive?:** Yes — `?archived=true&category=events` link present for older records  
**Fields on listing:** title, date (plain text "Posted on Jun 15, 2026"), summary excerpt, category tags (can be multiple), item URL, thumbnail image URL  
**Fields on detail:** full body text, images, complete article  
**HTML / PDF / other:** Plain server-rendered HTML  
**Suitable for reusable template?:** Yes  
**Why:** Cleanest listing surface on the site. Consistent `ul.news-cards li.news-card` record boundary. Same template works across all `/news?category=*` variants (research-news, new-in-campus, spotlight, beyond-the-campus, in-the-media). No JS rendering. Archive link is discoverable for historical crawling.

**Record boundary selector:** `ul.news-cards li.news-card`  
**Key selectors:**
- Title: `.news-card .news-title a`
- URL: `.news-card .news-title a[href]`
- Date: `.news-card .news-date` (plain text, format: "Posted on Mon DD, YYYY")
- Summary: `.news-card .summary`
- Category tags: `.news-card .category-tag` (multiple possible per card)

**Notes:**
- Date has no `datetime` attribute — requires string parsing downstream
- Some cards have multiple category tags (e.g. "Events" + "New in Campus")
- A department filter dropdown exists on the page (`select[name=Department]`) — filtering by department is a query param, not a separate page

---

## Surface 2: Department Faculty Listing (Biology)

**URL:** https://www.iiserpune.ac.in/research/department/biology/people/faculty/regular-faculty  
**Record type:** Faculty profile  
**Listing → detail?:** Yes — each card links to an individual profile page e.g. `/research/department/biology/people/faculty/regular-faculty/anjan-banerjee/12`  
**Pagination?:** No — all ~30 records on a single page  
**Archive?:** No  
**Fields on listing:** name, designation/title, research areas (brief, sometimes empty `<markdown></markdown>`), email, profile URL  
**Fields on detail:** name, title, department(s), research areas (fuller), phone, email, lab website URL, bio paragraph, selected publications  
**HTML / PDF / other:** Plain server-rendered HTML  
**Suitable for reusable template?:** Yes — strongly recommended  
**Why:** Identical `ul.people-list li article` structure confirmed on both Biology and Chemistry departments. Same URL pattern `/research/department/{slug}/people/faculty/regular-faculty` applies across all 8 departments. Makes it the best cross-department reusable template candidate on the site.

**Record boundary selector:** `ul.people-list li article`  
**Key selectors (listing):**
- Profile URL: `li article a.profile-content[href]`
- Name: `li article a.profile-content h4` (text nodes split across first name / middle initial / last name — must join and strip)
- Designation: `li article a.profile-content p:first-of-type`
- Research areas: `li article .extra-info p:not(.apply-department-seperator)`
- Email: `li article .email`

**Key selectors (detail page — `section.page-person-profile`):**
- Name: `.name-card h3[itemprop=name]`
- Title: `.name-card p[itemprop=jobTitle]`
- Department(s): `.name-card .apply-department-seperator span`
- Research areas: `.name-card .pre-line-inner:first-of-type`
- Phone: `.name-card [itemprop=telephone]`
- Email: `.name-card [itemprop=email]`
- Lab website: `.name-card [itemprop=url] a[href]`
- Bio + publications: `.rich-text.markdown-text` (full text block)

**Notes:**
- Name is rendered as separate `<h4>` text nodes (first / middle / last) — joining and stripping whitespace is required
- Some faculty have an empty `<markdown></markdown>` tag instead of research areas — parser must handle gracefully
- Some faculty appear under multiple departments (e.g. Amrita Hazra: Chemistry + Biology Joint). Deduplication by `item_url` handles this since profile URL is unique per person
- Designation strings are verbose and inconsistent e.g. "Professor and Rahul Bajaj Chair Professor", "Professor (Currently on Deputation to NCBS Bengaluru)" — normalization needed
- Email div has a trailing `\n` — strip required

---

## Surface 3: Department Faculty Listing (Chemistry)

**URL:** https://www.iiserpune.ac.in/research/department/chemistry/people/faculty/regular-faculty  
**Record type:** Faculty profile  
**Listing → detail?:** Yes — same pattern as Biology  
**Pagination?:** No — all ~30 records on a single page  
**Archive?:** No  
**Fields on listing:** same as Biology listing  
**Fields on detail:** same as Biology detail page structure  
**HTML / PDF / other:** Plain server-rendered HTML  
**Suitable for reusable template?:** Yes — confirms the Biology faculty parser is reusable across departments  
**Why:** Identical `ul.people-list li article` HTML structure. Same record boundary, same selectors, same URL pattern. A single `parse_faculty_listing()` function parameterized by department slug covers both without modification.

**Notes:**
- Chemistry has sub-tabs: Regular Faculty, Joint Faculty, Adjunct Faculty (Biology had: Regular, Emeritus, Joint, Adjunct, Guest). Each is a separate URL — same template applies to all.

---

## Surface 4: Announcements Listing

**URL:** https://www.iiserpune.ac.in/announcements/  
**Record type:** Announcement  
**Listing → detail?:** Yes — each title links to a detail page e.g. `/announcements/10/slug`  
**Pagination?:** None observed  
**Archive?:** None observed  
**Fields on listing:** date (`time[datetime]` attribute — machine-readable ISO format), title, item URL  
**Fields on detail:** not inspected  
**HTML / PDF / other:** Plain server-rendered HTML  
**Suitable for reusable template?:** Yes — simple and clean, though low yield  
**Why:** Best date field on the site — uses a `datetime` attribute (`datetime="2026-01-01 17:19"`) so no string parsing needed. `li.annoucements-item` is the record boundary. Currently only 1 record visible, so not a high-yield monitoring surface, but structurally clean.

**Record boundary selector:** `ul.annoucements-list li.annoucements-item`  
**Key selectors:**
- Date (machine-readable): `li.annoucements-item time[datetime]`
- Date (display): `li.annoucements-item .date time`
- Title: `li.annoucements-item a.annoucement-title span`
- URL: `li.annoucements-item a.annoucement-title[href]`

---

## Rejected Surface: `/events/` Landing Page

**URL:** https://www.iiserpune.ac.in/events/  
**Why rejected:** Vue.js rendered — the entire listing is inside `<div id="EventsApp">` and populated via JS API calls at runtime. `view-source` shows an empty Vue template with `v-for`, `:class`, and `{{Item.Title}}` bindings but no actual records. Not suitable for `requests` + BeautifulSoup.  
**Note:** `/events/colloquia`, `/events/seminars`, `/events/workshops` etc. all follow the same Vue-rendered pattern — all rejected for the same reason.

---

## Confirmed Server-Rendered Event Detail Pages

**URL pattern:** `/events/{id}/{slug}` e.g. `/events/6180/molecular-biology-workshops-on-regulation-of-gene-expression-qualitative`  
**How discovered:** Via `ul.event-cards-aside li.event-card a[href]` on department overview pages and the research landing page  
**Record type:** Individual event  
**HTML / PDF / other:** Plain server-rendered HTML  
**Fields available:**
- Title: `h2.text-color-red[itemprop=name]`
- Speaker / affiliation: `.rich-text.mt-3` (plain text block — not structured)
- Location: `address[itemprop=location]`
- Start datetime: `span[itemprop=startDate]` (plain text e.g. "Mon, Mar 09, 2009 12:00 am")
- End datetime: `span[itemprop=endDate]`

**Notes:**
- Speaker and affiliation are rendered together in a single unstructured text block — no separate fields
- Start/end times use plain text, not ISO datetime — requires parsing
- These detail pages are the only server-rendered source for structured event metadata with speaker info on this site

---

## Potential Common Template

The following patterns repeat across multiple pages and are candidates for shared parsers:

**Faculty listing template** (`ul.people-list li article`): confirmed identical on Biology and Chemistry. URL pattern `/research/department/{slug}/people/faculty/regular-faculty` makes it trivially parameterizable. Expected to work on all 8 departments without selector changes.

**News listing template** (`ul.news-cards li.news-card`): works across all `/news?category=*` variants. Six categories (research-news, events, new-in-campus, spotlight, beyond-the-campus, in-the-media) share the same HTML structure — one parser, six sources.

**Dept overview events aside** (`ul.event-cards-aside li.event-card`): present on `/research` (main landing) and `/research/department/biology`. Shows upcoming and past events with title, category tag, date range, and item URL. Useful as a discovery surface to find event detail page URLs. Not suitable as a primary extraction surface — shows only 1–6 records at a time.

---

## Source-Specific Exceptions

- **Name rendering split across text nodes:** Faculty names in `<h4>` are split into first name, middle initial, and last name as separate text nodes with surrounding whitespace. Must join all text nodes and strip.
- **Empty `<markdown></markdown>` tags:** Some faculty cards use `<markdown></markdown>` instead of a `<p>` for research areas or bio. Parser must return `None` rather than crashing.
- **Verbose and inconsistent designations:** Titles like "Professor and Rahul Bajaj Chair Professor" or "Professor (Currently on Deputation to NCBS Bengaluru)" — normalization should extract a clean rank (Professor / Associate Professor / Assistant Professor) separately if needed downstream.
- **Trailing `\n` in email divs:** The `.email` div contains a trailing newline inside the text — strip required.
- **Multi-department faculty:** Some faculty appear on multiple department listing pages (same person, same profile URL). Deduplication by `item_url` (the SQLite primary key) handles this correctly — no duplicate rows will be created.
- **Department overview sidebar inconsistency:** Biology uses `ul.event-cards-aside` for events in its aside; Physics replaces it entirely with a freeform rich-text sidebar containing external links to third-party seminar pages (Google Sites, personal faculty websites). A parser targeting Biology's aside cannot be assumed to work on other department overview pages.
- **`/events/` listing is Vue.js rendered:** The main events hub is JS-only. Event detail pages at `/events/{id}/slug` are server-rendered and usable for enrichment, but require item URLs to be discovered from another surface.
- **News dates have no `datetime` attribute:** Dates on `/news?category=events` are plain text ("Posted on Jun 15, 2026") — require string parsing. By contrast, `/announcements/` uses a proper `time[datetime]` attribute.
- **Primary scraping target `/news?category=events` shows ~15 records per page with no pagination** — but `?archived=true&category=events` exists for historical records.
