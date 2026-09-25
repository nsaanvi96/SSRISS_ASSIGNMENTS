import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from logging_config import get_logger

logger = get_logger("web_monitor.scraper")

BASE_URL = "https://www.iiserpune.ac.in"
TARGET_URL = f"{BASE_URL}/news?category=events"
USER_AGENT = "IISERPune-WebMonitorInternship/0.1 (educational scraping project; contact: saanvi@example.com)"
SOURCE_NAME = "iiserpune_events"
IST = timezone(timedelta(hours=5, minutes=30))


def fetch(url: str) -> tuple[str, int]:
    """
    Fetch a URL and return (html, http_status).
    Raises RuntimeError on any network or HTTP failure.
    """
    headers = {"User-Agent": USER_AGENT}
    logger.debug("FETCH starting url=%s", url)
    start = time.monotonic()

    try:
        response = requests.get(url, headers=headers, timeout=10)
        duration_ms = int((time.monotonic() - start) * 1000)
        response.raise_for_status()

    except requests.exceptions.Timeout:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "FETCH timeout url=%s duration_ms=%d", url, duration_ms
        )
        raise RuntimeError(f"Request to {url} timed out.")

    except requests.exceptions.HTTPError as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "FETCH http_error url=%s status=%s duration_ms=%d error=%s",
            url, response.status_code, duration_ms, e,
        )
        raise RuntimeError(f"HTTP error fetching {url}: {e}")

    except requests.exceptions.ConnectionError as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "FETCH connection_error url=%s duration_ms=%d error=%s",
            url, duration_ms, e,
        )
        raise RuntimeError(f"Connection error fetching {url}: {e}")

    except requests.exceptions.RequestException as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "FETCH request_error url=%s duration_ms=%d error=%s",
            url, duration_ms, e,
        )
        raise RuntimeError(f"Failed to fetch {url}: {e}")

    logger.info(
        "FETCH ok url=%s status=%d duration_ms=%d",
        response.url, response.status_code, duration_ms,
    )
    return response.text, response.status_code


def parse_items(html: str, base_url: str) -> list[dict]:
    """
    Parse event cards from HTML and return a list of raw item dicts.
    """
    logger.debug("PARSE starting base_url=%s", base_url)

    try:
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select("li.news-card")
    except Exception as e:
        logger.error("PARSE failed to build soup error=%s", e)
        raise RuntimeError(f"Failed to parse HTML: {e}")

    if not cards:
        logger.warning("PARSE no records found — page may be empty or structure changed")

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

    logger.info("PARSE records=%d", len(items))
    return items


def _parse_posted_date(date_raw: str | None) -> str | None:
    if not date_raw:
        return None

    text = date_raw.replace("Posted on", "").strip()

    try:
        parsed = datetime.strptime(text, "%b %d, %Y")
    except ValueError:
        logger.warning("NORMALIZE date_parse_failed date_raw=%r", date_raw)
        return None

    parsed = parsed.replace(tzinfo=IST)
    return parsed.isoformat()


def normalize_item(raw_item: dict, fetched_at: str, http_status: int) -> dict:
    """
    Convert a raw parsed item into the shared output schema.
    """
    speaker_raw = raw_item.get("speaker_raw")
    speakers = [speaker_raw] if speaker_raw else []

    normalized = {
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

    logger.debug(
        "NORMALIZE item_url=%s event_start=%s",
        normalized["item_url"], normalized["event_start"],
    )
    return normalized


def limit_items(items: list[dict], limit: int | None = None) -> list[dict]:
    if limit is None:
        return items
    return items[:limit]
