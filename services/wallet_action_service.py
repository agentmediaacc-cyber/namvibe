import random
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from services.admin_auth_service import log_admin_action
from services.supabase_safe import safe_insert, safe_select, safe_update
from services.wallet_service import ensure_wallet

COIN_VALUE_NAD = 5


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _safe_int(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def get_or_create_wallet(profile_id):
    wallet = ensure_wallet(profile_id) or {}
    available = _safe_int(wallet.get("available_balance") or wallet.get("coin_balance"), 0)
    pending = _safe_int(wallet.get("pending_withdrawal_balance") or wallet.get("pending_withdrawal"), 0)
    safe_update(
        "chain_wallets",
        {
            "available_balance": max(available, 0),
            "coin_balance": max(available, 0),
            "pending_withdrawal_balance": max(pending, 0),
            "pending_withdrawal": max(pending, 0),
            "updated_at": _utcnow_iso(),
        },
        eq={"profile_id": profile_id},
    )
    rows = safe_select("chain_wallets", filters={"profile_id": profile_id}, limit=1, order_by=None)
    if rows:
        return rows[0]
    wallet["profile_id"] = profile_id
    wallet["available_balance"] = max(available, 0)
    wallet["pending_withdrawal_balance"] = max(pending, 0)
    wallet["coin_balance"] = max(available, 0)
    return wallet


def _record_platform_ledger(event_type, source_table, source_id, profile_id, gross_coins=0, platform_fee_coins=0, net_coins=0, amount_nad=0, description=None):
    payload = {
        "event_type": event_type,
        "source_table": source_table,
        "source_id": source_id,
        "profile_id": profile_id,
        "gross_coins": _safe_int(gross_coins, 0),
        "platform_fee_coins": _safe_int(platform_fee_coins, 0),
        "net_coins": _safe_int(net_coins, 0),
        "amount_nad": amount_nad or 0,
        "description": description,
        "created_at": _utcnow_iso(),
    }
    inserted = safe_insert("chain_platform_ledger", payload)
    return inserted[0] if inserted else payload


def record_wallet_transaction(profile_id, transaction_type, direction, coins=0, amount_nad=0, reference_number=None, related_table=None, related_id=None, status="completed", description=None, platform_fee_coins=0, net_coins=None, balance_before=None, balance_after=None):
    payload = {
        "profile_id": profile_id,
        "transaction_type": transaction_type,
        "direction": direction,
        "coins": _safe_int(coins, 0),
        "amount_nad": amount_nad or 0,
        "platform_fee_coins": _safe_int(platform_fee_coins, 0),
        "net_coins": _safe_int(net_coins if net_coins is not None else coins, 0),
        "balance_before": _safe_int(balance_before, 0),
        "balance_after": _safe_int(balance_after, 0),
        "reference_number": reference_number,
        "related_table": related_table,
        "related_id": related_id,
        "status": status,
        "description": description,
        "created_at": _utcnow_iso(),
    }
    inserted = safe_insert("chain_wallet_transactions", payload)
    return inserted[0] if inserted else payload


def list_wallet_transactions(profile_id):
    return safe_select("chain_wallet_transactions", filters={"profile_id": profile_id}, limit=40)


def generate_topup_reference():
    return f"NAMVIBE-TOPUP-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{random.randint(1000, 9999)}"


def create_topup_request(profile_id, amount_nad, payment_method, proof_url=None, proof_upload_id=None):
    amount_nad = float(amount_nad or 0)
    if amount_nad <= 0:
        return False, "Top-up amount must be greater than zero."
    coins_requested = max(int(amount_nad / COIN_VALUE_NAD), 1)
    payload = {
        "profile_id": profile_id,
        "reference": generate_topup_reference(),
        "method": payment_method,
        "amount_nad": amount_nad,
        "coins_requested": coins_requested,
        "proof_url": proof_url,
        "proof_upload_id": proof_upload_id,
        "status": "pending",
        "created_at": _utcnow_iso(),
        "updated_at": _utcnow_iso(),
    }
    inserted = safe_insert("chain_wallet_topups", payload)
    return True, inserted[0] if inserted else payload


def create_withdrawal_request(profile_id, coins, payment_details):
    coins = _safe_int(coins, 0)
    wallet = get_or_create_wallet(profile_id)
    available = _safe_int(wallet.get("available_balance") or wallet.get("coin_balance"), 0)
    if coins <= 0:
        return False, "Withdrawal coins must be greater than zero."
    if coins > available:
        return False, "Insufficient available balance."

    new_available = available - coins
    new_pending = _safe_int(wallet.get("pending_withdrawal_balance"), 0) + coins
    if new_available < 0:
        return False, "Insufficient available balance."

    safe_update(
        "chain_wallets",
        {
            "available_balance": new_available,
            "coin_balance": new_available,
            "pending_withdrawal_balance": new_pending,
            "pending_withdrawal": new_pending,
            "updated_at": _utcnow_iso(),
        },
        eq={"profile_id": profile_id},
    )
    payload = {
        "profile_id": profile_id,
        "amount_nad": coins * COIN_VALUE_NAD,
        "coins_redeemed": coins,
        "destination_method": payment_details.get("destination_method"),
        "destination_reference": payment_details.get("destination_reference"),
        "status": "pending",
        "created_at": _utcnow_iso(),
        "updated_at": _utcnow_iso(),
    }
    inserted = safe_insert("chain_wallet_withdrawals", payload)
    withdrawal = inserted[0] if inserted else payload
    record_wallet_transaction(
        profile_id,
        "withdrawal_request",
        "out",
        -coins,
        coins * COIN_VALUE_NAD,
        related_table="chain_wallet_withdrawals",
        related_id=withdrawal.get("id"),
        status="pending",
        description="Withdrawal request submitted and coins moved to pending balance.",
        balance_before=available,
        balance_after=new_available,
    )
    return True, withdrawal


def set_wallet_pin(profile_id, pin):
    cleaned = str(pin or "").strip()
    if len(cleaned) < 4:
        return False, "PIN must be at least 4 digits."
    wallet = get_or_create_wallet(profile_id)
    safe_update(
        "chain_wallets",
        {
            "wallet_pin_hash": generate_password_hash(cleaned),
            "wallet_pin_enabled": True,
            "updated_at": _utcnow_iso(),
        },
        eq={"profile_id": profile_id},
    )
    return True, wallet


def verify_wallet_pin(profile_id, pin):
    wallet = get_or_create_wallet(profile_id)
    stored = wallet.get("wallet_pin_hash")
    if not stored:
        return False
    return check_password_hash(stored, str(pin or "").strip())


def create_pin_reset_request(profile_id, id_copy_url, reason, id_copy_upload_id=None):
    payload = {
        "profile_id": profile_id,
        "status": "pending",
        "verification_status": "pending",
        "id_copy_url": id_copy_url,
        "id_copy_upload_id": id_copy_upload_id,
        "reason": reason,
        "created_at": _utcnow_iso(),
        "updated_at": _utcnow_iso(),
    }
    inserted = safe_insert("chain_wallet_pin_resets", payload)
    return True, inserted[0] if inserted else payload


def approve_topup(admin_id, topup_id):
    rows = safe_select("chain_wallet_topups", filters={"id": topup_id}, limit=1, order_by=None)
    if not rows:
        return False, "Top-up request not found."
    topup = rows[0]
    if topup.get("status") == "approved":
        return True, topup

    wallet = get_or_create_wallet(topup["profile_id"])
    current_available = _safe_int(wallet.get("available_balance") or wallet.get("coin_balance"), 0)
    coins = _safe_int(topup.get("coins_requested"), 0)
    new_balance = current_available + coins
    safe_update(
        "chain_wallets",
        {
            "available_balance": new_balance,
            "coin_balance": new_balance,
            "updated_at": _utcnow_iso(),
        },
        eq={"profile_id": topup["profile_id"]},
    )
    safe_update("chain_wallet_topups", {"status": "approved", "updated_at": _utcnow_iso()}, eq={"id": topup_id})
    record_wallet_transaction(
        topup["profile_id"],
        "topup_approved",
        "in",
        coins,
        topup.get("amount_nad") or 0,
        reference_number=topup.get("reference"),
        related_table="chain_wallet_topups",
        related_id=topup_id,
        description="Admin approved manual top-up request.",
        balance_before=current_available,
        balance_after=new_balance,
    )
    _record_platform_ledger("topup_approved", "chain_wallet_topups", topup_id, topup["profile_id"], gross_coins=coins, net_coins=coins, amount_nad=topup.get("amount_nad") or 0, description="Manual wallet top-up approved.")
    log_admin_action(admin_id, "approve_topup", "wallet_topup", topup_id, {"profile_id": topup["profile_id"], "coins": coins})
    return True, topup


def approve_withdrawal(admin_id, withdrawal_id):
    rows = safe_select("chain_wallet_withdrawals", filters={"id": withdrawal_id}, limit=1, order_by=None)
    if not rows:
        return False, "Withdrawal request not found."
    withdrawal = rows[0]
    if withdrawal.get("status") == "approved":
        return True, withdrawal

    wallet = get_or_create_wallet(withdrawal["profile_id"])
    pending_before = _safe_int(wallet.get("pending_withdrawal_balance"), 0)
    pending = max(pending_before - _safe_int(withdrawal.get("coins_redeemed"), 0), 0)
    safe_update(
        "chain_wallets",
        {
            "pending_withdrawal_balance": pending,
            "pending_withdrawal": pending,
            "updated_at": _utcnow_iso(),
        },
        eq={"profile_id": withdrawal["profile_id"]},
    )
    safe_update("chain_wallet_withdrawals", {"status": "approved", "updated_at": _utcnow_iso()}, eq={"id": withdrawal_id})
    record_wallet_transaction(
        withdrawal["profile_id"],
        "withdrawal_approved",
        "out",
        0,
        withdrawal.get("amount_nad") or 0,
        related_table="chain_wallet_withdrawals",
        related_id=withdrawal_id,
        description="Admin approved withdrawal execution.",
        balance_before=pending_before,
        balance_after=pending,
    )
    _record_platform_ledger("withdrawal_approved", "chain_wallet_withdrawals", withdrawal_id, withdrawal["profile_id"], amount_nad=withdrawal.get("amount_nad") or 0, description="Withdrawal approved for execution.")
    log_admin_action(admin_id, "approve_withdrawal", "wallet_withdrawal", withdrawal_id, {"profile_id": withdrawal["profile_id"], "coins": withdrawal.get("coins_redeemed")})
    return True, withdrawal


def reject_topup(admin_id, topup_id, reason):
    rows = safe_select("chain_wallet_topups", filters={"id": topup_id}, limit=1, order_by=None)
    if not rows:
        return False, "Top-up request not found."
    topup = rows[0]
    safe_update(
        "chain_wallet_topups",
        {"status": "rejected", "rejected_by": admin_id, "rejected_at": _utcnow_iso(), "rejection_reason": reason, "updated_at": _utcnow_iso()},
        eq={"id": topup_id},
    )
    log_admin_action(admin_id, "reject_topup", "wallet_topup", topup_id, {"reason": reason, "profile_id": topup.get("profile_id")})
    return True, topup


def reject_withdrawal(admin_id, withdrawal_id, reason):
    rows = safe_select("chain_wallet_withdrawals", filters={"id": withdrawal_id}, limit=1, order_by=None)
    if not rows:
        return False, "Withdrawal request not found."
    withdrawal = rows[0]
    wallet = get_or_create_wallet(withdrawal["profile_id"])
    available_before = _safe_int(wallet.get("available_balance") or wallet.get("coin_balance"), 0)
    pending_before = _safe_int(wallet.get("pending_withdrawal_balance"), 0)
    coins = _safe_int(withdrawal.get("coins_redeemed"), 0)
    available_after = available_before + coins
    pending_after = max(pending_before - coins, 0)
    safe_update(
        "chain_wallets",
        {
            "available_balance": available_after,
            "coin_balance": available_after,
            "pending_withdrawal_balance": pending_after,
            "pending_withdrawal": pending_after,
            "updated_at": _utcnow_iso(),
        },
        eq={"profile_id": withdrawal["profile_id"]},
    )
    safe_update(
        "chain_wallet_withdrawals",
        {"status": "rejected", "rejected_by": admin_id, "rejected_at": _utcnow_iso(), "rejection_reason": reason, "updated_at": _utcnow_iso()},
        eq={"id": withdrawal_id},
    )
    record_wallet_transaction(
        withdrawal["profile_id"],
        "withdrawal_rejected",
        "in",
        coins,
        withdrawal.get("amount_nad") or 0,
        related_table="chain_wallet_withdrawals",
        related_id=withdrawal_id,
        status="rejected",
        description="Withdrawal rejected and locked coins returned to available balance.",
        balance_before=available_before,
        balance_after=available_after,
    )
    _record_platform_ledger("withdrawal_rejected", "chain_wallet_withdrawals", withdrawal_id, withdrawal["profile_id"], gross_coins=coins, net_coins=coins, amount_nad=withdrawal.get("amount_nad") or 0, description="Rejected withdrawal returned coins to wallet.")
    log_admin_action(admin_id, "reject_withdrawal", "wallet_withdrawal", withdrawal_id, {"reason": reason, "profile_id": withdrawal.get("profile_id")})
    return True, withdrawal


def execute_withdrawal(admin_id, withdrawal_id, payout_reference):
    rows = safe_select("chain_wallet_withdrawals", filters={"id": withdrawal_id}, limit=1, order_by=None)
    if not rows:
        return False, "Withdrawal request not found."
    withdrawal = rows[0]
    wallet = get_or_create_wallet(withdrawal["profile_id"])
    pending_before = _safe_int(wallet.get("pending_withdrawal_balance"), 0)
    coins = _safe_int(withdrawal.get("coins_redeemed"), 0)
    pending_after = max(pending_before - coins, 0)
    safe_update(
        "chain_wallets",
        {"pending_withdrawal_balance": pending_after, "pending_withdrawal": pending_after, "updated_at": _utcnow_iso()},
        eq={"profile_id": withdrawal["profile_id"]},
    )
    safe_update(
        "chain_wallet_withdrawals",
        {
            "status": "executed",
            "executed_by": admin_id,
            "executed_at": _utcnow_iso(),
            "payout_reference": payout_reference,
            "updated_at": _utcnow_iso(),
        },
        eq={"id": withdrawal_id},
    )
    record_wallet_transaction(
        withdrawal["profile_id"],
        "withdrawal_executed",
        "out",
        0,
        withdrawal.get("amount_nad") or 0,
        reference_number=payout_reference,
        related_table="chain_wallet_withdrawals",
        related_id=withdrawal_id,
        status="completed",
        description="Withdrawal payout executed by admin.",
        balance_before=pending_before,
        balance_after=pending_after,
    )
    _record_platform_ledger("withdrawal_executed", "chain_wallet_withdrawals", withdrawal_id, withdrawal["profile_id"], amount_nad=withdrawal.get("amount_nad") or 0, description="Withdrawal payout executed.")
    log_admin_action(admin_id, "execute_withdrawal", "wallet_withdrawal", withdrawal_id, {"payout_reference": payout_reference, "profile_id": withdrawal.get("profile_id")})
    return True, withdrawal
