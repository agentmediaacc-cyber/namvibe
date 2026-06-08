import json
import os
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query, get_pool_status

_CK_COLS = "id, call_id, profile_id, caller_name, call_type, push_payload, created_at"

APNS_TOPIC = os.getenv("APNS_TOPIC", "app.chain")


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _row_to_callkit(row):
    return {
        "id": str(row["id"]),
        "call_id": str(row["call_id"]) if row.get("call_id") else None,
        "profile_id": str(row["profile_id"]),
        "caller_name": row.get("caller_name") or "",
        "call_type": row.get("call_type") or "audio",
        "push_payload": row.get("push_payload") or {},
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


def prepare_callkit_payload(call_id, caller_profile_id, caller_name, callee_profile_id, call_type="audio"):
    payload = {
        "aps": {
            "alert": {
                "title": "Incoming Call",
                "body": f"{caller_name} is calling",
            },
            "sound": "call.caf",
            "badge": 1,
            "mutable-content": 1,
            "category": "incoming_call",
        },
        "call_id": call_id,
        "caller_id": caller_profile_id,
        "caller_name": caller_name,
        "call_type": call_type,
        "handle": caller_name,
        "has_video": call_type == "video",
    }
    try:
        if _db_available():
            write_query(
                "INSERT INTO chain_callkit_payloads (call_id, profile_id, caller_name, call_type, push_payload) VALUES (%s, %s, %s, %s, %s::jsonb)",
                (call_id, callee_profile_id, caller_name, call_type, json.dumps(payload)),
            )
    except Exception:
        pass
    return payload


def get_callkit_payload(call_id, profile_id):
    try:
        if _db_available():
            rows = fast_query(
                f"SELECT {_CK_COLS} FROM chain_callkit_payloads WHERE call_id = %s AND profile_id = %s ORDER BY created_at DESC LIMIT 1",
                (call_id, profile_id),
                default=[],
            )
            if rows:
                return _row_to_callkit(rows[0])
        return None
    except Exception:
        return None


def build_apns_push_payload(payload):
    apns = {
        "aps": {
            "alert": {
                "title": payload.get("aps", {}).get("alert", {}).get("title", "CHAIN"),
                "body": payload.get("aps", {}).get("alert", {}).get("body", ""),
            },
            "sound": payload.get("aps", {}).get("sound", "call.caf"),
            "badge": payload.get("aps", {}).get("badge", 1),
            "mutable-content": payload.get("aps", {}).get("mutable-content", 1),
            "category": payload.get("aps", {}).get("category", "incoming_call"),
        },
        "call_id": payload.get("call_id"),
        "caller_id": payload.get("caller_id"),
        "caller_name": payload.get("caller_name"),
        "call_type": payload.get("call_type", "audio"),
        "handle": payload.get("handle", ""),
        "has_video": payload.get("has_video", False),
    }
    return apns


def build_android_call_payload(call_id, caller_name, call_type="audio"):
    return {
        "call_id": call_id,
        "caller_name": caller_name,
        "call_type": call_type,
        "has_video": call_type == "video",
        "is_background_call": True,
        "notification_type": "incoming_call",
    }
