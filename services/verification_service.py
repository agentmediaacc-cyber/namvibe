"""Full identity verification service: country, document, selfie, liveness, auto-checks, admin review."""
import uuid
import json
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query
from services.logging_service import log_info, log_error, log_warning
from services.notification_engine import create_notification
from services.verification_countries import COUNTRIES_WITH_FLAGS

# ── Countries & document types ──────────────────────────────────────────

COUNTRIES = COUNTRIES_WITH_FLAGS

DOCUMENT_TYPES = [
    {"id": "national_id", "label": "National ID Card", "has_back": True, "icon": "id-card"},
    {"id": "passport", "label": "Passport", "has_back": False, "icon": "passport"},
    {"id": "drivers_licence", "label": "Driver's Licence", "has_back": True, "icon": "license"},
    {"id": "residence_permit", "label": "Residence Permit", "has_back": True, "icon": "home"},
    {"id": "refugee_travel", "label": "Refugee/Travel Document", "has_back": True, "icon": "globe"},
]

VERIFICATION_LEVELS = {
    0: {"name": "Email Verified", "badge_color": "#6b7280", "badge_icon": "envelope"},
    1: {"name": "Phone Verified", "badge_color": "#9ca3af", "badge_icon": "phone"},
    2: {"name": "Identity Verified", "badge_color": "#1d9bf0", "badge_icon": "check-circle"},
    3: {"name": "Creator Verified", "badge_color": "#ec4899", "badge_icon": "star"},
    4: {"name": "Business Verified", "badge_color": "#f59e0b", "badge_icon": "briefcase"},
    5: {"name": "Government Verified", "badge_color": "#10b981", "badge_icon": "building"},
    6: {"name": "Healthcare Verified", "badge_color": "#ef4444", "badge_icon": "heart-pulse"},
}


def get_acceptable_docs(country):
    rows = fast_query(
        "SELECT accepted_docs, requires_back_photo, requires_residence_permit FROM chain_verification_country_rules WHERE country = %s",
        (country,), default=[]
    )
    if not rows:
        return [d["id"] for d in DOCUMENT_TYPES], True
    r = rows[0]
    return r["accepted_docs"] or [d["id"] for d in DOCUMENT_TYPES], r.get("requires_back_photo", True)


def get_or_create_verification_request(profile_id):
    existing = fast_query(
        "SELECT * FROM chain_verification_requests_v2 WHERE profile_id = %s ORDER BY created_at DESC LIMIT 1",
        (profile_id,), default=[]
    )
    if existing:
        req = existing[0]
        if req["status"] in ("pending", "needs_review"):
            return req, None
        if req["status"] == "approved":
            return req, None
    req_id = str(uuid.uuid4())
    try:
        write_query(
            "INSERT INTO chain_verification_requests_v2 (id, profile_id, status, created_at) VALUES (%s, %s, 'pending', now())",
            (req_id, profile_id)
        )
        log_info("verification_request_created", profile_id=profile_id, request_id=req_id)
        return {"id": req_id, "profile_id": profile_id, "status": "pending", "country": None, "document_type": None}, None
    except Exception as e:
        log_error("verification_request_create_failed", profile_id=profile_id, error=str(e))
        return None, str(e)


