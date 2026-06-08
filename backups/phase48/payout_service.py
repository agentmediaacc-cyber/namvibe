import os
import json
from datetime import datetime, timezone
from uuid import uuid4

from services.neon_service import fast_query, write_query, get_pool_status
from services.logging_service import log_info, log_warning, log_error, log_wallet_event
from services.wallet_service import get_wallet, get_or_create_wallet, debit_wallet
from services.socketio_service import emit_to_profile
from services.notification_engine import create_notification


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _payout_dict(row):
    return {
        "id": str(row["id"]),
        "creator_profile_id": str(row["creator_profile_id"]),
        "amount_cents": int(row["amount_cents"]),
        "currency": row.get("currency", "NAD"),
        "payout_method": row.get("payout_method", "bank"),
        "payout_details": row.get("payout_details", {}),
        "status": row.get("status", "pending"),
        "admin_note": row.get("admin_note"),
        "requested_at": row["requested_at"].isoformat() if row.get("requested_at") else None,
        "reviewed_at": row["reviewed_at"].isoformat() if row.get("reviewed_at") else None,
        "paid_at": row["paid_at"].isoformat() if row.get("paid_at") else None,
    }


def request_payout(creator_profile_id, amount_cents, payout_method="bank", payout_details=None):
    if amount_cents <= 0:
        return {"ok": False, "error": "amount_must_be_positive"}
    if amount_cents > 5000000:
        return {"ok": False, "error": "amount_exceeds_limit"}
    wallet = get_wallet(creator_profile_id)
    if not wallet:
        return {"ok": False, "error": "wallet_not_found"}
    if wallet.get("status") == "locked":
        return {"ok": False, "error": "wallet_locked"}
    if wallet["balance_cents"] < amount_cents:
        return {"ok": False, "error": "insufficient_balance"}
    pending_rows = None
    if _db_available():
        pending_rows = fast_query(
            "SELECT COALESCE(SUM(amount_cents), 0) AS pending_total FROM chain_payout_requests WHERE creator_profile_id = %s AND status IN ('pending', 'approved')",
            (creator_profile_id,), default=[{"pending_total": 0}]
        )
    pending_total = int(pending_rows[0]["pending_total"]) if pending_rows else 0
    available = wallet["balance_cents"] - pending_total
    if available < amount_cents:
        return {"ok": False, "error": "amount_exceeds_available_balance", "available_cents": available}
    if not _db_available():
        return {"ok": True, "payout_id": str(uuid4()), "status": "pending"}
    try:
        pid = str(uuid4())
        write_query(
            """INSERT INTO chain_payout_requests
               (id, creator_profile_id, amount_cents, payout_method, payout_details, status)
               VALUES (%s, %s, %s, %s, %s, 'pending')""",
            (pid, creator_profile_id, amount_cents, payout_method, json.dumps(payout_details or {}))
        )
        log_wallet_event("payout_requested", creator=creator_profile_id, amount_cents=amount_cents)
        return {"ok": True, "payout_id": pid, "status": "pending"}
    except Exception as e:
        log_error("payout_request_failed", error=str(e))
        return {"ok": False, "error": str(e)}


def get_payout_requests(status=None, limit=50, offset=0):
    if not _db_available():
        return []
    if status:
        rows = fast_query(
            "SELECT * FROM chain_payout_requests WHERE status = %s ORDER BY requested_at DESC LIMIT %s OFFSET %s",
            (status, limit, offset), default=[]
        )
    else:
        rows = fast_query(
            "SELECT * FROM chain_payout_requests ORDER BY requested_at DESC LIMIT %s OFFSET %s",
            (limit, offset), default=[]
        )
    return [_payout_dict(r) for r in rows]


def get_creator_payouts(creator_profile_id, limit=50, offset=0):
    if not _db_available():
        return []
    rows = fast_query(
        "SELECT * FROM chain_payout_requests WHERE creator_profile_id = %s ORDER BY requested_at DESC LIMIT %s OFFSET %s",
        (creator_profile_id, limit, offset), default=[]
    )
    return [_payout_dict(r) for r in rows]


