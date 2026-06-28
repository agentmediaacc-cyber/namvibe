import json, os
from datetime import datetime, timezone
from uuid import uuid4
from services.neon_service import fast_query, write_query, get_pool_status
from services.logging_service import log_error, log_wallet_event
from services.wallet_service import get_wallet, get_or_create_wallet

PLATFORM_FEE_PCT = 5

def _db():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    s = get_pool_status()
    return bool(s.get("pool_ready") or s.get("recent_success"))

def _utcnow():
    return datetime.now(timezone.utc)

def _cents(v):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError, OverflowError):
        return 0

def credit(profile_id, amount_cents, description="", tx_type="credit", ref_type=None, ref_id=None, counterparty=None, idempotency_key=None):
    if amount_cents <= 0:
        return {"ok": False, "error": "amount_must_be_positive"}
    wallet = get_or_create_wallet(profile_id)
    if not wallet:
        return {"ok": False, "error": "wallet_not_found"}
    if wallet.get("status") == "locked":
        return {"ok": False, "error": "wallet_locked"}
    if idempotency_key:
        existing = _check_idempotency(idempotency_key, profile_id, tx_type)
        if existing:
            return {"ok": True, "idempotent": True, "transaction_id": existing.get("id")}
    tx_id = str(uuid4())
    if not _db():
        return {"ok": True, "balance_cents": amount_cents, "transaction_id": tx_id}
    try:
        write_query(
            "UPDATE chain_wallets SET balance_cents = balance_cents + %s, lifetime_earned_cents = lifetime_earned_cents + %s, updated_at = now() WHERE profile_id = %s",
            (amount_cents, amount_cents, profile_id)
        )
        _insert_tx(wallet["id"], profile_id, amount_cents, 0, amount_cents, tx_type, "credit", counterparty=counterparty, ref_type=ref_type, ref_id=ref_id, desc=description, idempotency_key=idempotency_key, tx_id=tx_id)
        updated = get_wallet(profile_id)
        log_wallet_event("ledger_credit", profile_id=profile_id, amount_cents=amount_cents, tx_type=tx_type)
        return {"ok": True, "balance_cents": updated["balance_cents"] if updated else wallet["balance_cents"] + amount_cents, "transaction_id": tx_id}
    except Exception as e:
        log_error("ledger_credit_failed", profile_id=profile_id, error=str(e))
        return {"ok": False, "error": f"credit_failed: {e}"}

def debit(profile_id, amount_cents, description="", tx_type="debit", ref_type=None, ref_id=None, counterparty=None, idempotency_key=None):
    if amount_cents <= 0:
        return {"ok": False, "error": "amount_must_be_positive"}
    if idempotency_key:
        existing = _check_idempotency(idempotency_key, profile_id, tx_type)
        if existing:
            return {"ok": True, "idempotent": True, "transaction_id": existing.get("id")}
    if not _db():
        return {"ok": True, "balance_cents": 0, "transaction_id": str(uuid4())}
    wallet = get_or_create_wallet(profile_id)
    if not wallet:
        return {"ok": False, "error": "wallet_not_found"}
    if wallet.get("status") == "locked":
        return {"ok": False, "error": "wallet_locked"}
    if wallet["balance_cents"] < amount_cents:
        return {"ok": False, "error": "insufficient_balance"}
        existing = _check_idempotency(idempotency_key, profile_id, tx_type)
        if existing:
            return {"ok": True, "idempotent": True, "transaction_id": existing.get("id")}
    tx_id = str(uuid4())
    if not _db():
        return {"ok": True, "balance_cents": wallet["balance_cents"] - amount_cents, "transaction_id": tx_id}
    try:
        write_query(
            "UPDATE chain_wallets SET balance_cents = balance_cents - %s, lifetime_spent_cents = lifetime_spent_cents + %s, updated_at = now() WHERE profile_id = %s AND balance_cents >= %s",
            (amount_cents, amount_cents, profile_id, amount_cents)
        )
        _insert_tx(wallet["id"], profile_id, -amount_cents, 0, -amount_cents, tx_type, "debit", counterparty=counterparty, ref_type=ref_type, ref_id=ref_id, desc=description, idempotency_key=idempotency_key, tx_id=tx_id)
        updated = get_wallet(profile_id)
        log_wallet_event("ledger_debit", profile_id=profile_id, amount_cents=amount_cents, tx_type=tx_type)
        return {"ok": True, "balance_cents": updated["balance_cents"] if updated else wallet["balance_cents"] - amount_cents, "transaction_id": tx_id}
    except Exception as e:
        log_error("ledger_debit_failed", profile_id=profile_id, error=str(e))
        return {"ok": False, "error": f"debit_failed: {e}"}

