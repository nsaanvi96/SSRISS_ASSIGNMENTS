# Assignment 4 — Selector Workbook

## Part 1 — Fictional Fixture (`assignments/03_dom/fixture_events.html`)

| Field    | CSS selector                                                | XPath                                                                 |
|----------|--------------------------------------------------------------|------------------------------------------------------------------------|
| Record   | `.event-card`                                                | `//div[@class="event-card"]`                                          |
| Title    | `.event-card .title`                                          | `//div[@class="event-card"]//h2[@class="title"]`                      |
| URL      | `.event-card .title a`                                         | `//div[@class="event-card"]//h2[@class="title"]/a/@href`             |
| Date     | `.event-card time`                                             | `//div[@class="event-card"]//time`                                    |
| Speaker  | `.event-card .speaker`                                         | `//div[@class="event-card"]//span[@class="speaker"]`                   |
| Location | `.event-card .location`                                        | `//div[@class="event-card"]//span[@class="location"]`                  |

> Note (Date): use the `datetime` attribute (`time_el.get('datetime')`), not the visible text — more reliable to parse downstream.

---

## Part 2 — IISER Pune (real surface from Assignment 2)

Surface used: https://www.iiserpune.ac.in/news?category=events

| Field    | CSS selector | XPath |
|----------|--------------|-------|
| Record   | `li.news-card` | `//li[@class="news-card"]` |
| Title    | `li.news-card h2.news-title a` | `//li[@class="news-card"]//h2[@class="news-title"]/a` |
| URL      | `li.news-card h2.news-title a` (then `.get('href')`) | `//li[@class="news-card"]//h2[@class="news-title"]/a/@href` |
| Date     | `li.news-card .news-date` | `//li[@class="news-card"]//div[@class="news-date"]` |
| Speaker  | Not available on listing page. May require visiting the detail page. | Not available on listing page. May require visiting the detail page. |
| Location | Not available on listing page. May require visiting the detail page. | Not available on listing page. May require visiting the detail page. |

Note: the date here has no `datetime` attribute (unlike the fictional fixture) — it's plain text like "Posted on Jun 15, 2026" inside `div.news-date`, so it'll need parsing later at normalization, not attribute extraction.

---

## Part 3 — Robustness Challenge

Fixture modification made: I added an extra class to one of the event cards, so it became `<div class="event-card featured">`. Left the rest of the cards alone so I'd have something to compare against.

Fixture modification made: `<div class="event-card featured">` — featured class added extra.

1. **Which selectors broke?**
   The XPath selectors broke.

2. **Why did they break?**
   They broke because they were explicitly searching for a class that equals exactly "event-card" and nothing else.

3. **Which selectors survived?**
   The CSS selectors survived.

4. **How could the brittle selectors be made less position-dependent?**
   The brittle selectors can be made less position-dependent by using `contains()` — this makes the selector check whether the class contains the given string, instead of needing it to be exactly equal.
