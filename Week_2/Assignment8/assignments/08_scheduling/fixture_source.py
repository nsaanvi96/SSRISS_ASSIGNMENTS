"""
assignments/08_scheduling/fixture_source.py
Local fixture source for Assignment 8.

Reads fixture HTML from disk so the scheduler demo runs without any
network access. Reuses the existing normalize_item from iiser_pune.py
to prove the template is genuinely generic: the scheduler doesn't care
whether data comes from a live site or a fixture file.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "sources"))

from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Reuse IISER Pune's normalizer — proves the runner is source-agnostic.
from iiser_pune import normalize_item

# ── Fixture HTML path ─────────────────────────────────────────────────────────

_FIXTURE_PATH = Path(__file__).parent / "fixture_events.html"

FIXTURE_LISTING_URL = "file://fixture_events.html"
FIXTURE_BASE_URL    = "https://fixture.example.org"
FIXTURE_SOURCE_NAME = "fixture_events"


# ── Parser ────────────────────────────────────────────────────────────────────

def parse_fixture_items(html: str, base_url: str) -> list[dict]:
    """
    Parse event cards from the local fixture HTML.
    Uses the same card structure as the IISER Pune listing so the
    existing iiser_pune.py normalizer works without modification.
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
            "speaker_raw":  None,
            "location_raw": None,
            "raw_text":     raw_text,
        })

    return items


# ── Fetch from disk ───────────────────────────────────────────────────────────

def fetch_fixture(url: str) -> tuple[str, int]:
    """
    Reads fixture HTML from disk. Returns (html, 200).
    Signature matches what runner.py expects from fetch().
    """
    html = _FIXTURE_PATH.read_text(encoding="utf-8")
    return html, 200


# ── Source config ─────────────────────────────────────────────────────────────
# runner.py normally calls src/fetch.py; we override "fetcher" here so the
# runner uses our disk reader instead — no network involved.

SOURCE = {
    "name":        FIXTURE_SOURCE_NAME,
    "listing_url": FIXTURE_LISTING_URL,
    "base_url":    FIXTURE_BASE_URL,
    "item_type":   "event",
    "parser":      parse_fixture_items,
    "normalizer":  normalize_item,
    "fetcher":     fetch_fixture,   # optional key — runner checks for this
}
