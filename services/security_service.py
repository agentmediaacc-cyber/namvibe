import json
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query
from services.logging_service import log_error


def _utcnow():
    return datetime.now(timezone.utc)


_DEVICE_COLS = "id, profile_id, device_name, device_type, browser, os, ip_hash, trusted, last_seen, created_at, revoked_at"

def _row_to_device(row):
    if not row:
        return None
    return {
        "id": str(row["id"]), "profile_id": str(row["profile_id"]),
        "device_name": row.get("device_name") or "",
        "device_type": row.get("device_type") or "",
        "browser": row.get("browser") or "",
        "os": row.get("os") or "",
        "ip_hash": row.get("ip_hash") or "",
        "trusted": row.get("trusted", False),
        "last_seen": row["last_seen"].isoformat() if row.get("last_seen") else None,
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "revoked_at": row["revoked_at"].isoformat() if row.get("revoked_at") else None,
    }

def _row_to_event(row):
    if not row:
        return None
    meta = row.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    return {
        "id": str(row["id"]), "profile_id": str(row["profile_id"]),
        "event_type": row["event_type"],
        "device_id": str(row["device_id"]) if row.get("device_id") else None,
        "metadata": meta if isinstance(meta, dict) else {},
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }

def _row_to_privacy(row):
    if not row:
        return None
    return {
        "profile_id": str(row["profile_id"]),
        "show_online_status": row.get("show_online_status", True),
        "show_last_seen": row.get("show_last_seen", True),
        "show_read_receipts": row.get("show_read_receipts", True),
        "show_typing_indicator": row.get("show_typing_indicator", True),
        "show_profile_photo": row.get("show_profile_photo", True),
        "allow_calls": row.get("allow_calls", True),
        "allow_group_invites": row.get("allow_group_invites", True),
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


# ---------- Device Sessions ----------

def create_device_session(profile_id, device_name="", device_type="", browser="", system_os="", ip_hash="", trusted=False):
    rows = fast_query(
        "INSERT INTO chain_device_sessions (profile_id, device_name, device_type, browser, os, ip_hash, trusted) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (profile_id, device_name, device_type, browser, system_os, ip_hash, trusted),
        default=[],
    )
    if rows:
        return str(rows[0]["id"])
    return None


def get_device_sessions(profile_id):
    rows = fast_query(
        f"SELECT {_DEVICE_COLS} FROM chain_device_sessions "
        "WHERE profile_id = %s AND revoked_at IS NULL ORDER BY last_seen DESC",
        (profile_id,),
        default=[],
    )
    return [_row_to_device(r) for r in rows]


def get_device_session(device_id):
    rows = fast_query(
        f"SELECT {_DEVICE_COLS} FROM chain_device_sessions WHERE id = %s",
        (device_id,),
        default=[],
    )
    return _row_to_device(rows[0]) if rows else None


def update_device_last_seen(device_id):
    write_query("UPDATE chain_device_sessions SET last_seen = now() WHERE id = %s", (device_id,))


def revoke_device_session(device_id, profile_id=None):
    if profile_id:
        write_query(
            "UPDATE chain_device_sessions SET revoked_at = now() WHERE id = %s AND profile_id = %s",
            (device_id, profile_id),
        )
    else:
        write_query("UPDATE chain_device_sessions SET revoked_at = now() WHERE id = %s", (device_id,))


def logout_all_other_devices(current_device_id, profile_id):
    write_query(
        "UPDATE chain_device_sessions SET revoked_at = now() "
        "WHERE profile_id = %s AND id != %s AND revoked_at IS NULL",
        (profile_id, current_device_id),
    )


def is_device_active(device_id):
    rows = fast_query(
        "SELECT id FROM chain_device_sessions WHERE id = %s AND revoked_at IS NULL",
        (device_id,),
        default=[],
    )
    return len(rows) > 0


# ---------- Security Events ----------

def create_security_event(profile_id, event_type, device_id=None, metadata=None):
    meta_json = json.dumps(metadata or {})
    rows = fast_query(
        "INSERT INTO chain_security_events (profile_id, event_type, device_id, metadata) "
        "VALUES (%s, %s, %s, %s::jsonb) RETURNING id",
        (profile_id, event_type, device_id, meta_json),
        default=[],
    )
    if rows:
        return str(rows[0]["id"])
    return None


def get_security_events(profile_id, limit=50):
    rows = fast_query(
        "SELECT id, profile_id, event_type, device_id, metadata, created_at "
        "FROM chain_security_events WHERE profile_id = %s "
        "ORDER BY created_at DESC LIMIT %s",
        (profile_id, limit),
        default=[],
    )
    return [_row_to_event(r) for r in rows]


# ---------- Privacy Settings ----------

def get_privacy_settings(profile_id):
    rows = fast_query(
        "SELECT profile_id, show_online_status, show_last_seen, show_read_receipts, "
        "show_typing_indicator, show_profile_photo, allow_calls, allow_group_invites, updated_at "
        "FROM chain_privacy_settings WHERE profile_id = %s",
        (profile_id,),
        default=[],
    )
    if rows:
        return _row_to_privacy(rows[0])
    return {
        "profile_id": profile_id,
        "show_online_status": True,
        "show_last_seen": True,
        "show_read_receipts": True,
        "show_typing_indicator": True,
        "show_profile_photo": True,
        "allow_calls": True,
        "allow_group_invites": True,
        "updated_at": None,
    }


def upsert_privacy_settings(profile_id, settings):
    existing = fast_query(
        "SELECT profile_id FROM chain_privacy_settings WHERE profile_id = %s",
        (profile_id,),
        default=[],
    )
    show_online_status = settings.get("show_online_status", True)
    show_last_seen = settings.get("show_last_seen", True)
    show_read_receipts = settings.get("show_read_receipts", True)
    show_typing_indicator = settings.get("show_typing_indicator", True)
    show_profile_photo = settings.get("show_profile_photo", True)
    allow_calls = settings.get("allow_calls", True)
    allow_group_invites = settings.get("allow_group_invites", True)
    if existing:
        write_query(
            "UPDATE chain_privacy_settings SET show_online_status = %s, show_last_seen = %s, "
            "show_read_receipts = %s, show_typing_indicator = %s, show_profile_photo = %s, "
            "allow_calls = %s, allow_group_invites = %s, updated_at = now() WHERE profile_id = %s",
            (show_online_status, show_last_seen, show_read_receipts,
             show_typing_indicator, show_profile_photo, allow_calls,
             allow_group_invites, profile_id),
        )
    else:
        write_query(
            "INSERT INTO chain_privacy_settings (profile_id, show_online_status, show_last_seen, "
            "show_read_receipts, show_typing_indicator, show_profile_photo, allow_calls, allow_group_invites) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (profile_id, show_online_status, show_last_seen, show_read_receipts,
             show_typing_indicator, show_profile_photo, allow_calls, allow_group_invites),
        )
    return True


