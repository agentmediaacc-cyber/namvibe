import os
import json
from uuid import uuid4
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query, get_pool_status

_FAKE_REPORTS = []
_FAKE_QUEUE = []
_FAKE_ACTIONS = []
_RESTRICTED = set()


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1" or os.getenv("CHAIN_TEST_FAKE_DB") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _now():
    return datetime.now(timezone.utc).isoformat()


def create_report(reporter_profile_id, reported_profile_id=None, content_type=None, content_id=None, reason="other", details=None, severity="medium"):
    report = {"id": str(uuid4()), "reporter_profile_id": reporter_profile_id, "reported_profile_id": reported_profile_id, "content_type": content_type, "content_id": content_id, "reason": reason, "details": details, "status": "open", "severity": severity or "medium", "moderator_profile_id": None, "resolution_note": None, "created_at": _now(), "resolved_at": None}
    _FAKE_REPORTS.append(report)
    if _db_available():
        write_query(
            "INSERT INTO chain_user_reports (id, reporter_profile_id, reported_profile_id, content_type, content_id, reason, details, severity) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (report["id"], reporter_profile_id, reported_profile_id, content_type, content_id, reason, details, report["severity"])
        )
    add_to_moderation_queue(reported_profile_id, content_type or "profile", content_id, "user_report", report["severity"], reason, {"report_id": report["id"]})
    try:
        from services.socketio_service import socketio
        socketio.emit("safety:report-created", {"report_id": report["id"]})
    except Exception:
        pass
    return {"ok": True, "report": report}


def get_reports(status=None, profile_id=None, limit=50):
    if _db_available():
        where = []
        params = []
        if status:
            where.append("status = %s")
            params.append(status)
        if profile_id:
            where.append("(reporter_profile_id = %s OR reported_profile_id = %s)")
            params.extend([profile_id, profile_id])
        sql = "SELECT * FROM chain_user_reports" + ((" WHERE " + " AND ".join(where)) if where else "") + " ORDER BY created_at DESC LIMIT %s"
        rows = fast_query(sql, (*params, limit), default=[])
        return [dict(r) for r in rows]
    rows = [r for r in _FAKE_REPORTS if (not status or r["status"] == status) and (not profile_id or r["reporter_profile_id"] == profile_id or r["reported_profile_id"] == profile_id)]
    return rows[-limit:]


def resolve_report(report_id, moderator_profile_id=None, status="resolved", resolution_note=None):
    for r in _FAKE_REPORTS:
        if r["id"] == report_id:
            r.update({"status": status, "moderator_profile_id": moderator_profile_id, "resolution_note": resolution_note, "resolved_at": _now()})
            break
    if _db_available():
        write_query("UPDATE chain_user_reports SET status=%s, moderator_profile_id=%s, resolution_note=%s, resolved_at=now() WHERE id=%s", (status, moderator_profile_id, resolution_note, report_id))
    try:
        from services.push_notification_service import queue_push_event
        report = next((r for r in _FAKE_REPORTS if r["id"] == report_id), None)
        if report and report.get("reporter_profile_id"):
            queue_push_event(report["reporter_profile_id"], "report_resolved", "Report resolved", resolution_note or "Your report was reviewed.")
    except Exception:
        pass
    return {"ok": True}


def add_to_moderation_queue(profile_id=None, content_type="profile", content_id=None, queue_type="manual", risk_level="medium", reason="", metadata=None):
    item = {"id": str(uuid4()), "profile_id": profile_id, "content_type": content_type, "content_id": content_id, "queue_type": queue_type, "risk_level": risk_level or "medium", "status": "pending", "reason": reason, "metadata": metadata or {}, "assigned_to_profile_id": None, "created_at": _now(), "reviewed_at": None}
    _FAKE_QUEUE.append(item)
    if _db_available():
        write_query(
            "INSERT INTO chain_moderation_queue (id, profile_id, content_type, content_id, queue_type, risk_level, reason, metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
            (item["id"], profile_id, content_type, content_id, queue_type, item["risk_level"], reason, json.dumps(metadata or {}))
        )
    if item["risk_level"] in {"high", "critical"} or queue_type in {"fraud", "spam", "user_report"}:
        try:
            from services.job_queue_service import enqueue_job
            enqueue_job("safety_scan", {"moderation_item_id": item["id"], "profile_id": profile_id}, priority=2, queue="safety")
        except Exception:
            pass
    return {"ok": True, "item": item}


