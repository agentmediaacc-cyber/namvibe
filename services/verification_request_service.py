"""Verification request service with document uploads."""
import uuid
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query
from services.logging_service import log_info

def submit_verification(profile_id, id_front_url=None, id_back_url=None,
                        address_proof_url=None, address_proof_type="water_bill",
                        selfie_video_url=None, whatsapp_phone=None, whatsapp_code=None):
    existing = fast_query(
        "SELECT id, status FROM chain_verification_documents WHERE profile_id = %s ORDER BY submitted_at DESC LIMIT 1",
        (profile_id,), default=[]
    )
    if existing:
        old = existing[0]
        if old["status"] in ("pending",):
            return {"ok": False, "error": "You already have a pending verification request."}
        if old["status"] == "approved":
            return {"ok": False, "error": "You are already verified."}
    vid = str(uuid.uuid4())
    try:
        write_query(
            """INSERT INTO chain_verification_documents 
               (id, profile_id, id_front_url, id_back_url, address_proof_url, 
                address_proof_type, selfie_video_url, whatsapp_phone, whatsapp_code, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')""",
            (vid, profile_id, id_front_url, id_back_url, address_proof_url,
             address_proof_type, selfie_video_url, whatsapp_phone, whatsapp_code)
        )
        log_info("verification_submitted", profile_id=profile_id, request_id=vid)
        return {"ok": True, "request_id": vid}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_verification_status(profile_id):
    rows = fast_query(
        "SELECT id, status, admin_notes, submitted_at, reviewed_at FROM chain_verification_documents WHERE profile_id = %s ORDER BY submitted_at DESC LIMIT 1",
        (profile_id,), default=[]
    )
    if not rows:
        return {"status": "none", "submitted": False}
    r = rows[0]
    return {"status": r["status"], "request_id": r["id"], "admin_notes": r.get("admin_notes"),
            "submitted_at": r["submitted_at"].isoformat() if r.get("submitted_at") else None,
            "reviewed_at": r["reviewed_at"].isoformat() if r.get("reviewed_at") else None,
            "submitted": True}

def get_pending_verifications(limit=50):
    rows = fast_query(
        """SELECT v.*, p.username, p.display_name, p.full_name, p.email, p.avatar_url 
           FROM chain_verification_documents v 
           JOIN chain_profiles p ON v.profile_id = p.id 
           WHERE v.status = 'pending' 
           ORDER BY v.submitted_at DESC LIMIT %s""",
        (limit,), default=[]
    )
    return rows

def get_all_verifications(limit=50):
    rows = fast_query(
        """SELECT v.*, p.username, p.display_name, p.full_name, p.email, p.avatar_url 
           FROM chain_verification_documents v 
           JOIN chain_profiles p ON v.profile_id = p.id 
           ORDER BY v.submitted_at DESC LIMIT %s""",
        (limit,), default=[]
    )
    return rows

def get_verification_detail(request_id):
    rows = fast_query(
        """SELECT v.*, p.username, p.display_name, p.full_name, p.email, p.avatar_url 
           FROM chain_verification_documents v 
           JOIN chain_profiles p ON v.profile_id = p.id 
           WHERE v.id = %s LIMIT 1""",
        (request_id,), default=[]
    )
    return rows[0] if rows else None

def approve_verification(request_id, admin_id, notes=None):
    row = fast_query("SELECT profile_id FROM chain_verification_documents WHERE id = %s", (request_id,), default=[])
    if not row:
        return {"ok": False, "error": "Request not found."}
    profile_id = row[0]["profile_id"]
    try:
        write_query(
            "UPDATE chain_verification_documents SET status = 'approved', reviewed_by = %s, admin_notes = %s, reviewed_at = now() WHERE id = %s",
            (admin_id, notes, request_id)
        )
        write_query(
            "UPDATE chain_profiles SET is_verified = TRUE, verified = TRUE, verification_date = now() WHERE id = %s",
            (profile_id,)
        )
        from services.notification_engine import create_notification
        create_notification(
            profile_id, "verification_approved",
            "Verification Approved",
            "Your profile verification has been approved. You now have a verified badge!",
            action_url="/profile/settings"
        )
        log_info("verification_approved", profile_id=profile_id, request_id=request_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def reject_verification(request_id, admin_id, notes=None):
    row = fast_query("SELECT profile_id FROM chain_verification_documents WHERE id = %s", (request_id,), default=[])
    if not row:
        return {"ok": False, "error": "Request not found."}
    profile_id = row[0]["profile_id"]
    try:
        write_query(
            "UPDATE chain_verification_documents SET status = 'rejected', reviewed_by = %s, admin_notes = %s, reviewed_at = now() WHERE id = %s",
            (admin_id, notes, request_id)
        )
        from services.notification_engine import create_notification
        create_notification(
            profile_id, "verification_rejected",
            "Verification Rejected",
            f"Your verification request was rejected. Reason: {notes or 'No reason provided.'}",
            action_url="/profile/verification"
        )
        log_info("verification_rejected", profile_id=profile_id, request_id=request_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def request_more_info(request_id, admin_id, notes=None):
    row = fast_query("SELECT profile_id FROM chain_verification_documents WHERE id = %s", (request_id,), default=[])
    if not row:
        return {"ok": False, "error": "Request not found."}
    profile_id = row[0]["profile_id"]
    try:
        write_query(
            "UPDATE chain_verification_documents SET status = 'needs_more_info', reviewed_by = %s, admin_notes = %s, reviewed_at = now() WHERE id = %s",
            (admin_id, notes, request_id)
        )
        from services.notification_engine import create_notification
        create_notification(
            profile_id, "verification_needs_info",
            "Verification Needs More Info",
            f"Your verification needs more information: {notes or 'Please provide additional documents.'}",
            action_url="/profile/verification"
        )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
