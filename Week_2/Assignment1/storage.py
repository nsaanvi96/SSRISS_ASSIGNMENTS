utf-8import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from logging_config import get_logger

logger = get_logger("web_monitor.storage")

DB_PATH = Path(__file__).parent / "data" / "iiserpune.db"

HASH_FIELDS = [
    "title",
    "event_start",
    "event_end",
    "location",
    "speakers",
    "organizations",
    "raw_text",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _content_hash(item: dict) -> str:
    payload = {field: item.get(field) for field in HASH_FIELDS}
    serialized = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def init_db(db_path: Path = DB_PATH) -> None:
    logger.debug("STORAGE init_db path=%s", db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    item_url TEXT PRIMARY KEY,
                    source_name TEXT,
                    source_url TEXT,
                    item_type TEXT,
                    title TEXT,
                    event_start TEXT,
                    event_end TEXT,
                    location TEXT,
                    speakers TEXT,
                    organizations TEXT,
                    raw_text TEXT,
                    http_status INTEGER,
                    content_hash TEXT,
                    first_seen_at TEXT,
                    last_seen_at TEXT,
                    fetched_at TEXT
                )
                """
            )
            conn.commit()
            logger.info("STORAGE db_ready path=%s", db_path)
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.error("STORAGE init_db_failed path=%s error=%s", db_path, e)
        raise


def upsert_item(item: dict, db_path: Path = DB_PATH) -> str:
    if not item.get("item_url"):
        logger.error("STORAGE upsert_failed reason=missing_item_url item=%s", item)
        raise ValueError("item is missing item_url, cannot upsert")

    logger.debug("STORAGE upsert item_url=%s", item["item_url"])

    try:
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.execute(
                "SELECT content_hash, first_seen_at FROM items WHERE item_url = ?",
                (item["item_url"],),
            )
            existing = cursor.fetchone()
            new_hash = _content_hash(item)
            now = _now()

            if existing is None:
                conn.execute(
                    """
                    INSERT INTO items (
                        item_url, source_name, source_url, item_type, title,
                        event_start, event_end, location, speakers, organizations,
                        raw_text, http_status, content_hash, first_seen_at,
                        last_seen_at, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["item_url"],
                        item.get("source_name"),
                        item.get("source_url"),
                        item.get("item_type"),
                        item.get("title"),
                        item.get("event_start"),
                        item.get("event_end"),
                        item.get("location"),
                        json.dumps(item.get("speakers") or []),
                        json.dumps(item.get("organizations") or []),
                        item.get("raw_text"),
                        item.get("http_status"),
                        new_hash,
                        now,
                        now,
                        item.get("fetched_at"),
                    ),
                )
                conn.commit()
                logger.debug("STORAGE inserted item_url=%s", item["item_url"])
                return "new"

            existing_hash, _ = existing

            if existing_hash == new_hash:
                conn.execute(
                    "UPDATE items SET last_seen_at = ?, fetched_at = ?, http_status = ? WHERE item_url = ?",
                    (now, item.get("fetched_at"), item.get("http_status"), item["item_url"]),
                )
                conn.commit()
                logger.debug("STORAGE unchanged item_url=%s", item["item_url"])
                return "unchanged"

            conn.execute(
                """
                UPDATE items SET
                    source_name = ?, source_url = ?, item_type = ?, title = ?,
                    event_start = ?, event_end = ?, location = ?, speakers = ?,
                    organizations = ?, raw_text = ?, http_status = ?, content_hash = ?,
                    last_seen_at = ?, fetched_at = ?
                WHERE item_url = ?
                """,
                (
                    item.get("source_name"),
                    item.get("source_url"),
                    item.get("item_type"),
                    item.get("title"),
                    item.get("event_start"),
                    item.get("event_end"),
                    item.get("location"),
                    json.dumps(item.get("speakers") or []),
                    json.dumps(item.get("organizations") or []),
                    item.get("raw_text"),
                    item.get("http_status"),
                    new_hash,
                    now,
                    item.get("fetched_at"),
                    item["item_url"],
                ),
            )
            conn.commit()
            logger.debug("STORAGE updated item_url=%s", item["item_url"])
            return "updated"

        finally:
            conn.close()

    except sqlite3.Error as e:
        logger.error("STORAGE upsert_failed item_url=%s error=%s", item.get("item_url"), e)
        raise
