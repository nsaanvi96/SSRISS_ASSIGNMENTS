# Assignment 2 — URL Scope Filter: Test Cases

## Source Configuration Used

```python
source_config = {
    "allowed_hostname": "www.iima.ac.in",
    "allowed_path_prefixes": [
        "/the-institute/events",
        "/news",
        "/research/publications",
    ],
    "excluded_path_prefixes": [
        "/calendar",
        "/search",
        "/filter",
        "/login",
        "/user",
        "/admin",
        "/sites/default/files",
        "/tag",
        "/taxonomy",
    ],
    "allow_external": False,
    "strip_query_params": False,
    "ignored_query_params": [
        "utm_source", "utm_medium", "utm_campaign",
        "utm_term", "utm_content",
        "fbclid", "gclid", "ref", "source",
    ],
}
```

---

## Test Cases

### Category 1 — Valid Allowed URLs

| # | URL | Allowed? | Why? |
|---|-----|----------|------|
| 1 | `https://www.iima.ac.in/the-institute/events/annual-management-retreat-2026` | ✅ Yes | Same host. Path starts with `/the-institute/events`. Not excluded. Not binary. Not a duplicate. |
| 2 | `https://www.iima.ac.in/news/iima-ranked-1-in-india-2026` | ✅ Yes | Same host. Path starts with `/news`. Not excluded. Not binary. |
| 3 | `https://www.iima.ac.in/research/publications/working-paper-2026-01` | ✅ Yes | Same host. Path starts with `/research/publications`. All checks pass. |
| 4 | `https://www.iima.ac.in/the-institute/events/seminar?page=2` | ✅ Yes | `page` is not a tracking param, it is a genuine pagination param. Treated as a distinct URL from `?page=1`. |

---

### Category 2 — External / Same-Site Boundary

| # | URL | Allowed? | Why? |
|---|-----|----------|------|
| 5 | `https://www.eventbrite.com/e/iima-annual-retreat-tickets-123456` | ❌ No | Different hostname (`eventbrite.com` ≠ `www.iima.ac.in`) and `allow_external` is `False`. |
| 6 | `https://twitter.com/IIMAhmedabad/status/1776543210987654321` | ❌ No | Different hostname (`twitter.com`). `allow_external` is `False`. |
| 7 | `https://alumni.iima.ac.in/events/homecoming-2026` | ❌ No | Subdomain (`alumni.iima.ac.in`) is treated as a different hostname. `allow_external` is `False`. |

---

### Category 3 — Excluded Path Prefixes

| # | URL | Allowed? | Why? |
|---|-----|----------|------|
| 8 | `https://www.iima.ac.in/login?destination=/events` | ❌ No | Path `/login` matches excluded prefix `/login`. Authentication pages have no crawlable content. |
| 9 | `https://www.iima.ac.in/search?q=conference` | ❌ No | Path `/search` is excluded. Search URLs generate infinite unique URLs with no stable content. |
| 10 | `https://www.iima.ac.in/calendar/2026-10` | ❌ No | Path `/calendar` is excluded. Calendar pages create a combinatorial explosion (year × month × day × view). |
| 11 | `https://www.iima.ac.in/filter/events?type=seminar&month=10` | ❌ No | Path `/filter` is excluded. Filter pages create infinite URL spaces via facet combinations. |
| 12 | `https://www.iima.ac.in/admin/content` | ❌ No | Path `/admin` is excluded. Admin pages require auth and contain no public event content. |

---

### Category 4 — Binary / Non-HTML Resources

| # | URL | Allowed? | Why? |
|---|-----|----------|------|
| 13 | `https://www.iima.ac.in/sites/default/files/brochure.pdf` | ❌ No | Extension `.pdf` is in the binary extensions blocklist. Also hits the `/sites/default/files` excluded prefix. Blocked at both layers. |
| 14 | `https://www.iima.ac.in/the-institute/events/agenda.pdf` | ❌ No | Extension `.pdf` is binary even though the path starts with an allowed prefix. Extension check runs *after* prefix check. |
| 15 | `https://www.iima.ac.in/news/report.docx` | ❌ No | Extension `.docx` is a binary document format. |
| 16 | `https://www.iima.ac.in/the-institute/events/banner.jpg` | ❌ No | Extension `.jpg` is an image asset, not a content page. |

---

### Category 5 — Out-of-Scope Internal Pages

| # | URL | Allowed? | Why? |
|---|-----|----------|------|
| 17 | `https://www.iima.ac.in/about/leadership` | ❌ No | Same host but path `/about/leadership` does not start with any allowed prefix. Path-prefix allowlist is enforced. |
| 18 | `https://www.iima.ac.in/programmes/pgp` | ❌ No | Path `/programmes/pgp` not in `allowed_path_prefixes`. Rejected by allowlist. |

