# IISER Pune — Surface Recon Notes (Assignment 2)

## A. Domain and access

- **Main domain:** https://www.iiserpune.ac.in
- **robots.txt:** checked https://www.iiserpune.ac.in/robots.txt — it's literally just
  `User-agent: *` and nothing else. No Disallow, no Crawl-delay, no Sitemap line. So
  basically no restrictions anywhere on the site.
- **Sitemap:** `/sitemap` exists but it's just a normal HTML page for humans (logo, nav
  links, the works) — not an actual sitemap. Tried `/sitemap.xml` directly and got a
  clean 404. So no real XML sitemap here.
- **RSS/Atom:** found this in the `<head>` of the news/events pages:
  `<link rel="alternate" type="application/rss+xml" href="/news/feed">` — so they clearly
  meant to have a feed. But hitting `/news/feed` gives a 500 error every time, reload and
  all. So it exists on paper but it's just broken right now. Worth checking again later,
  would be the best option if it ever starts working.

## B. Candidate surfaces

Checked one page for each thing the assignment asks about — events, seminars, news/
announcements, research.

### Events → `/news?category=events`
Plain HTML, confirmed by view-source (content's actually in the response, not JS junk).
Each card is `<li class="news-card"><article>...</article></li>` with an image, category
tag, title (`<h2 class="news-title">`), and a "Posted on ..." date. Links out to a detail
page like `/news/post/<slug>/<id>`. There's a "View News Archives" button for older stuff
but didn't dig into exactly how pagination works past that. ~15-18 cards showing before
you hit archives.

**Good surface** — one clean repeated structure, everything we need is right there in
the HTML.

### Seminars/talks → `/events/seminars`
This one's a trap. Looks totally normal in the browser — real seminar titles, real dates,
e.g. "Nanostructured semiconductors..." on Sept 10 2026. But that's only because the
browser runs the JS for you automatically. Checked view-source (i.e. what `requests.get()`
actually sees) and it's all just Vue placeholders: `{{Item.Title}}`, `{{Item.Category}}`,
`{{Item.StartDateTime}}`, even pagination is templated (`v-for="i in NoOfPages"`). Same
deal for the bare `/events` page and all its sibling tabs (colloquia, conferences,
workshops, etc.) — same Vue app underneath.

**Not usable** — the data's real but only shows up after JS runs, and we're not allowed
to do browser automation this week.

### News/announcements → `/announcements`
Plain HTML, simple listing of short dated one-liners (postdoc openings, appointments,
that kind of thing). Some link out externally. Thinner content than the events page —
just a date + title mostly, no excerpt.

**Secondary option** — fine but not as rich as the events surface.

### Research → `/news?category=research-news`
Same template as the events page basically — checked view-source by searching for
"Ismaiel" from a headline I could see, and it showed up straight in the raw HTML (in the
URL, the title, the summary). One small extra: cards here can have more than one category
tag at once (like "Research News" + "In the Media"), and there's a department filter
dropdown that events didn't have.

**Good surface** — same reliable structure as events.

## C. Which one to go with

Going with **`/news?category=events`** for Week 1.

- **Why:** it's basically a built-in aggregator — one page, all the campus events stuff,
  no need to go department-hunting across the site.
- **Plain HTML or not:** confirmed plain HTML via view-source. That's the whole reason
  it beats the seminars page, which looks the same to a human but is JS-only underneath.
- **Access stuff:** robots.txt is wide open so nothing's actually blocked, but still
  gonna use a proper User-Agent + timeout + not hammer it, just to be decent about it.
  Keep an eye on `/news/feed` too — if that 500 ever gets fixed, switch to that instead.
- **Fields I can actually pull from the listing:**
  - title (`<h2 class="news-title">`, also sits in a `title=` attr)
  - link to detail page
  - date ("Posted on ...")
  - category tag(s) — can be more than one
  - image + alt text
  - speaker name: **not available on listing page, would need the detail page**
