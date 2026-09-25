utf-8"""
run.py — Main runner for the IISER Pune events scraper.

Usage:
    python run.py              # live fetch from iiserpune.ac.in
    python run.py --fixture    # use saved sample_response.html instead
"""

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from logging_config import get_logger
from scraper import fetch, parse_items, normalize_item, limit_items, BASE_URL, TARGET_URL
from storage import init_db, upsert_item, DB_PATH

logger = get_logger("web_monitor.runner")

FIXTURE_PATH = Path(__file__).parent.parent.parent / "05_parsing" / "IISER" / "sample_response.html"


def run(use_fixture: bool = False) -> None:
    start = time.monotonic()
    source = "iiserpune_events"
    logger.info("START source=%s", source)

    
    try:
        init_db(DB_PATH)
    except Exception as e:
        logger.error("STAGE=init_db source=%s error=%s", source, e)
        sys.exit(1)

    
    fetched_at = datetime.now(timezone.utc).isoformat()
    try:
        if use_fixture:
            logger.info("FETCH using fixture path=%s", FIXTURE_PATH)
            html = FIXTURE_PATH.read_text(encoding="utf-8")
            http_status = 200
        else:
            html, http_status = fetch(TARGET_URL)
    except Exception as e:
        logger.error("STAGE=fetch source=%s error=%s", source, e)
        sys.exit(1)

    
    try:
        raw_items = parse_items(html, BASE_URL)
    except Exception as e:
        logger.error("STAGE=parse source=%s error=%s", source, e)
        sys.exit(1)

    
    normalized = []
    for raw in raw_items:
        try:
            normalized.append(normalize_item(raw, fetched_at=fetched_at, http_status=http_status))
        except Exception as e:
            logger.warning("NORMALIZE skipped item_url=%s error=%s", raw.get("item_url"), e)
    logger.info("NORMALIZE records=%d", len(normalized))

    
    counts = {"new": 0, "unchanged": 0, "updated": 0}
    for item in normalized:
        try:
            result = upsert_item(item, DB_PATH)
            counts[result] += 1
        except Exception as e:
            logger.error("STORE failed item_url=%s error=%s", item.get("item_url"), e)

    logger.info(
        "STORE new=%d existing=%d changed=%d",
        counts["new"], counts["unchanged"], counts["updated"],
    )

    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info("END source=%s duration_ms=%d", source, duration_ms)


if __name__ == "__main__":
    use_fixture = "--fixture" in sys.argv
    run(use_fixture=use_fixture)
