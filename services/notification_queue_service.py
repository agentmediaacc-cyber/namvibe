import json
import os
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query, get_pool_status

_NQ_COLS = "id, profile_id, notification_type, title, body, payload, status, retry_count, max_retries, created_at, processed_at"


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _row_to_entry(row):
    return {
        "id": str(row["id"]),
        "profile_id": str(row["profile_id"]),
        "notification_type": row.get("notification_type") or "info",
        "title": row.get("title") or "",
        "body": row.get("body") or "",
        "payload": row.get("payload") or {},
        "status": row.get("status") or "pending",
        "retry_count": row.get("retry_count") or 0,
        "max_retries": row.get("max_retries") or 3,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "processed_at": row["processed_at"].isoformat() if row.get("processed_at") else None,
    }


def queue_notification(profile_id, notification_type, title="", body="", payload=None):
    if not profile_id or not notification_type:
        return {"ok": False, "error": "missing_fields"}
    try:
        if _db_available():
            write_query(
                "INSERT INTO chain_notification_queue (profile_id, notification_type, title, body, payload) VALUES (%s, %s, %s, %s, %s::jsonb)",
                (profile_id, notification_type, title, body, json.dumps(payload or {})),
            )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def process_notification(queue_id):
    if not queue_id:
        return {"ok": False, "error": "missing_id"}
    try:
        if _db_available():
            rows = fast_query(
                f"SELECT {_NQ_COLS} FROM chain_notification_queue WHERE id = %s AND status = 'pending' LIMIT 1",
                (queue_id,),
                default=[],
            )
            if not rows:
                return {"ok": False, "error": "not_found"}
            entry = _row_to_entry(rows[0])
            from services.push_notification_service import send_push_notification
            result = send_push_notification(
                entry["profile_id"],
                entry["title"],
                entry["body"],
                {**entry["payload"], "_notification_type": entry["notification_type"]},
            )
            if result.get("ok"):
                mark_notification_sent(queue_id)
            else:
                mark_notification_failed(queue_id)
            return result
        return {"ok": False, "error": "db_unavailable"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def process_pending_notifications(limit=50):
    try:
        if not _db_available():
            return {"ok": False, "error": "db_unavailable", "processed": 0}
        rows = fast_query(
            f"SELECT {_NQ_COLS} FROM chain_notification_queue WHERE status = 'pending' AND retry_count < max_retries ORDER BY created_at ASC LIMIT {limit}",
            default=[],
        )
        processed = 0
        for row in rows:
            result = process_notification(str(row["id"]))
            if result.get("ok"):
                processed += 1
        return {"ok": True, "processed": processed, "total": len(rows)}
    except Exception as e:
        return {"ok": False, "error": str(e), "processed": 0}


def mark_notification_sent(queue_id):
    if not queue_id:
        return {"ok": False}
    try:
        if _db_available():
            write_query(
                "UPDATE chain_notification_queue SET status = 'sent', processed_at = now() WHERE id = %s",
                (queue_id,),
            )
        return {"ok": True}
    except Exception:
        return {"ok": False}


def mark_notification_failed(queue_id):
    if not queue_id:
        return {"ok": False}
    try:
        if _db_available():
            write_query(
                "UPDATE chain_notification_queue SET retry_count = retry_count + 1, status = CASE WHEN retry_count + 1 >= max_retries THEN 'failed' ELSE 'pending' END WHERE id = %s",
                (queue_id,),
            )
        return {"ok": True}
    except Exception:
        return {"ok": False}


def get_notification_history(profile_id, limit=50):
    if not profile_id:
        return []
    try:
        if _db_available():
            rows = fast_query(
                f"SELECT {_NQ_COLS} FROM chain_notification_queue WHERE profile_id = %s ORDER BY created_at DESC LIMIT {limit}",
                (profile_id,),
                default=[],
            )
            return [_row_to_entry(r) for r in rows]
        return []
    except Exception:
        return []
