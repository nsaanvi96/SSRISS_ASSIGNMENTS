"""
sources/iiser_pune.py — IISER Pune events source adapter.

Exposes:
    SOURCE         — config dict consumed by src/runner.py
    parse_items    — extracts raw records from listing HTML
    parse_detail   — extracts enrichment fields from a detail page
    merge          — combines listing + detail records
    normalize_item — converts raw record to shared schema
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# ── Constants ─────────────────────────────────────────────────────────────────

BASE_URL    = "https://www.iiserpune.ac.in"
LISTING_URL = f"{BASE_URL}/news?category=events"
SOURCE_NAME = "iiserpune_events"
IST         = timezone(timedelta(hours=5, minutes=30))


# ── Listing parser ────────────────────────────────────────────────────────────

def parse_items(html: str, base_url: str) -> list[dict]:
    """
    Extract raw event records from the IISER Pune events listing page.
    Returns one dict per li.news-card — values exactly as on the page,
    no normalization applied here.
    """
    soup  = BeautifulSoup(html, "lxml")
    cards = soup.select("li.news-card")

    items = []
    for card in cards:
        title_el = card.select_one("h2.news-title a")
        title    = title_el.get_text(strip=True) if title_el else None

        href     = title_el.get("href") if title_el else None
        item_url = urljoin(base_url, href) if href else None

        date_el  = card.select_one(".news-date")
        date_raw = date_el.get_text(strip=True) if date_el else None

        raw_text = card.get_text(" ", strip=True)

        items.append({
            "title":        title,
            "item_url":     item_url,
            "date_raw":     date_raw,
            "speaker_raw":  None,   # not available on listing page
            "location_raw": None,   # not available on listing page
            "raw_text":     raw_text,
        })

    return items


# ── Detail parser ─────────────────────────────────────────────────────────────

def parse_detail(html: str, item_url: str) -> dict:
    """
    Extract enrichment fields from a /news/post/... detail page.

    Fields available:
        title            — same as listing (sanity check)
        published_at_raw — time[datetime] value; format "2026-06-15 15:14"
        description      — full article body text
        categories       — list of category labels

    Not available as structured fields:
        speaker, location — buried in prose only; not extracted here.
    """
    soup = BeautifulSoup(html, "lxml")

    title_el         = soup.select_one("h1.post-title span")
    title            = title_el.get_text(strip=True) if title_el else None

    time_el          = soup.select_one("time[datetime]")
    published_at_raw = time_el["datetime"] if time_el else None

    desc_el          = soup.select_one("div.news-post-content")
    description      = desc_el.get_text(separator=" ", strip=True) if desc_el else None

    category_els     = soup.select("a.post-category span")
    categories       = [el.get_text(strip=True) for el in category_els]

    return {
        "item_url":         item_url,
        "title":            title,
        "published_at_raw": published_at_raw,
        "description":      description,
        "categories":       categories,
    }


# ── Merger ────────────────────────────────────────────────────────────────────

def merge(listing_item: dict, detail_item: dict) -> dict:
    """
    Combine a listing record with enrichment from its detail page.
    Listing fields are the base; detail fills in the gaps.
    If a detail fetch failed, runner passes an empty dict — listing kept as-is.
    """
    merged = listing_item.copy()
    merged["published_at_raw"] = detail_item.get("published_at_raw")
    merged["description"]      = detail_item.get("description")
    merged["categories"]       = detail_item.get("categories", [])
    return merged


# ── Normalizer ────────────────────────────────────────────────────────────────

def _parse_date(date_str: str | None) -> str | None:
    """
    Parse dates from two possible formats:
      Detail page time[datetime]: "2026-06-15 15:14"
      Listing page text:          "Posted on Jun 15, 2026"
    Returns ISO-8601 with IST offset, or None if unparseable.
    """
    if not date_str:
        return None

    # Detail page format (more precise — prefer when available)
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        return parsed.replace(tzinfo=IST).isoformat()
    except ValueError:
        pass

    # Listing page fallback
    text = date_str.replace("Posted on", "").strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=IST).isoformat()
        except ValueError:
            continue

    return None


def normalize_item(raw_item: dict, fetched_at: str, http_status: int) -> dict:
    """
    Convert a raw (possibly detail-enriched) item into the shared output schema.
    This is the only function that knows about IISER-specific quirks.
    """
    speaker_raw = raw_item.get("speaker_raw")

    # Prefer published_at_raw from detail page; fall back to listing date_raw
    date_str = raw_item.get("published_at_raw") or raw_item.get("date_raw")

    return {
        "source_name":   SOURCE_NAME,
        "source_url":    LISTING_URL,
        "item_url":      raw_item.get("item_url"),
        "item_type":     "event",
        "title":         raw_item.get("title"),
        "event_start":   _parse_date(date_str),
        "event_end":     None,
        "location":      raw_item.get("location_raw"),
        "speakers":      [speaker_raw] if speaker_raw else [],
        "organizations": [],
        "description":   raw_item.get("description"),    # from detail page
        "categories":    raw_item.get("categories", []), # from detail page
        "raw_text":      raw_item.get("raw_text"),
        "fetched_at":    fetched_at,
        "http_status":   http_status,
    }


# ── Source config ─────────────────────────────────────────────────────────────
# This dict is what runner.py consumes.
# "detail" and "merger" are optional — runner skips enrichment if absent.

SOURCE = {
    "name":        SOURCE_NAME,
    "listing_url": LISTING_URL,
    "base_url":    BASE_URL,
    "item_type":   "event",
    "parser":      parse_items,
    "normalizer":  normalize_item,
    "detail":      parse_detail,  # optional: runner fetches each item's detail page
    "merger":      merge,         # optional: combines listing + detail dicts
    # "max_items":  10,           # uncomment to cap listing records during dev
    # "max_detail":  5,           # uncomment to limit detail fetches (saves requests)
}