def save_step_country(profile_id, country):
    req, err = get_or_create_verification_request(profile_id)
    if err:
        return {"ok": False, "error": err}
    docs, requires_back = get_acceptable_docs(country)
    try:
        write_query(
            "UPDATE chain_verification_requests_v2 SET country = %s, updated_at = now() WHERE id = %s",
            (country, req["id"])
        )
        return {"ok": True, "request_id": req["id"], "acceptable_docs": docs, "requires_back_photo": requires_back}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def save_step_document_type(profile_id, doc_type):
    req, err = get_or_create_verification_request(profile_id)
    if err:
        return {"ok": False, "error": err}
    has_back = True
    for d in DOCUMENT_TYPES:
        if d["id"] == doc_type:
            has_back = d["has_back"]
            break
    try:
        write_query(
            "UPDATE chain_verification_requests_v2 SET document_type = %s, updated_at = now() WHERE id = %s",
            (doc_type, req["id"])
        )
        return {"ok": True, "request_id": req["id"], "has_back": has_back}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def save_step_upload(profile_id, front_url, back_url=None):
    req, err = get_or_create_verification_request(profile_id)
    if err:
        return {"ok": False, "error": err}
    try:
        write_query(
            "UPDATE chain_verification_requests_v2 SET doc_front_url = %s, doc_back_url = %s, updated_at = now() WHERE id = %s",
            (front_url, back_url, req["id"])
        )
        return {"ok": True, "request_id": req["id"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def save_step_selfie(profile_id, selfie_url, liveness_data=None):
    req, err = get_or_create_verification_request(profile_id)
    if err:
        return {"ok": False, "error": err}
    liveness_json = json.dumps(liveness_data or {})
    try:
        write_query(
            "UPDATE chain_verification_requests_v2 SET selfie_url = %s, liveness_data = %s::jsonb, updated_at = now() WHERE id = %s",
            (selfie_url, liveness_json, req["id"])
        )
        return {"ok": True, "request_id": req["id"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def save_step_auto_checks(profile_id, checks=None, risk_indicators=None):
    req, err = get_or_create_verification_request(profile_id)
    if err:
        return {"ok": False, "error": err}
    checks_json = json.dumps(checks or {})
    risk_json = json.dumps(risk_indicators or [])
    try:
        write_query(
            "UPDATE chain_verification_requests_v2 SET auto_checks = %s::jsonb, risk_indicators = %s::jsonb, status = 'needs_review', updated_at = now() WHERE id = %s",
            (checks_json, risk_json, req["id"])
        )
        return {"ok": True, "request_id": req["id"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_my_verification(profile_id):
    rows = fast_query(
        "SELECT * FROM chain_verification_requests_v2 WHERE profile_id = %s ORDER BY created_at DESC LIMIT 1",
        (profile_id,), default=[]
    )
    if not rows:
        return None
    r = rows[0]
    if r.get("auto_checks") and isinstance(r["auto_checks"], str):
        try:
            r["auto_checks"] = json.loads(r["auto_checks"])
        except (json.JSONDecodeError, TypeError):
            pass
    if r.get("liveness_data") and isinstance(r["liveness_data"], str):
        try:
            r["liveness_data"] = json.loads(r["liveness_data"])
        except (json.JSONDecodeError, TypeError):
            pass
    if r.get("risk_indicators") and isinstance(r["risk_indicators"], str):
        try:
            r["risk_indicators"] = json.loads(r["risk_indicators"])
        except (json.JSONDecodeError, TypeError):
            pass
    return r


def get_verification_detail(profile_id):
    return get_my_verification(profile_id)


def get_profile_verification_status(profile_id):
    level_row = fast_query(
        "SELECT verification_level, is_verified, verified FROM chain_profiles WHERE id = %s",
        (profile_id,), default=[]
    )
    level = 0
    is_verified = False
    if level_row:
        level = level_row[0].get("verification_level") or 0
        is_verified = bool(level_row[0].get("is_verified") or level_row[0].get("verified"))
    req = get_my_verification(profile_id)
    return {
        "level": level,
        "is_verified": is_verified,
        "has_request": req is not None,
        "request_status": req["status"] if req else None,
        "level_info": VERIFICATION_LEVELS.get(level, {}),
    }


# ── Admin ───────────────────────────────────────────────────────────────

def list_pending_verifications(limit=50):
    return fast_query(
        """SELECT v.*, p.username, p.display_name, p.full_name, p.email, p.avatar_url, p.verification_level
           FROM chain_verification_requests_v2 v
           JOIN chain_profiles p ON v.profile_id = p.id
           WHERE v.status IN ('pending', 'needs_review')
           ORDER BY v.created_at ASC LIMIT %s""",
        (limit,), default=[]
    )


def list_all_verifications(limit=50, status=None):
    if status:
        return fast_query(
            """SELECT v.*, p.username, p.display_name, p.full_name, p.email, p.avatar_url, p.verification_level
               FROM chain_verification_requests_v2 v
               JOIN chain_profiles p ON v.profile_id = p.id
               WHERE v.status = %s
               ORDER BY v.updated_at DESC LIMIT %s""",
            (status, limit), default=[]
        )
    return fast_query(
        """SELECT v.*, p.username, p.display_name, p.full_name, p.email, p.avatar_url, p.verification_level
           FROM chain_verification_requests_v2 v
           JOIN chain_profiles p ON v.profile_id = p.id
           ORDER BY v.updated_at DESC LIMIT %s""",
        (limit,), default=[]
    )


def get_verification_by_id(request_id):
    rows = fast_query(
        """SELECT v.*, p.username, p.display_name, p.full_name, p.email, p.avatar_url, p.verification_level
           FROM chain_verification_requests_v2 v
           JOIN chain_profiles p ON v.profile_id = p.id
           WHERE v.id = %s LIMIT 1""",
        (request_id,), default=[]
    )
    if not rows:
        return None
    r = rows[0]
    for field in ("auto_checks", "liveness_data", "risk_indicators"):
        if r.get(field) and isinstance(r[field], str):
            try:
                r[field] = json.loads(r[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return r


def _audit_log(request_id, action, admin_id, notes=None):
    log_id = str(uuid.uuid4())
    write_query(
        "INSERT INTO chain_verification_audit_log (id, request_id, action, admin_id, notes, created_at) VALUES (%s, %s, %s, %s, %s, now())",
        (log_id, request_id, action, admin_id, notes)
    )


def approve_verification(request_id, admin_id, notes=None, verification_level=2):
    req_row = fast_query("SELECT profile_id, country FROM chain_verification_requests_v2 WHERE id = %s", (request_id,), default=[])
    if not req_row:
        return {"ok": False, "error": "Request not found"}
    profile_id = req_row[0]["profile_id"]
    country = req_row[0].get("country")
    try:
        write_query(
            """UPDATE chain_verification_requests_v2
               SET status = 'approved', admin_notes = %s, reviewed_by = %s, reviewed_at = now(), updated_at = now()
               WHERE id = %s""",
            (notes, admin_id, request_id)
        )
        write_query(
            "UPDATE chain_profiles SET is_verified = TRUE, verified = TRUE, verification_level = %s, verification_country = %s, verification_date = now() WHERE id = %s",
            (verification_level, country, profile_id)
        )
        _audit_log(request_id, "approved", admin_id, notes)
        create_notification(
            profile_id, "verification_approved",
            "✓ Identity Verified",
            "Your identity verification has been approved. Your verified badge is now live on your profile!",
            action_url="/verification/center"
        )
        log_info("verification_approved", profile_id=profile_id, request_id=request_id, admin_id=admin_id)
        return {"ok": True}
    except Exception as e:
        log_error("verification_approve_failed", request_id=request_id, error=str(e))
        return {"ok": False, "error": str(e)}


def reject_verification(request_id, admin_id, reason=None):
    req_row = fast_query("SELECT profile_id FROM chain_verification_requests_v2 WHERE id = %s", (request_id,), default=[])
    if not req_row:
        return {"ok": False, "error": "Request not found"}
    profile_id = req_row[0]["profile_id"]
    try:
        write_query(
            """UPDATE chain_verification_requests_v2
               SET status = 'rejected', rejection_reason = %s, admin_notes = %s, reviewed_by = %s, reviewed_at = now(), updated_at = now()
               WHERE id = %s""",
            (reason, reason, admin_id, request_id)
        )
        _audit_log(request_id, "rejected", admin_id, reason)
        create_notification(
            profile_id, "verification_rejected",
            "Verification Rejected",
            f"Your verification request was rejected. Reason: {reason or 'Documents did not meet requirements.'}. You can re-apply with corrected documents.",
            action_url="/verification/center"
        )
        log_info("verification_rejected", profile_id=profile_id, request_id=request_id)
        return {"ok": True}
    except Exception as e:
        log_error("verification_reject_failed", request_id=request_id, error=str(e))
        return {"ok": False, "error": str(e)}


def mark_needs_review(request_id, admin_id, notes=None):
    req_row = fast_query("SELECT profile_id FROM chain_verification_requests_v2 WHERE id = %s", (request_id,), default=[])
    if not req_row:
        return {"ok": False, "error": "Request not found"}
    profile_id = req_row[0]["profile_id"]
    try:
        write_query(
            "UPDATE chain_verification_requests_v2 SET status = 'needs_review', admin_notes = %s, updated_at = now() WHERE id = %s",
            (notes, request_id)
        )
        _audit_log(request_id, "needs_review", admin_id, notes)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def request_more_info(request_id, admin_id, notes=None):
    req_row = fast_query("SELECT profile_id FROM chain_verification_requests_v2 WHERE id = %s", (request_id,), default=[])
    if not req_row:
        return {"ok": False, "error": "Request not found"}
    profile_id = req_row[0]["profile_id"]
    try:
        write_query(
            "UPDATE chain_verification_requests_v2 SET status = 'needs_more_info', admin_notes = %s, updated_at = now() WHERE id = %s",
            (notes, request_id)
        )
        _audit_log(request_id, "requested_info", admin_id, notes)
        create_notification(
            profile_id, "verification_needs_info",
            "Verification Needs More Info",
            f"Additional information needed: {notes or 'Please provide clearer documents.'}",
            action_url="/verification/center"
        )
        log_info("verification_requested_info", profile_id=profile_id, request_id=request_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def suspend_verification(request_id, admin_id, reason=None):
    req_row = fast_query("SELECT profile_id FROM chain_verification_requests_v2 WHERE id = %s", (request_id,), default=[])
    if not req_row:
        return {"ok": False, "error": "Request not found"}
    profile_id = req_row[0]["profile_id"]
    try:
        write_query(
            "UPDATE chain_verification_requests_v2 SET status = 'suspended', admin_notes = %s, updated_at = now() WHERE id = %s",
            (reason, request_id)
        )
        write_query(
            "UPDATE chain_profiles SET verification_level = 0 WHERE id = %s",
            (profile_id,)
        )
        _audit_log(request_id, "suspended", admin_id, reason)
        create_notification(
            profile_id, "verification_suspended",
            "Verification Suspended",
            f"Your verification has been suspended. Reason: {reason or 'Violation of terms.'}",
            action_url="/verification/center"
        )
        log_info("verification_suspended", profile_id=profile_id, request_id=request_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_audit_log(request_id):
    return fast_query(
        "SELECT * FROM chain_verification_audit_log WHERE request_id = %s ORDER BY created_at DESC",
        (request_id,), default=[]
    )


def get_dashboard_stats():
    total = fast_query("SELECT count(*) as c FROM chain_verification_requests_v2", default=[])
    pending = fast_query("SELECT count(*) as c FROM chain_verification_requests_v2 WHERE status IN ('pending', 'needs_review')", default=[])
    approved_today = fast_query("SELECT count(*) as c FROM chain_verification_requests_v2 WHERE status = 'approved' AND reviewed_at >= date_trunc('day', now())", default=[])
    rejected_today = fast_query("SELECT count(*) as c FROM chain_verification_requests_v2 WHERE status = 'rejected' AND reviewed_at >= date_trunc('day', now())", default=[])
    by_country = fast_query(
        "SELECT country, count(*) as c FROM chain_verification_requests_v2 WHERE country IS NOT NULL GROUP BY country ORDER BY c DESC",
        default=[]
    )
    return {
        "total": total[0]["c"] if total else 0,
        "pending": pending[0]["c"] if pending else 0,
        "approved_today": approved_today[0]["c"] if approved_today else 0,
        "rejected_today": rejected_today[0]["c"] if rejected_today else 0,
        "by_country": by_country,
    }
