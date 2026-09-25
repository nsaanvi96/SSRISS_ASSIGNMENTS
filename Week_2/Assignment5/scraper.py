utf-8import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup





BASE_URL = "https://www.iiserpune.ac.in"
TARGET_URL = f"{BASE_URL}/news?category=events"
USER_AGENT = (
    "IISERPune-WebMonitorInternship/0.1 "
    "(educational scraping project; contact: saanvi@example.com)"
)
SOURCE_NAME = "iiserpune_events"
IST = timezone(timedelta(hours=5, minutes=30))

log = logging.getLogger(__name__)





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

        raw_text = card.get_text(" ", strip=True)

        items.append({
            "title": title,
            "item_url": item_url,
            "date_raw": date_raw,
            "speaker_raw": None,
            "location_raw": None,
            "raw_text": raw_text,
        })

    return items






def parse_detail(html: str, item_url: str) -> dict:
    """
    Extract enrichment fields from a /news/post/... detail page.
    Missing fields are None; categories is always a list.

    Assumption: these are post-event reports, not pre-event listings.
    published_at_raw is when the article was posted, not the event date.
    Speaker and location are not available as structured fields on these pages.
    """
    soup = BeautifulSoup(html, "lxml")

    title_el = soup.select_one("h1.post-title span")
    title = title_el.get_text(strip=True) if title_el else None

    time_el = soup.select_one("time[datetime]")
    published_at_raw = time_el["datetime"] if time_el else None

    desc_el = soup.select_one("div.news-post-content")
    description = desc_el.get_text(separator=" ", strip=True) if desc_el else None

    category_els = soup.select("a.post-category span")
    categories = [el.get_text(strip=True) for el in category_els]

    return {
        "item_url": item_url,
        "title": title,
        "published_at_raw": published_at_raw,
        "description": description,
        "categories": categories,
    }






def merge_listing_and_detail(listing_item: dict, detail_item: dict) -> dict:
    """
    Combine a listing record with enrichment from its detail page.
    Listing fields are the base; detail fills in the gaps.
    If detail fetch failed, pass an empty dict — listing record is kept as-is.
    """
    merged = listing_item.copy()
    merged["published_at_raw"] = detail_item.get("published_at_raw")
    merged["description"] = detail_item.get("description")
    merged["categories"] = detail_item.get("categories", [])
    return merged






def _parse_posted_date(date_str: str | None) -> str | None:
    """
    Parse dates from two possible formats:
      Detail page time[datetime]: '2026-06-15 15:14'
      Listing page fallback text: 'Posted on Jun 15, 2026'
    Returns ISO 8601 string in IST, or None if unparseable.
    """
    if not date_str:
        return None

    
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        return parsed.replace(tzinfo=IST).isoformat()
    except ValueError:
        pass

    
    text = date_str.replace("Posted on", "").strip()
    try:
        parsed = datetime.strptime(text, "%b %d, %Y")
        return parsed.replace(tzinfo=IST).isoformat()
    except ValueError:
        return None


def normalize_item(raw_item: dict, fetched_at: str, http_status: int) -> dict:
    speaker_raw = raw_item.get("speaker_raw")
    speakers = [speaker_raw] if speaker_raw else []

    
    date_str = raw_item.get("published_at_raw") or raw_item.get("date_raw")

    return {
        "source_name": SOURCE_NAME,
        "source_url": TARGET_URL,
        "item_url": raw_item.get("item_url"),
        "item_type": "event",
        "title": raw_item.get("title"),
        "event_start": _parse_posted_date(date_str),
        "event_end": None,
        "location": raw_item.get("location_raw"),
        "speakers": speakers,
        "organizations": [],
        "description": raw_item.get("description"),
        "categories": raw_item.get("categories", []),
        "raw_text": raw_item.get("raw_text"),
        "fetched_at": fetched_at,
        "http_status": http_status,
    }






def run(listing_url: str = TARGET_URL, max_detail: int = 5) -> list[dict]:
    """
    Two-stage collection:
      1. Fetch listing page -> discover items
      2. For each item (up to max_detail), fetch detail page -> enrich
      3. Merge and normalize
    If a detail fetch fails, the listing record is kept as-is.
    """
    log.info("START source=%s", SOURCE_NAME)
    fetched_at = datetime.now(timezone.utc).isoformat()

    log.info("FETCH listing url=%s", listing_url)
    listing_html = fetch(listing_url)
    items = parse_items(listing_html, BASE_URL)
    log.info("PARSE listing records=%d", len(items))

    results = []
    for item in items[:max_detail]:
        detail_url = item.get("item_url")

        if not detail_url:
            log.warning("SKIP item missing item_url title=%s", item.get("title"))
            merged = item
        else:
            try:
                log.info("FETCH detail url=%s", detail_url)
                detail_html = fetch(detail_url)
                detail = parse_detail(detail_html, detail_url)
                merged = merge_listing_and_detail(item, detail)
                log.info("DETAIL ok url=%s", detail_url)
            except Exception as e:
                log.warning(
                    "DETAIL failed url=%s error=%s — keeping listing record",
                    detail_url, e
                )
                merged = item

        normalized = normalize_item(merged, fetched_at=fetched_at, http_status=200)
        results.append(normalized)

    log.info("END records=%d", len(results))
    return results






if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )

    here = Path(__file__).parent
    fixture_path = here / "sample_response.html"
    fixtures_dir = here / "fixtures"

    if fixture_path.exists():
        
        log.info("Running against saved fixture: %s", fixture_path)
        listing_html = fixture_path.read_text(encoding="utf-8")
        items = parse_items(listing_html, BASE_URL)
        fetched_at = datetime.now(timezone.utc).isoformat()
        results = []

        for i, item in enumerate(items[:5]):
            detail_url = item.get("item_url")
            detail_fixture = fixtures_dir / f"detail_{i + 1}.html"

            if detail_fixture.exists():
                detail_html = detail_fixture.read_text(encoding="utf-8")
                detail = parse_detail(detail_html, detail_url or "")
                merged = merge_listing_and_detail(item, detail)
                log.info("Used fixture: %s", detail_fixture.name)
            else:
                log.warning("No fixture for item %d — using listing record only", i + 1)
                merged = item

            normalized = normalize_item(merged, fetched_at=fetched_at, http_status=200)
            results.append(normalized)
    else:
        
        log.info("No fixture found — running live (max_detail=5)")
        results = run(max_detail=5)

    out_path = here / "output.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {len(results)} records to {out_path}")
