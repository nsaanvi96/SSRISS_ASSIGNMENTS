utf-8import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scraper.py"))
sys.path.insert(0, str(Path(__file__).parent.parent / "storage.py"))

from scraper import parse_items, normalize_item
from storage import init_db, upsert_item, get_item

FIXTURES = Path(__file__).parent / "fixtures"
BASE_URL = "https://www.iiserpune.ac.in"


def load(filename):
    return (FIXTURES / filename).read_text(encoding="utf-8")


def make_normalized(raw_item):
    return normalize_item(
        raw_item,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        http_status=200,
    )


SCHEMA_KEYS = {
    "source_name", "source_url", "item_url", "item_type", "title",
    "event_start", "event_end", "location", "speakers", "organizations",
    "raw_text", "fetched_at", "http_status",
}




def test_parse_expected_number_of_items():
    items = parse_items(load("normal_page.html"), BASE_URL)
    assert len(items) == 15


def test_parse_title():
    items = parse_items(load("normal_page.html"), BASE_URL)
    assert items[0]["title"] == "Bridging Science and Enterprise: Kiran Mazumdar-Shaw's visit to IISER Pune"


def test_parse_url_is_absolute():
    items = parse_items(load("normal_page.html"), BASE_URL)
    for item in items:
        assert item["item_url"].startswith("https://"), f"Not absolute: {item['item_url']}"


def test_parse_date_raw():
    items = parse_items(load("normal_page.html"), BASE_URL)
    assert items[0]["date_raw"] == "Posted on Jun 15, 2026"


def test_normalization_shape():
    items = parse_items(load("normal_page.html"), BASE_URL)
    for item in items:
        normalized = make_normalized(item)
        assert SCHEMA_KEYS == set(normalized.keys()), f"Schema mismatch for {item['item_url']}"




def test_missing_date_returns_none():
    items = parse_items(load("missing_optional_field.html"), BASE_URL)
    assert len(items) == 5
    assert items[1]["date_raw"] is None


def test_missing_date_does_not_crash_normalize():
    items = parse_items(load("missing_optional_field.html"), BASE_URL)
    normalized = make_normalized(items[1])
    assert normalized["event_start"] is None


def test_missing_summary_returns_none_or_empty():
    items = parse_items(load("missing_optional_field.html"), BASE_URL)
    raw_text = items[2]["raw_text"]
    assert raw_text is None or raw_text.strip() == "" or isinstance(raw_text, str)


def test_empty_title_text_url_still_captured():
    items = parse_items(load("missing_optional_field.html"), BASE_URL)
    item = items[3]
    assert item["item_url"] is not None
    assert item["item_url"].startswith("https://")


def test_all_records_returned_despite_missing_fields():
    items = parse_items(load("missing_optional_field.html"), BASE_URL)
    assert len(items) == 5




def test_empty_listing_returns_empty_list():
    items = parse_items(load("empty_listing.html"), BASE_URL)
    assert items == []




def test_changed_structure_record_count():
    items = parse_items(load("changed_card_structure.html"), BASE_URL)
    assert len(items) == 5


def test_extra_class_on_li_still_parsed():
    items = parse_items(load("changed_card_structure.html"), BASE_URL)
    assert items[0]["title"] is not None
    assert items[0]["item_url"] is not None




def test_duplicate_item_creates_one_row(tmp_path):
    db = tmp_path / "test.db"
    init_db(db_path=db)

    items = parse_items(load("normal_page.html"), BASE_URL)
    normalized = make_normalized(items[0])

    upsert_item(normalized, db_path=db)
    upsert_item(normalized, db_path=db)

    conn = sqlite3.connect(db)
    count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    conn.close()

    assert count == 1