def hold(profile_id, amount_cents, reason="", related_type=None, related_id=None):
    if amount_cents <= 0:
        return {"ok": False, "error": "amount_must_be_positive"}
    hold_id = str(uuid4())
    if not _db():
        return {"ok": True, "hold_id": hold_id}
    wallet = get_or_create_wallet(profile_id)
    if not wallet:
        return {"ok": False, "error": "wallet_not_found"}
    if wallet.get("status") == "locked":
        return {"ok": False, "error": "wallet_locked"}
    available = wallet["balance_cents"] - wallet.get("pending_cents", 0) - wallet.get("withdrawable_cents", 0)
    if available < amount_cents:
        return {"ok": False, "error": "insufficient_available_balance"}
    try:
        write_query(
            "UPDATE chain_wallets SET withdrawable_cents = withdrawable_cents - %s, updated_at = now() WHERE profile_id = %s AND withdrawable_cents >= %s",
            (amount_cents, profile_id, amount_cents)
        )
        write_query(
            "INSERT INTO chain_wallet_holds (id, wallet_id, profile_id, amount_cents, reason, status, related_type, related_id) VALUES (%s, %s, %s, %s, %s, 'active', %s, %s)",
            (hold_id, wallet.get("id"), profile_id, amount_cents, reason, related_type, related_id)
        )
        log_wallet_event("hold_created", profile_id=profile_id, amount_cents=amount_cents, hold_id=hold_id)
        return {"ok": True, "hold_id": hold_id}
    except Exception as e:
        log_error("hold_failed", profile_id=profile_id, error=str(e))
        return {"ok": False, "error": f"hold_failed: {e}"}

def release_hold(hold_id):
    if not _db():
        return {"ok": True}
    rows = fast_query("SELECT * FROM chain_wallet_holds WHERE id = %s AND status = 'active' LIMIT 1", (hold_id,), default=[])
    if not rows:
        return {"ok": False, "error": "hold_not_found_or_not_active"}
    h = rows[0]
    try:
        write_query("UPDATE chain_wallet_holds SET status = 'released', released_at = now() WHERE id = %s AND status = 'active'", (hold_id,))
        write_query("UPDATE chain_wallets SET withdrawable_cents = withdrawable_cents + %s, updated_at = now() WHERE profile_id = %s", (h["amount_cents"], h["profile_id"]))
        log_wallet_event("hold_released", hold_id=hold_id, profile_id=h["profile_id"], amount_cents=h["amount_cents"])
        return {"ok": True}
    except Exception as e:
        log_error("hold_release_failed", hold_id=hold_id, error=str(e))
        return {"ok": False, "error": f"release_failed: {e}"}

def capture_hold(hold_id):
    if not _db():
        return {"ok": True}
    rows = fast_query("SELECT * FROM chain_wallet_holds WHERE id = %s AND status = 'active' LIMIT 1", (hold_id,), default=[])
    if not rows:
        return {"ok": False, "error": "hold_not_found_or_not_active"}
    h = rows[0]
    try:
        write_query("UPDATE chain_wallet_holds SET status = 'captured', released_at = now() WHERE id = %s AND status = 'active'", (hold_id,))
        write_query("UPDATE chain_wallets SET balance_cents = balance_cents - %s, lifetime_spent_cents = lifetime_spent_cents + %s, updated_at = now() WHERE profile_id = %s AND balance_cents >= %s",
                     (h["amount_cents"], h["amount_cents"], h["profile_id"], h["amount_cents"]))
        log_wallet_event("hold_captured", hold_id=hold_id, profile_id=h["profile_id"], amount_cents=h["amount_cents"])
        return {"ok": True}
    except Exception as e:
        log_error("hold_capture_failed", hold_id=hold_id, error=str(e))
        return {"ok": False, "error": f"capture_failed: {e}"}

