import os
from uuid import uuid4
from datetime import datetime, timezone

from services.neon_service import write_query, get_pool_status

_FAKE_RATE_EVENTS = []
DEFAULT_LIMITS = {
    "message": (20, 60),
    "tip": (10, 300),
    "gift": (10, 300),
    "report": (5, 300),
    "payout_request": (3, 600),
    "creator_verification": (2, 86400),
}


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1" or os.getenv("CHAIN_TEST_FAKE_DB") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def record_rate_limit_event(profile_id=None, action_type="generic", count=1, window_seconds=60, blocked=False, ip_hash=None, metadata=None):
    event = {"id": str(uuid4()), "profile_id": profile_id, "ip_hash": ip_hash, "action_type": action_type, "count": count, "window_seconds": window_seconds, "blocked": blocked, "metadata": metadata or {}, "created_at": datetime.now(timezone.utc).isoformat()}
    _FAKE_RATE_EVENTS.append(event)
    if _db_available():
        import json
        write_query(
            "INSERT INTO chain_rate_limit_events (id, profile_id, ip_hash, action_type, count, window_seconds, blocked, metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
            (event["id"], profile_id, ip_hash, action_type, count, window_seconds, blocked, json.dumps(metadata or {}))
        )
    return {"ok": True, "event": event}


def check_action_rate_limit(profile_id=None, action_type="generic", limit=None, window_seconds=None, ip_hash=None):
    default_limit, default_window = DEFAULT_LIMITS.get(action_type, (30, 60))
    limit = limit or default_limit
    window_seconds = window_seconds or default_window
    key_count = len([e for e in _FAKE_RATE_EVENTS if e.get("profile_id") == profile_id and e.get("action_type") == action_type])
    blocked = key_count >= limit
    record_rate_limit_event(profile_id, action_type, key_count + 1, window_seconds, blocked, ip_hash)
    return {"ok": True, "blocked": blocked, "count": key_count + 1, "limit": limit, "window_seconds": window_seconds}


def is_action_blocked(profile_id=None, action_type="generic"):
    limit, _window = DEFAULT_LIMITS.get(action_type, (30, 60))
    return len([e for e in _FAKE_RATE_EVENTS if e.get("profile_id") == profile_id and e.get("action_type") == action_type]) >= limit


def get_rate_limit_summary(profile_id=None):
    events = [e for e in _FAKE_RATE_EVENTS if not profile_id or e.get("profile_id") == profile_id]
    return {"ok": True, "events": events[-100:], "count": len(events), "blocked_count": len([e for e in events if e.get("blocked")])}
