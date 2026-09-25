utf-8import copy
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scraper import BASE_URL, parse_items, normalize_item
from storage import DB_PATH, init_db, upsert_item, get_item


def load_normalized_items() -> list[dict]:
    html_path = Path(__file__).parent / "sample_response.html"
    html = html_path.read_text(encoding="utf-8")

    raw_items = parse_items(html, base_url=BASE_URL)
    fetched_at = datetime.now(timezone.utc).isoformat()

    return [normalize_item(item, fetched_at=fetched_at, http_status=200) for item in raw_items]


def run_once(items: list[dict], label: str) -> None:
    counts = {"new": 0, "unchanged": 0, "updated": 0}
    for item in items:
        result = upsert_item(item)
        counts[result] += 1

    print(f"{label}: {len(items)} total -> "
          f"{counts['new']} new, {counts['unchanged']} unchanged, {counts['updated']} updated")


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()

    init_db()

    items = load_normalized_items()

    run_once(items, "RUN 1")
    run_once(items, "RUN 2")

    modified_items = copy.deepcopy(items)
    target_url = modified_items[0]["item_url"]
    modified_items[0]["title"] = modified_items[0]["title"] + " (UPDATED)"

    run_once(modified_items, "RUN 3 (one item modified)")

    stored = get_item(target_url)
    print(f"\nStored record for modified item ({target_url}):")
    print(f"  title:         {stored['title']}")
    print(f"  first_seen_at: {stored['first_seen_at']}")
    print(f"  last_seen_at:  {stored['last_seen_at']}")


if __name__ == "__main__":
    main()
