"""
runner.py — generic source runner.

A source config dict must have:
    name         str                  — human-readable source identifier
    listing_url  str                  — URL of the listing page to fetch
    base_url     str                  — base for resolving relative links
    item_type    str                  — "event" | "faculty" | "announcement"
    parser       callable(html, base_url) -> list[dict]
    normalizer   callable(raw_item, fetched_at, http_status) -> dict

Optional keys:
    detail       callable(html, item_url) -> dict
                     — if present, runner fetches each item's detail page and
                       merges the result before normalization
    merger       callable(listing_item, detail_item) -> dict
                     — required alongside "detail"; combines the two dicts
    max_items    int  — cap records per run (useful during dev)
    max_detail   int  — cap detail fetches per run (default: same as max_items)
"""

import time
from pathlib import Path

from fetch import fetch
from logging_config import get_logger
from schema import now_utc, validate_item
from storage import DB_PATH, init_db, upsert_item

logger = get_logger("web_monitor")


def run_source(source_config: dict, db_path: Path = DB_PATH) -> dict:
    """
    Run one full collect cycle for a source.

    Returns a summary dict:
        { "source": str, "new": int, "unchanged": int, "updated": int,
          "errors": int, "duration_ms": int }
    """
    name         = source_config["name"]
    listing_url  = source_config["listing_url"]
    base_url     = source_config["base_url"]
    parser       = source_config["parser"]
    normalizer   = source_config["normalizer"]
    detail_fn    = source_config.get("detail")
    merger       = source_config.get("merger")
    max_items    = source_config.get("max_items")
    max_detail   = source_config.get("max_detail", max_items)

    summary = {"source": name, "new": 0, "unchanged": 0, "updated": 0, "errors": 0}
    t_start = time.monotonic()

    logger.info("START source=%s", name)

    # ── 1. Fetch listing ──────────────────────────────────────────────────────
    # Use a custom fetcher if the source provides one (e.g. fixture/disk source),
    # otherwise fall back to the standard network fetcher.
    _fetcher = source_config.get("fetcher", fetch)
    try:
        html, http_status = _fetcher(listing_url)
        logger.info("FETCH url=%s status=%d", listing_url, http_status)
    except RuntimeError as exc:
        logger.error("FETCH FAILED source=%s error=%s", name, exc)
        summary["errors"] += 1
        _log_end(name, summary, t_start)
        return summary

    fetched_at = now_utc()

    # ── 2. Parse listing ──────────────────────────────────────────────────────
    try:
        raw_items = parser(html, base_url)
        if max_items is not None:
            raw_items = raw_items[:max_items]
        logger.info("PARSE records=%d source=%s", len(raw_items), name)
    except Exception as exc:
        logger.error("PARSE FAILED source=%s error=%s", name, exc)
        summary["errors"] += 1
        _log_end(name, summary, t_start)
        return summary

    # ── 3. Detail enrichment (optional) ──────────────────────────────────────
    if detail_fn and merger:
        raw_items = _enrich_with_detail(
            raw_items, detail_fn, merger, name,
            max_detail=max_detail,
        )

    # ── 4. Normalize ──────────────────────────────────────────────────────────
    normalized = []
    for raw in raw_items:
        try:
            item = normalizer(raw, fetched_at=fetched_at, http_status=http_status)
            errs = validate_item(item)
            if errs:
                logger.warning(
                    "NORMALIZE schema errors source=%s item=%s errors=%s",
                    name, raw.get("item_url"), errs,
                )
            normalized.append(item)
        except Exception as exc:
            logger.error(
                "NORMALIZE error source=%s item=%s error=%s",
                name, raw.get("item_url"), exc,
            )
            summary["errors"] += 1

    logger.info("NORMALIZE records=%d source=%s", len(normalized), name)

    # ── 5. Store ──────────────────────────────────────────────────────────────
    init_db(db_path)
    for item in normalized:
        try:
            result = upsert_item(item, db_path=db_path)
            summary[result] += 1
        except Exception as exc:
            logger.error(
                "STORE error source=%s item=%s error=%s",
                name, item.get("item_url"), exc,
            )
            summary["errors"] += 1

    logger.info(
        "STORE new=%d unchanged=%d updated=%d errors=%d source=%s",
        summary["new"], summary["unchanged"], summary["updated"],
        summary["errors"], name,
    )

    _log_end(name, summary, t_start)
    return summary


def _enrich_with_detail(
    raw_items: list[dict],
    detail_fn,
    merger,
    source_name: str,
    max_detail: int | None,
) -> list[dict]:
    """
    For each raw listing item, fetch its detail page and merge the result.
    If a detail fetch fails, the listing record is kept unchanged.
    Items beyond max_detail are passed through without enrichment.
    """
    enriched = []
    detail_cap = max_detail if max_detail is not None else len(raw_items)

    for i, raw in enumerate(raw_items):
        item_url = raw.get("item_url")

        if i >= detail_cap or not item_url:
            if i >= detail_cap:
                logger.debug(
                    "DETAIL skip (cap reached) source=%s item=%s",
                    source_name, item_url,
                )
            else:
                logger.warning(
                    "DETAIL skip (no url) source=%s", source_name,
                )
            enriched.append(raw)
            continue

        try:
            detail_html, _ = fetch(item_url)
            detail = detail_fn(detail_html, item_url)
            merged = merger(raw, detail)
            logger.info("DETAIL ok source=%s item=%s", source_name, item_url)
            enriched.append(merged)
        except Exception as exc:
            logger.warning(
                "DETAIL failed source=%s item=%s error=%s — keeping listing record",
                source_name, item_url, exc,
            )
            enriched.append(raw)

    return enriched


def _log_end(name: str, summary: dict, t_start: float) -> None:
    duration_ms = int((time.monotonic() - t_start) * 1000)
    summary["duration_ms"] = duration_ms
    logger.info(
        "END source=%s duration_ms=%d new=%d unchanged=%d updated=%d errors=%d",
        name, duration_ms,
        summary["new"], summary["unchanged"], summary["updated"], summary["errors"],
    )
