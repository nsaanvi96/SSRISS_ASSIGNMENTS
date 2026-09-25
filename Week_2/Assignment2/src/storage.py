utf-8import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path(__file__).parent.parent / "data" / "monitor.db"


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
    """Create the items table if it does not already exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                item_url        TEXT PRIMARY KEY,
                source_name     TEXT,
                source_url      TEXT,
                item_type       TEXT,
                title           TEXT,
                event_start     TEXT,
                event_end       TEXT,
                location        TEXT,
                speakers        TEXT,
                organizations   TEXT,
                raw_text        TEXT,
                http_status     INTEGER,
                content_hash    TEXT,
                first_seen_at   TEXT,
                last_seen_at    TEXT,
                fetched_at      TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def upsert_item(item: dict, db_path: Path = DB_PATH) -> str:
    """
    Insert or update one item.
    Returns: 'new' | 'unchanged' | 'updated'
    """
    if not item.get("item_url"):
        raise ValueError("item is missing item_url — cannot upsert")

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            "SELECT content_hash FROM items WHERE item_url = ?",
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
                    raw_text, http_status, content_hash,
                    first_seen_at, last_seen_at, fetched_at
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
            return "new"

        (existing_hash,) = existing

        if existing_hash == new_hash:
            conn.execute(
                "UPDATE items SET last_seen_at = ?, fetched_at = ?, http_status = ? WHERE item_url = ?",
                (now, item.get("fetched_at"), item.get("http_status"), item["item_url"]),
            )
            conn.commit()
            return "unchanged"

        conn.execute(
            """
            UPDATE items SET
                source_name = ?, source_url = ?, item_type = ?, title = ?,
                event_start = ?, event_end = ?, location = ?, speakers = ?,
                organizations = ?, raw_text = ?, http_status = ?,
                content_hash = ?, last_seen_at = ?, fetched_at = ?
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
        return "updated"
    finally:
        conn.close()


def get_item(item_url: str, db_path: Path = DB_PATH) -> dict | None:
    """Return one stored item by URL, or None if not found."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute("SELECT * FROM items WHERE item_url = ?", (item_url,))
        row = cursor.fetchone()
        if row is None:
            return None
        result = dict(row)
        result["speakers"] = json.loads(result["speakers"]) if result["speakers"] else []
        result["organizations"] = json.loads(result["organizations"]) if result["organizations"] else []
        return result
    finally:
        conn.close()
