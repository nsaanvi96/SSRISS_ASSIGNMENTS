utf-8"""
schema.py — shared output schema for all sources.

Every source normalizer must return a dict that matches ITEM_SCHEMA.
Call validate_item() before upsert to catch missing required fields early.
"""

from datetime import datetime, timezone



ITEM_SCHEMA = {
    "source_name":    str,   
    "source_url":     str,   
    "item_url":       str,   
    "item_type":      str,   
    "title":          str,   
    "event_start":    None,  
    "event_end":      None,  
    "location":       None,  
    "speakers":       list,  
    "organizations":  list,  
    "raw_text":       None,  
    "fetched_at":     str,   
    "http_status":    int,   
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
