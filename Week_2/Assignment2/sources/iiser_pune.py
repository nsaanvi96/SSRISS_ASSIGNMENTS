"""
sources/iiser_pune.py — IISER Pune events source adapter.

Exposes:
    SOURCE       — config dict consumed by src/runner.py
    parse_items  — extracts raw records from listing HTML
    normalize_item — converts raw record to shared schema
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# ── Constants ─────────────────────────────────────────────────────────────────

BASE_URL = "https://www.iiserpune.ac.in"
LISTING_URL = f"{BASE_URL}/news?category=events"
SOURCE_NAME = "iiserpune_events"
IST = timezone(timedelta(hours=5, minutes=30))


# ── Parser ────────────────────────────────────────────────────────────────────

def parse_items(html: str, base_url: str) -> list[dict]:
    """
    Extract raw event records from the IISER Pune events listing page.
    Returns one dict per event card — values are exactly as they appear
    on the page, no normalization applied here.
    """
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("li.news-card")

    items = []
    for card in cards:
        title_el = card.select_one("h2.news-title a")
        title = title_el.get_text(strip=True) if title_el else None

        href = title_el.get("href") if title_el else None
        item_url = urljoin(base_url, href) if href else None

        date_el = card.select_one(".news-date")
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


# ── Normalizer ────────────────────────────────────────────────────────────────

def _parse_date(date_raw: str | None) -> str | None:
    """
    Convert raw date string to ISO-8601 with IST offset.
    Expected input: "Posted on Sep 10, 2026" or "Sep 10, 2026"
    Returns None if parsing fails.
    """
    if not date_raw:
        return None

    text = date_raw.replace("Posted on", "").strip()

    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            parsed = datetime.strptime(text, fmt).replace(tzinfo=IST)
            return parsed.isoformat()
        except ValueError:
            continue

    return None


def normalize_item(raw_item: dict, fetched_at: str, http_status: int) -> dict:
    """
    Convert a raw parsed item into the shared output schema.
    This is the only function that knows about IISER-specific quirks
    (date format, missing fields, IST timezone assumption, etc.)
    """
    speaker_raw = raw_item.get("speaker_raw")

    return {
        "source_name":   SOURCE_NAME,
        "source_url":    LISTING_URL,
        "item_url":      raw_item.get("item_url"),
        "item_type":     "event",
        "title":         raw_item.get("title"),
        "event_start":   _parse_date(raw_item.get("date_raw")),
        "event_end":     None,
        "location":      raw_item.get("location_raw"),
        "speakers":      [speaker_raw] if speaker_raw else [],
        "organizations": [],
        "raw_text":      raw_item.get("raw_text"),
        "fetched_at":    fetched_at,
        "http_status":   http_status,
    }


# ── Source config ─────────────────────────────────────────────────────────────
# This dict is what runner.py consumes — everything the runner needs
# to collect from this source is declared here.

SOURCE = {
    "name":        SOURCE_NAME,
    "listing_url": LISTING_URL,
    "base_url":    BASE_URL,
    "item_type":   "event",
    "parser":      parse_items,
    "normalizer":  normalize_item,
    # "max_items": 10,  # uncomment to cap records during development
}
