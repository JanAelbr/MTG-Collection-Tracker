import math

import pandas as pd


# Return True when a value is None or pandas NA.
def is_missing(value) -> bool:
    return value is None or pd.isna(value)


# Coerce a value to a clean string for JSON payloads.
def str_or_empty(value) -> str:
    if is_missing(value):
        return ""
    return str(value).strip()


# Resolve the display name for one deck card row.
def deck_card_display_name(row) -> str:
    for key in ("catalog_name", "card_name", "name"):
        text = str_or_empty(row.get(key))
        if text:
            return text
    set_code = str_or_empty(row.get("set_code"))
    collector_number = str_or_empty(row.get("collector_number"))
    if set_code and collector_number:
        return f"{set_code} #{collector_number}"
    return "Unknown"


# Replace NaN and Infinity values so JSON payloads are valid and JS-safe.
def sanitize_json_payload(value):
    if isinstance(value, dict):
        return {str(key): sanitize_json_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_json_payload(item) for item in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value