def get_moderation_queue(status="pending", limit=50):
    if _db_available():
        rows = fast_query("SELECT * FROM chain_moderation_queue WHERE status = %s ORDER BY created_at DESC LIMIT %s", (status, limit), default=[])
        return [dict(r) for r in rows]
    return [q for q in _FAKE_QUEUE if not status or q["status"] == status][-limit:]


def assign_moderation_item(item_id, moderator_profile_id):
    for item in _FAKE_QUEUE:
        if item["id"] == item_id:
            item["assigned_to_profile_id"] = moderator_profile_id
    if _db_available():
        write_query("UPDATE chain_moderation_queue SET assigned_to_profile_id=%s WHERE id=%s", (moderator_profile_id, item_id))
    return {"ok": True}


def review_moderation_item(item_id, moderator_profile_id=None, status="reviewed", note=None):
    for item in _FAKE_QUEUE:
        if item["id"] == item_id:
            item.update({"status": status, "assigned_to_profile_id": moderator_profile_id or item.get("assigned_to_profile_id"), "reviewed_at": _now()})
    if _db_available():
        write_query("UPDATE chain_moderation_queue SET status=%s, assigned_to_profile_id=COALESCE(%s, assigned_to_profile_id), reviewed_at=now() WHERE id=%s", (status, moderator_profile_id, item_id))
    return {"ok": True}


def take_moderation_action(action_type, target_profile_id=None, moderator_profile_id=None, content_type=None, content_id=None, reason="", duration_minutes=None, metadata=None):
    action = {"id": str(uuid4()), "moderator_profile_id": moderator_profile_id, "target_profile_id": target_profile_id, "content_type": content_type, "content_id": content_id, "action_type": action_type, "reason": reason, "duration_minutes": duration_minutes, "metadata": metadata or {}, "created_at": _now()}
    _FAKE_ACTIONS.append(action)
    if action_type == "warn" and target_profile_id:
        warn_user(target_profile_id, reason, moderator_profile_id)
    if action_type == "restrict" and target_profile_id:
        restrict_user(target_profile_id, reason, duration_minutes, moderator_profile_id)
    if _db_available():
        write_query(
            "INSERT INTO chain_moderation_actions (id, moderator_profile_id, target_profile_id, content_type, content_id, action_type, reason, duration_minutes, metadata) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
            (action["id"], moderator_profile_id, target_profile_id, content_type, content_id, action_type, reason, duration_minutes, json.dumps(metadata or {}))
        )
    return {"ok": True, "action": action}


def restrict_user(profile_id, reason="", duration_minutes=None, moderator_profile_id=None):
    _RESTRICTED.add(profile_id)
    from services.trust_score_service import record_restriction
    record_restriction(profile_id, reason)
    return {"ok": True, "restricted": True}


def unrestrict_user(profile_id, moderator_profile_id=None, reason=""):
    _RESTRICTED.discard(profile_id)
    return {"ok": True, "restricted": False}


def warn_user(profile_id, reason="", moderator_profile_id=None):
    from services.trust_score_service import record_warning
    record_warning(profile_id, reason)
    return {"ok": True}


def remove_content(content_type, content_id, moderator_profile_id=None, reason=""):
    return {"ok": True, "removed": True, "content_type": content_type, "content_id": content_id}


def restore_content(content_type, content_id, moderator_profile_id=None, reason=""):
    return {"ok": True, "restored": True, "content_type": content_type, "content_id": content_id}


def is_user_restricted(profile_id):
    return profile_id in _RESTRICTED
