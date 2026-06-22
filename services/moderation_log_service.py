import os
from uuid import uuid4
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query, get_pool_status

_FAKE_LOGS = []


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1" or os.getenv("CHAIN_TEST_FAKE_DB") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _now():
    return datetime.now(timezone.utc).isoformat()


def _row(row):
    data = dict(row)
    data["id"] = str(data["id"])
    return data


def log_moderation_action(actor_id, target_id, action, entity_type=None, entity_id=None, reason=None, details=None, ip_address=None):
    log_id = str(uuid4())
    log_entry = {
        "id": log_id,
        "actor_id": actor_id,
        "target_id": target_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "reason": reason,
        "details": details,
        "ip_address": ip_address,
        "created_at": _now(),
    }
    _FAKE_LOGS.append(log_entry)
    if _db_available():
        write_query(
            "INSERT INTO chain_moderation_logs (id, actor_id, target_id, action, entity_type, entity_id, reason, details, ip_address) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (log_id, actor_id, target_id, action, entity_type, entity_id, reason, details, ip_address)
        )
    return {"ok": True, "log": log_entry}


def get_moderation_logs(actor_id=None, target_id=None, action=None, limit=50, offset=0):
    if not _db_available():
        results = list(_FAKE_LOGS)
        if actor_id:
            results = [l for l in results if l["actor_id"] == actor_id]
        if target_id:
            results = [l for l in results if l["target_id"] == target_id]
        if action:
            results = [l for l in results if l["action"] == action]
        return results[-limit:] if limit else results
    where = []
    params = []
    if actor_id:
        where.append("actor_id = %s")
        params.append(actor_id)
    if target_id:
        where.append("target_id = %s")
        params.append(target_id)
    if action:
        where.append("action = %s")
        params.append(action)
    sql = "SELECT * FROM chain_moderation_logs" + ((" WHERE " + " AND ".join(where)) if where else "") + " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    rows = fast_query(sql, tuple(params), default=[])
    return [_row(r) for r in rows]


def get_moderation_log_count(actor_id=None, target_id=None, action=None):
    if not _db_available():
        results = list(_FAKE_LOGS)
        if actor_id:
            results = [l for l in results if l["actor_id"] == actor_id]
        if target_id:
            results = [l for l in results if l["target_id"] == target_id]
        if action:
            results = [l for l in results if l["action"] == action]
        return {"ok": True, "count": len(results)}
    where = []
    params = []
    if actor_id:
        where.append("actor_id = %s")
        params.append(actor_id)
    if target_id:
        where.append("target_id = %s")
        params.append(target_id)
    if action:
        where.append("action = %s")
        params.append(action)
    sql = "SELECT COUNT(*) AS count FROM chain_moderation_logs" + ((" WHERE " + " AND ".join(where)) if where else "")
    rows = fast_query(sql, tuple(params), default=[])
    count = int((rows[0] or {}).get("count") or 0) if rows else 0
    return {"ok": True, "count": count}
