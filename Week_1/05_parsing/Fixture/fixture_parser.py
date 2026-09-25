utf-8from urllib.parse import urljoin
from bs4 import BeautifulSoup


def parse_events(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    events = []

    for card in soup.select(".event-card"):
        title_el = card.select_one("h2.title a")
        title = title_el.get_text(strip=True) if title_el else None

        href = title_el.get("href") if title_el else None
        item_url = urljoin(base_url, href) if href else None

        date_el = card.select_one("time")
        date_raw = date_el.get_text(strip=True) if date_el else None

        speaker_el = card.select_one(".speaker")
        speaker_raw = speaker_el.get_text(strip=True) if speaker_el else None

        location_el = card.select_one(".location")
        location_raw = location_el.get_text(strip=True) if location_el else None

        raw_text = card.get_text(" ", strip=True)

        events.append({
            "title": title,
            "item_url": item_url,
            "date_raw": date_raw,
            "speaker_raw": speaker_raw,
            "location_raw": location_raw,
            "raw_text": raw_text,
        })

    return events


if __name__ == "__main__":
    import json
    from pathlib import Path

    fixture_path = Path(__file__).parent / "fixture.html"
    html = fixture_path.read_text(encoding="utf-8")

    results = parse_events(html, base_url="https://example.org/events")

    out_path = Path(__file__).parent / "fixture_output.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"Parsed {len(results)} events -> {out_path}")
