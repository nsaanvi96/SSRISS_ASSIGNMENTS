import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from storage import init_db, upsert_item

DB_PATH = Path(__file__).parent / "data" / "pagination_test.db"

logger = logging.getLogger(__name__)


def get_next_page_url(html: str, current_url: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    link = soup.select_one("nav.pagination a.next-page")
    if not link:
        return None
    href = link.get("href", "").strip()
    if not href:
        return None
    return str(Path(current_url).parent / href)


def parse_events(html: str, source_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    records = []
    for card in soup.select("li.event-card"):
        title_tag = card.select_one("h2.title a")
        time_tag = card.select_one("time")
        speaker_tag = card.select_one("span.speaker")
        location_tag = card.select_one("span.location")

        raw_href = title_tag.get("href", "") if title_tag else ""
        item_url = urljoin("https://example-university.edu", raw_href) if raw_href else None

        speaker = speaker_tag.get_text(strip=True) if speaker_tag else None

        records.append({
            "source_name": "pagination_fixture",
            "source_url": source_url,
            "item_url": item_url,
            "item_type": "event",
            "title": title_tag.get_text(strip=True) if title_tag else None,
            "event_start": None,
            "event_end": None,
            "location": location_tag.get_text(strip=True) if location_tag else None,
            "speakers": [speaker] if speaker else [],
            "organizations": [],
            "raw_text": time_tag.get_text(strip=True) if time_tag else None,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "http_status": 200,
        })
    return records


def load_local(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def collect_listing(start_url: str, max_pages: int = 10) -> list[dict]:
    all_items = []
    visited = set()
    current_url = start_url

    while current_url and len(visited) < max_pages:
        if current_url in visited:
            logger.warning("already visited %s — stopping", current_url)
            break

        visited.add(current_url)
        logger.info("fetching page=%d url=%s", len(visited), current_url)

        html = load_local(current_url)
        page_items = parse_events(html, current_url)
        logger.info("parsed records=%d", len(page_items))

        all_items.extend(page_items)

        next_url = get_next_page_url(html, current_url)
        if next_url == current_url:
            logger.warning("next url same as current — stopping")
            break

        current_url = next_url

    logger.info("traversal complete pages=%d total_records=%d", len(visited), len(all_items))
    return all_items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    init_db(DB_PATH)

    items = collect_listing(str(Path(__file__).parent / "fixtures" / "page_1.html"))

    new_count = unchanged_count = 0
    for item in items:
        result = upsert_item(item, DB_PATH)
        if result == "new":
            new_count += 1
        else:
            unchanged_count += 1

    conn = sqlite3.connect(DB_PATH)
    (row_count,) = conn.execute("SELECT COUNT(*) FROM items").fetchone()
    conn.close()

    print(f"\ntotal collected : {len(items)}")
    print(f"new rows        : {new_count}")
    print(f"unchanged (dupe): {unchanged_count}")
    print(f"rows in DB      : {row_count}")