def approve_payout(payout_id, admin_note=None):
    if not _db_available():
        return {"ok": False, "error": "db_unavailable"}
    rows = fast_query(
        "SELECT * FROM chain_payout_requests WHERE id = %s AND status = 'pending' LIMIT 1",
        (payout_id,), default=[]
    )
    if not rows:
        return {"ok": False, "error": "payout_not_found_or_already_processed"}
    payout = rows[0]
    creator_pid = str(payout["creator_profile_id"])
    try:
        if admin_note:
            write_query(
                "UPDATE chain_payout_requests SET status = 'approved', admin_note = %s, reviewed_at = now() WHERE id = %s AND status = 'pending'",
                (admin_note, payout_id)
            )
        else:
            write_query(
                "UPDATE chain_payout_requests SET status = 'approved', reviewed_at = now() WHERE id = %s AND status = 'pending'",
                (payout_id,)
            )
        log_wallet_event("payout_approved", payout_id=payout_id, creator=creator_pid, amount_cents=row["amount_cents"])
        emit_to_profile(creator_pid, "wallet:payout-updated", {"payout_id": payout_id, "status": "approved"})
        try:
            create_notification(
                recipient_profile_id=creator_pid,
                event_type="payout_approved",
                title="Payout Approved!",
                body=f"Your payout of N$ {int(payout['amount_cents']) / 100:.2f} has been approved",
                entity_type="payout",
                action_url="/wallet/payouts",
            )
        except Exception:
            log_warning("payout_approve_notification_failed", creator=creator_pid)
        return {"ok": True, "status": "approved"}
    except Exception as e:
        log_error("payout_approve_failed", payout_id=payout_id, error=str(e))
        return {"ok": False, "error": str(e)}


def reject_payout(payout_id, admin_note=None):
    if not _db_available():
        return {"ok": False, "error": "db_unavailable"}
    rows = fast_query(
        "SELECT * FROM chain_payout_requests WHERE id = %s AND status = 'pending' LIMIT 1",
        (payout_id,), default=[]
    )
    if not rows:
        return {"ok": False, "error": "payout_not_found_or_already_processed"}
    payout = rows[0]
    creator_pid = str(payout["creator_profile_id"])
    try:
        note = admin_note or "Rejected by admin"
        write_query(
            "UPDATE chain_payout_requests SET status = 'rejected', admin_note = %s, reviewed_at = now() WHERE id = %s AND status = 'pending'",
            (note, payout_id)
        )
        log_wallet_event("payout_rejected", payout_id=payout_id, creator=creator_pid, amount_cents=row["amount_cents"])
        emit_to_profile(creator_pid, "wallet:payout-updated", {"payout_id": payout_id, "status": "rejected"})
        try:
            create_notification(
                recipient_profile_id=creator_pid,
                event_type="payout_rejected",
                title="Payout Rejected",
                body=f"Your payout request for N$ {int(payout['amount_cents']) / 100:.2f} was rejected",
                entity_type="payout",
                action_url="/wallet/payouts",
            )
        except Exception:
            log_warning("payout_reject_notification_failed", creator=creator_pid)
        return {"ok": True, "status": "rejected"}
    except Exception as e:
        log_error("payout_reject_failed", payout_id=payout_id, error=str(e))
        return {"ok": False, "error": str(e)}


def mark_payout_paid(payout_id):
    if not _db_available():
        return {"ok": False, "error": "db_unavailable"}
    rows = fast_query(
        "SELECT * FROM chain_payout_requests WHERE id = %s AND status = 'approved' LIMIT 1",
        (payout_id,), default=[]
    )
    if not rows:
        return {"ok": False, "error": "payout_not_found_or_not_approved"}
    payout = rows[0]
    creator_id = str(payout["creator_profile_id"])
    amount = int(payout["amount_cents"])
    debit = debit_wallet(
        creator_id, amount,
        description=f"Payout: {payout_id}",
        transaction_type="payout",
    )
    if not debit.get("ok"):
        return debit
    try:
        write_query(
            "UPDATE chain_payout_requests SET status = 'paid', paid_at = now() WHERE id = %s AND status = 'approved'",
            (payout_id,)
        )
        log_wallet_event("payout_paid", payout_id=payout_id, creator=creator_id, amount_cents=amount)
        emit_to_profile(creator_id, "wallet:payout-updated", {"payout_id": payout_id, "status": "paid"})
        emit_to_profile(creator_id, "wallet:balance-updated", {"balance_cents": debit.get("balance_cents", 0)})
        try:
            create_notification(
                recipient_profile_id=creator_id,
                event_type="payout_paid",
                title="Payout Completed!",
                body=f"Your payout of N$ {amount / 100:.2f} has been paid",
                entity_type="payout",
                action_url="/wallet/payouts",
            )
        except Exception:
            log_warning("payout_paid_notification_failed", creator=creator_id)
        return {"ok": True, "status": "paid"}
    except Exception as e:
        log_error("payout_mark_paid_failed", payout_id=payout_id, error=str(e))
        return {"ok": False, "error": str(e)}