def reverse(profile_id, amount_cents, description="", ref_type=None, ref_id=None):
    return credit(profile_id, amount_cents, description=description, tx_type="reversal", ref_type=ref_type, ref_id=ref_id)

def reconcile(profile_id):
    if not _db():
        return {"ok": True, "reconciled": True}
    try:
        rows = fast_query(
            "SELECT COALESCE(SUM(amount_cents), 0) AS total FROM chain_wallet_transactions WHERE profile_id = %s AND direction = 'credit' AND status = 'completed'",
            (profile_id,), default=[{"total": 0}]
        )
        total_credited = _cents(rows[0]["total"]) if rows else 0
        rows = fast_query(
            "SELECT COALESCE(SUM(ABS(amount_cents)), 0) AS total FROM chain_wallet_transactions WHERE profile_id = %s AND direction = 'debit' AND status = 'completed'",
            (profile_id,), default=[{"total": 0}]
        )
        total_debited = _cents(rows[0]["total"]) if rows else 0
        expected_balance = total_credited - total_debited
        wallet = get_wallet(profile_id)
        if not wallet:
            return {"ok": False, "error": "wallet_not_found"}
        actual_balance = _cents(wallet.get("balance_cents", 0))
        if expected_balance != actual_balance:
            write_query("UPDATE chain_wallets SET balance_cents = %s, updated_at = now() WHERE profile_id = %s", (expected_balance, profile_id))
            log_wallet_event("balance_reconciled", profile_id=profile_id, expected=expected_balance, actual=actual_balance)
            return {"ok": True, "reconciled": True, "expected": expected_balance, "actual": actual_balance, "fixed": True}
        return {"ok": True, "reconciled": True, "expected": expected_balance, "actual": actual_balance, "fixed": False}
    except Exception as e:
        log_error("reconcile_failed", profile_id=profile_id, error=str(e))
        return {"ok": False, "error": f"reconcile_failed: {e}"}

def transfer(from_pid, to_pid, amount_cents, description="", idempotency_key=None):
    if from_pid == to_pid:
        return {"ok": False, "error": "self_transfer_not_allowed"}
    debit_key = f"{idempotency_key}:debit" if idempotency_key else None
    credit_key = f"{idempotency_key}:credit" if idempotency_key else None
    dr = debit(from_pid, amount_cents, description=f"Transfer: {description}", tx_type="transfer_out", counterparty=to_pid, idempotency_key=debit_key)
    if not dr.get("ok"):
        return dr
    cr = credit(to_pid, amount_cents, description=f"Transfer: {description}", tx_type="transfer_in", counterparty=from_pid, idempotency_key=credit_key)
    if not cr.get("ok"):
        reverse(from_pid, amount_cents, description=f"Transfer reversal: {description}")
        return {"ok": False, "error": "transfer_reversed"}
    return {"ok": True, "transaction_id": dr.get("transaction_id"), "idempotent": bool(dr.get("idempotent") and cr.get("idempotent"))}

def _insert_tx(wallet_id, profile_id, amount_cents, fee_cents, net_cents, tx_type, direction, counterparty=None, ref_type=None, ref_id=None, desc="", idempotency_key=None, tx_id=None):
    if not tx_id:
        tx_id = str(uuid4())
    if not _db():
        return tx_id
    try:
        write_query(
            "INSERT INTO chain_wallet_transactions (id, wallet_id, profile_id, counterparty_profile_id, transaction_type, direction, amount_cents, fee_cents, net_amount_cents, currency, status, reference_type, reference_id, description, idempotency_key, metadata) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'NAD', 'completed', %s, %s, %s, %s, %s)",
            (tx_id, wallet_id, profile_id, counterparty, tx_type, direction, amount_cents, fee_cents, net_cents, ref_type, ref_id, desc, idempotency_key, json.dumps({}))
        )
        return tx_id
    except Exception as e:
        log_error("ledger_tx_insert_failed", error=str(e))
        return tx_id

def _check_idempotency(key, profile_id, action_type):
    if not key:
        return None
    rows = fast_query(
        "SELECT id FROM chain_wallet_transactions WHERE idempotency_key = %s AND profile_id = %s AND transaction_type = %s AND status = 'completed' LIMIT 1",
        (key, profile_id, action_type), default=[]
    )
    return rows[0] if rows else None