---

### Category 6 — URL Canonicalization & Deduplication

| # | URL | Allowed? | Why? |
|---|-----|----------|------|
| 19 | `https://www.iima.ac.in/the-institute/events/retreat-2026` | ✅ Yes (1st visit) | First time seen. Passes all checks. Canonical form stored in visited set. |
| 20 | `https://www.iima.ac.in/the-institute/events/retreat-2026#agenda` | ❌ No (duplicate) | Fragment `#agenda` is stripped during canonicalization. Canonical URL is identical to #19. Rejected as duplicate. |
| 21 | `https://www.iima.ac.in/the-institute/events/retreat-2026?utm_source=email` | ❌ No (duplicate) | `utm_source` is an ignored tracking parameter. After stripping it, canonical URL is identical to #19. Rejected as duplicate. |
| 22 | `https://www.iima.ac.in/news/iima-ranked-1?utm_source=email&utm_campaign=weekly&fbclid=abc123` | ❌ No (duplicate) | All three tracking params (`utm_source`, `utm_campaign`, `fbclid`) are ignored. Canonical URL matches previously-seen clean URL. |
| 23 | `https://www.iima.ac.in/the-institute/events?page=1` | ✅ Yes | `page` is NOT in `ignored_query_params`. Canonical URL retains `?page=1`. Treated as unique. |
| 24 | `https://www.iima.ac.in/the-institute/events?page=2` | ✅ Yes | `page=2` gives a different canonical from `page=1`. Treated as a distinct URL. |

---

### Category 7 — Scheme Checks

| # | URL | Allowed? | Why? |
|---|-----|----------|------|
| 25 | `http://www.iima.ac.in/the-institute/events/retreat-2026` | ✅ Yes | `http` scheme is permitted (alongside `https`). Same host, valid path prefix. |
| 26 | `ftp://www.iima.ac.in/files/report.pdf` | ❌ No | `ftp` scheme is not `http` or `https`. Rejected at scheme check. |
| 27 | `mailto:events@iima.ac.in` | ❌ No | `mailto` scheme is not `http` or `https`. |
| 28 | `javascript:void(0)` | ❌ No | `javascript` scheme is not `http` or `https`. Common in onclick-injected `href` values. |

---

## Concepts Demonstrated

| Concept | Where Applied |
|---------|--------------|
| **Crawl frontier** | `UrlScopeFilter._visited` set; only URLs passing all checks enter the frontier |
| **Allowlist rules** | `allowed_hostname` + `allowed_path_prefixes` config keys |
| **Same-site vs external** | Hostname comparison + `allow_external` flag (Cases 5-7) |
| **Path prefixes** | `allowed_path_prefixes` + `excluded_path_prefixes` (Cases 8-12, 17-18) |
| **URL canonicalization** | `_canonicalize()` using `urllib.parse.urlsplit` / `urlunsplit` |
| **Query parameters** | `ignored_query_params` stripped before dedup; `strip_query_params` option |
| **Fragments** | Always removed in `_canonicalize()` — `fragment = ""` |
| **Visited URLs** | Canonical URL stored in `visited` set; duplicates rejected (Cases 19-24) |
| **Binary extensions** | `_BINARY_EXTENSIONS` set checked against path extension (Cases 13-16) |
| **Calendar/search/filter explosion** | Excluded via `excluded_path_prefixes` (Cases 9-11) |
| **Infinite URL spaces** | Search + filter + calendar all blocked; tracking params collapsed |

---

## urllib.parse Functions Used

| Function | Used For |
|----------|----------|
| `urllib.parse.urlsplit(url)` | Parse URL into scheme, netloc, path, query, fragment |
| `urllib.parse.urlunsplit(parts)` | Reconstruct canonical URL from parts |
| `urllib.parse.parse_qsl(query)` | Decode query string into list of (key, value) pairs |
| `urllib.parse.urlencode(params)` | Re-encode filtered query params back to string |
| `urllib.parse.urljoin(base, href)` | Used in `HtmlListingAdapter` to resolve relative links |
| `.hostname` attribute | Extract lowercased hostname from `SplitResult` |
| `.path` attribute | Extract URL path for prefix checks |
| `.query` attribute | Extract raw query string |
| `.fragment` attribute | (Not used directly; always set to `""` in reconstruction) |

---

## Checkpoint

> **Your aggregator should not blindly follow every link found on the page.**
>
> The `UrlScopeFilter` enforces a clear boundary before any URL reaches the
> collection pipeline:
>
> 1. Wrong scheme → out
> 2. Wrong domain (external) → out
> 3. Path not in allowlist → out
> 4. Path in exclusion list → out
> 5. Binary file extension → out
> 6. Already visited (deduplicated) → out
> 7. **Only then** → URL enters the frontier
