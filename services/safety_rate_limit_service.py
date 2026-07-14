import os
from uuid import uuid4
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query, get_pool_status

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


def _count_events(profile_id=None, action_type=None, ip_hash=None):
    if _db_available():
        filters = []
        params = []
        if profile_id:
            filters.append("profile_id = %s")
            params.append(profile_id)
        if action_type:
            filters.append("action_type = %s")
            params.append(action_type)
        if ip_hash:
            filters.append("ip_hash = %s")
            params.append(ip_hash)
        where = " AND ".join(filters) if filters else "TRUE"
        rows = fast_query(
            f"SELECT COUNT(*) as c FROM chain_rate_limit_events WHERE {where}",
            tuple(params), default=[{"c": 0}]
        )
        return rows[0]["c"] if rows else 0
    events = [e for e in _FAKE_RATE_EVENTS
              if (not profile_id or e.get("profile_id") == profile_id)
              and (not action_type or e.get("action_type") == action_type)]
    return len(events)


def record_rate_limit_event(profile_id=None, action_type="generic", count=1, window_seconds=60, blocked=False, ip_hash=None, metadata=None):
    if _db_available():
        import json
        write_query(
            "INSERT INTO chain_rate_limit_events (id, profile_id, ip_hash, action_type, count, window_seconds, blocked, metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
            (str(uuid4()), profile_id, ip_hash, action_type, count, window_seconds, blocked, json.dumps(metadata or {}))
        )
    else:
        event = {"id": str(uuid4()), "profile_id": profile_id, "ip_hash": ip_hash, "action_type": action_type, "count": count, "window_seconds": window_seconds, "blocked": blocked, "metadata": metadata or {}, "created_at": datetime.now(timezone.utc).isoformat()}
        _FAKE_RATE_EVENTS.append(event)
    return {"ok": True}


def check_action_rate_limit(profile_id=None, action_type="generic", limit=None, window_seconds=None, ip_hash=None):
    default_limit, default_window = DEFAULT_LIMITS.get(action_type, (30, 60))
    limit = limit or default_limit
    window_seconds = window_seconds or default_window
    key_count = _count_events(profile_id=profile_id, action_type=action_type, ip_hash=ip_hash)
    blocked = key_count >= limit
    record_rate_limit_event(profile_id, action_type, key_count + 1, window_seconds, blocked, ip_hash)
    return {"ok": True, "blocked": blocked, "count": key_count + 1, "limit": limit, "window_seconds": window_seconds}


def is_action_blocked(profile_id=None, action_type="generic"):
    limit, _window = DEFAULT_LIMITS.get(action_type, (30, 60))
    count = _count_events(profile_id=profile_id, action_type=action_type)
    return count >= limit


def get_rate_limit_summary(profile_id=None):
    if _db_available():
        if profile_id:
            rows = fast_query("SELECT * FROM chain_rate_limit_events WHERE profile_id=%s ORDER BY created_at DESC LIMIT 100", (profile_id,), default=[])
        else:
            rows = fast_query("SELECT * FROM chain_rate_limit_events ORDER BY created_at DESC LIMIT 100", default=[])
        return {"ok": True, "events": rows, "count": len(rows), "blocked_count": len([e for e in rows if e.get("blocked")])}
    events = [e for e in _FAKE_RATE_EVENTS if not profile_id or e.get("profile_id") == profile_id]
    return {"ok": True, "events": events[-100:], "count": len(events), "blocked_count": len([e for e in events if e.get("blocked")])}
