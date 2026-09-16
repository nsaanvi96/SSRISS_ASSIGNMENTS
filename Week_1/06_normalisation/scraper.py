from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.iiserpune.ac.in"
TARGET_URL = f"{BASE_URL}/news?category=events"
USER_AGENT = "IISERPune-WebMonitorInternship/0.1 (educational scraping project; contact: saanvi@example.com)"
SOURCE_NAME = "iiserpune_events"
IST = timezone(timedelta(hours=5, minutes=30))


def fetch(url: str) -> str:
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Request to {url} timed out.")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"HTTP error fetching {url}: {e}")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to fetch {url}: {e}")

    return response.text


def parse_items(html: str, base_url: str) -> list[dict]:
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

        speaker_raw = None
        location_raw = None

        raw_text = card.get_text(" ", strip=True)

        items.append({
            "title": title,
            "item_url": item_url,
            "date_raw": date_raw,
            "speaker_raw": speaker_raw,
            "location_raw": location_raw,
            "raw_text": raw_text,
        })

    return items


def _parse_posted_date(date_raw: str | None) -> str | None:
    if not date_raw:
        return None

    text = date_raw.replace("Posted on", "").strip()

    try:
        parsed = datetime.strptime(text, "%b %d, %Y")
    except ValueError:
        return None

    parsed = parsed.replace(tzinfo=IST)
    return parsed.isoformat()


def normalize_item(raw_item: dict, fetched_at: str, http_status: int) -> dict:
    speaker_raw = raw_item.get("speaker_raw")
    speakers = [speaker_raw] if speaker_raw else []

    return {
        "source_name": SOURCE_NAME,
        "source_url": TARGET_URL,
        "item_url": raw_item.get("item_url"),
        "item_type": "event",
        "title": raw_item.get("title"),
        "event_start": _parse_posted_date(raw_item.get("date_raw")),
        "event_end": None,
        "location": raw_item.get("location_raw"),
        "speakers": speakers,
        "organizations": [],
        "raw_text": raw_item.get("raw_text"),
        "fetched_at": fetched_at,
        "http_status": http_status,
    }


def limit_items(items: list[dict], limit: int | None = None) -> list[dict]:
    if limit is None:
        return items
    return items[:limit]


if __name__ == "__main__":
    import json
    from pathlib import Path

    here = Path(__file__).parent
    fixture_path = here / "sample_response.html"

    html = fixture_path.read_text(encoding="utf-8")

    all_items = parse_items(html, base_url=BASE_URL)
    limited_items = limit_items(all_items, limit=10)

    fetched_at = datetime.now(timezone.utc).isoformat()
    http_status = 200

    normalized_items = [
        normalize_item(item, fetched_at=fetched_at, http_status=http_status)
        for item in limited_items
    ]

    out_path = here.parent.parent / "06_normalization" / "iiserpune_normalized.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for item in normalized_items:
            f.write(json.dumps(item) + "\n")

    print(f"Parsed {len(all_items)} events, normalized {len(normalized_items)} -> {out_path}")
