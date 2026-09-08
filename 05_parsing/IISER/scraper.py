from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.iiserpune.ac.in"
TARGET_URL = f"{BASE_URL}/news?category=events"
USER_AGENT = "IISERPune-WebMonitorInternship/0.1 (educational scraping project; contact: saanvi@example.com)"


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
    results = limit_items(all_items, limit=10)

    out_path = here / "output.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"Parsed {len(all_items)} events, keeping {len(results)} -> {out_path}")
