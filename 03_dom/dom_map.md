# DOM Mapping — Assignment 3

## Part A: Fictional Fixture (`fixture_events.html`)

### Record (event container)
```
Field: Record container
HTML tag: div
Important class/id/attribute: class="event-card"
Parent: <main id="events">
Relevant children: h2.title, time, span.speaker, span.location
How I know this belongs to one event record: it repeats once per event and is the smallest element that contains all of a single event's fields — going up (main) would group multiple events, going down (h2) would miss date/speaker/location.
```

### Title
```
Field: Title
HTML tag: h2 (visible text is inside the nested <a>)
Important class/id/attribute: class="title" on the h2
Parent: div.event-card
Relevant children: a
How I know this belongs to one event record: it's a direct child of one event-card, and its text is that event's name, not shared across cards.
```

### URL
```
Field: URL
HTML tag: a
Important class/id/attribute: href (relative path, no class on the <a>)
Parent: h2.title
Relevant children: none (leaf element)
How I know this belongs to one event record: it's the anchor nested inside this specific event-card's title, so its href points to that event's own detail page. Note: relative URL, will need to be joined with base domain later.
```

### Date
```
Field: Date
HTML tag: time
Important class/id/attribute: no class; datetime attribute (e.g. datetime="2026-09-10")
Parent: div.event-card
Relevant children: none (leaf element)
How I know this belongs to one event record: only date-like element in the card; the datetime attribute is machine-readable, the inner text is human-readable — same event, two representations.
```

### Speaker
```
Field: Speaker
HTML tag: span
Important class/id/attribute: class="speaker"
Parent: div.event-card
Relevant children: none (leaf element)
How I know this belongs to one event record: direct child of the event-card, positioned between date and location, text is a person's name/title.
Note: this field is OPTIONAL — absent entirely (not empty, just missing) on the "Open Source in Academia" card. Extraction code must guard against None, e.g. speaker_el.get_text() if speaker_el else None.
```

### Location
```
Field: Location
HTML tag: span
Important class/id/attribute: class="location"
Parent: div.event-card
Relevant children: none (leaf element)
How I know this belongs to one event record: direct child of the event-card, last field in the card, text is a place name; present on every card (unlike speaker).
```

---

## Part B: Real Surface — IISER Pune `/news`

Source: `view-source:https://www.iiserpune.ac.in/news`
Note: page also exposes an RSS feed at `/news/feed` (found in `<head>`), worth flagging back in Assignment 2 — a feed may be a lower-complexity surface than scraping this listing directly.

Focus is the main list, `<ul class="news-cards">` (not the `news-cards-pinned` list above it, which is a curated/featured subset).

### Record (news item container)
```
Field: Record container
HTML tag: li (article is nested one level inside it)
Important class/id/attribute: class="news-card" (article inside has no class)
Parent: <ul class="news-cards">
Relevant children: article > div.image, div.text (containing category-tag(s), h2.news-title, div.news-date, div.summary)
How I know this belongs to one event record: li.news-card repeats once per news item inside ul.news-cards, and is the smallest element containing everything about one item — image, title, date, summary, category tags. The nested <article> alone would also work, but li is the actual repeating unit in the list.
```

### Title
```
Field: Title
HTML tag: h2 (text + href in nested <a>)
Important class/id/attribute: class="news-title"
Parent: article > div.text
Relevant children: a
How I know this belongs to one event record: one h2.news-title per li.news-card, text matches that specific article's headline.
```

### URL
```
Field: URL
HTML tag: a
Important class/id/attribute: href (absolute-looking path like /news/post/<slug>/<id>, but still relative to domain — no scheme/host)
Parent: h2.news-title (also duplicated as the image-anchor <a> around the thumbnail)
Relevant children: none (leaf element)
How I know this belongs to one event record: href inside this card's own h2.news-title points to that specific article's detail page; the same URL also wraps the thumbnail image earlier in the card.
```

### Date
```
Field: Date
HTML tag: div
Important class/id/attribute: class="news-date"
Parent: article > div.text
Relevant children: none (leaf element) — plain text only, e.g. "Posted on Jul 01, 2026"
How I know this belongs to one event record: one per card, directly under div.text, text is a date.
Note: unlike the fixture's <time datetime="...">, there is NO machine-readable datetime attribute here — only display text ("Posted on Jul 01, 2026"). This will need explicit string parsing during normalization (Assignment 6), since there's no shortcut attribute to read.
```

### Category tag(s)
```
Field: Category tag
HTML tag: a
Important class/id/attribute: class="category-tag" (href like /news?category=events)
Parent: article > div.text
Relevant children: none (leaf element)
How I know this belongs to one event record: appears directly under this card's div.text, before the title.
Note: this field is OPTIONAL and can be MULTIPLE — some cards have zero category-tags (e.g. the Yuva Sangam and NCIKSST-style items with none), some have one, some have two (e.g. "Research work from Dr. Ismaiel's Group" has both Research News and In the Media). Extraction should use select() / find_all() to return a list, not select_one(), since there can be more than one.
```

### Summary
```
Field: Summary
HTML tag: div
Important class/id/attribute: class="summary"
Parent: article > div.text
Relevant children: none (leaf element, plain text, often truncated with "...")
How I know this belongs to one event record: one per card, directly under div.text, appears after the date; text is a short excerpt of that specific article.
Note: present on the main /news listing cards but absent on the pinned-articles cards (those omit the .summary div entirely) — another optional-field case.
```

### Speaker
```
Field: Speaker
Not available on listing page.
May require visiting the detail page.
(Confirmed in Assignment 2 surface notes — speaker name is not present anywhere in the /news?category=events listing HTML.)
```

### Location
```
Field: Location
Not available on listing page.
May require visiting the detail page.
(Not mentioned in Assignment 2 surface notes either — no location/venue field appears in the listing HTML for any card checked so far.)
```

---

## Robustness note (for Assignment 4 later)

The real page already shows several of the "brittleness" patterns Assignment 4 asks you to anticipate:
- Record boundary is nested one level (li > article) rather than flat, unlike the fixture's flat div.event-card.
- No shared machine-readable date attribute (fixture had datetime=; this page doesn't).
- Category tags are 0-to-many, not always-1, so selector code must expect a list.
- Pinned-articles cards and main-listing cards share li.news-card/article structure but differ slightly in fields present (no .summary on pinned cards) — same class name, inconsistent shape.
