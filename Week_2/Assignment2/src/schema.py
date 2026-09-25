"""
schema.py — shared output schema for all sources.

Every source normalizer must return a dict that matches ITEM_SCHEMA.
Call validate_item() before upsert to catch missing required fields early.
"""

from datetime import datetime, timezone

# The canonical shape every normalized item must conform to.
# None = optional. [] = empty list is fine.
ITEM_SCHEMA = {
    "source_name":    str,   # required — e.g. "iiserpune_events"
    "source_url":     str,   # required — the listing page URL
    "item_url":       str,   # required — canonical URL for this item
    "item_type":      str,   # required — "event" | "faculty" | "announcement"
    "title":          str,   # required
    "event_start":    None,  # ISO-8601 string or None
    "event_end":      None,  # ISO-8601 string or None
    "location":       None,  # str or None
    "speakers":       list,  # list of str (may be empty)
    "organizations":  list,  # list of str (may be empty)
    "raw_text":       None,  # str or None
    "fetched_at":     str,   # required — ISO-8601 UTC timestamp
    "http_status":    int,   # required — e.g. 200
}

REQUIRED_FIELDS = {"source_name", "source_url", "item_url", "item_type", "title", "fetched_at", "http_status"}


def now_utc() -> str:
    """Current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def validate_item(item: dict) -> list[str]:
    """
    Check item against the shared schema.
    Returns a list of error strings (empty = valid).
    """
    errors = []
    for field in REQUIRED_FIELDS:
        if not item.get(field):
            errors.append(f"Missing required field: {field}")
    if "speakers" in item and not isinstance(item["speakers"], list):
        errors.append("'speakers' must be a list")
    if "organizations" in item and not isinstance(item["organizations"], list):
        errors.append("'organizations' must be a list")
    return errors
