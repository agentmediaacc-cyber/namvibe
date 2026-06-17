from datetime import datetime, timezone
import uuid

def initiate_mtc_maris_payment(profile_id, amount_nad):
    """
    Simulates initiating an MTC Maris payment (USSD/SMS push).
    Returns a reference and external URL.
    """
    ref = f"MARIS-{uuid.uuid4().hex[:8].upper()}"
    return {
        "status": "pending",
        "reference": ref,
        "instructions": f"Dial *140*666# and enter ref {ref} to complete your {amount_nad} NAD payment."
    }

def verify_bank_transfer(profile_id, amount_nad, reference_id):
    """
    Simulates manual/semi-auto verification of FNB/Bank transfers.
    In a real app, this would query a statement API or wait for admin approval.
    """
    # Placeholder: record a pending verification
    return {"status": "awaiting_proof", "ref": reference_id}

def process_webhook(provider, payload):
    """
    Main entry point for payment provider webhooks (Paystack, Flutterwave, etc.)
    """
    if not payload:
        return {"ok": False, "error": "empty_payload"}
    txn_id = payload.get("transaction_id") or payload.get("id") or payload.get("reference")
    status = payload.get("status", "").lower()
    amount_cents = int(float(payload.get("amount", 0)) * 100)
    profile_id = payload.get("profile_id") or payload.get("user_id")

    if status not in ("success", "completed", "confirmed"):
        return {"ok": True, "status": status, "message": "no_action_needed"}

    if not profile_id or not txn_id or amount_cents <= 0:
        return {"ok": False, "error": "missing_fields"}

    from services.wallet_service import credit_wallet
    result = credit_wallet(profile_id, amount_cents, description=f"{provider} deposit: {txn_id}", transaction_type="deposit")
    return {"ok": result.get("ok", False), "transaction_id": txn_id, "wallet_result": result}

def log_payout_request(profile_id, amount_nad, method):
    """Logs a creator payout request for admin review"""
    from services.supabase_safe import safe_insert
    payload = {
        "profile_id": profile_id,
        "amount_nad": amount_nad,
        "coins_deducted": int(amount_nad * 10), # 1 NAD = 10 coins
        "payout_method": method,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    return safe_insert("chain_wallet_payouts", payload)