# ---------- Trusted Devices ----------

def trust_device(profile_id, device_session_id):
    existing = fast_query(
        "SELECT id FROM chain_trusted_devices WHERE profile_id = %s AND device_session_id = %s",
        (profile_id, device_session_id),
        default=[],
    )
    if not existing:
        write_query(
            "INSERT INTO chain_trusted_devices (profile_id, device_session_id) VALUES (%s, %s)",
            (profile_id, device_session_id),
        )
    write_query(
        "UPDATE chain_device_sessions SET trusted = TRUE WHERE id = %s AND profile_id = %s",
        (device_session_id, profile_id),
    )
    return True


def untrust_device(profile_id, device_session_id):
    write_query(
        "DELETE FROM chain_trusted_devices WHERE profile_id = %s AND device_session_id = %s",
        (profile_id, device_session_id),
    )
    write_query(
        "UPDATE chain_device_sessions SET trusted = FALSE WHERE id = %s AND profile_id = %s",
        (device_session_id, profile_id),
    )
    return True


def get_trusted_devices(profile_id):
    rows = fast_query(
        "SELECT td.id, td.profile_id, td.device_session_id, td.trusted_at, td.created_at, "
        "ds.device_name, ds.device_type, ds.browser, ds.os, ds.last_seen "
        "FROM chain_trusted_devices td "
        "JOIN chain_device_sessions ds ON ds.id = td.device_session_id "
        "WHERE td.profile_id = %s ORDER BY td.trusted_at DESC",
        (profile_id,),
        default=[],
    )
    result = []
    for r in rows:
        result.append({
            "id": str(r["id"]), "profile_id": str(r["profile_id"]),
            "device_session_id": str(r["device_session_id"]),
            "trusted_at": r["trusted_at"].isoformat() if r.get("trusted_at") else None,
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
            "device_name": r.get("device_name") or "",
            "device_type": r.get("device_type") or "",
            "browser": r.get("browser") or "",
            "os": r.get("os") or "",
            "last_seen": r["last_seen"].isoformat() if r.get("last_seen") else None,
        })
    return result


def get_session_by_device_id(profile_id, device_id):
    rows = fast_query(
        f"SELECT {_DEVICE_COLS} FROM chain_device_sessions WHERE id = %s AND profile_id = %s",
        (device_id, profile_id),
        default=[],
    )
    return _row_to_device(rows[0]) if rows else None
