"""Cursor-based pagination helper for feeds."""

from base64 import b64encode, b64decode
import json


def encode_cursor(value):
    if value is None:
        return None
    return b64encode(json.dumps({"c": str(value)}).encode()).decode()


def decode_cursor(cursor_str):
    if not cursor_str:
        return None
    try:
        data = json.loads(b64decode(cursor_str.encode()).decode())
        return data.get("c")
    except Exception:
        return None


def paginate(items, cursor, limit=20):
    if cursor:
        cursor_val = decode_cursor(cursor)
        try:
            idx = next(i for i, item in enumerate(items) if item.get("id") == cursor_val)
            items = items[idx + 1:]
        except (StopIteration, ValueError):
            pass

    result = items[:limit]
    next_cursor = None
    if len(result) == limit and len(items) > limit:
        next_cursor = encode_cursor(result[-1].get("id"))
    return result, next_cursor
