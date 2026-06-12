import os
import json
from datetime import datetime, timezone
from uuid import uuid4

from services.neon_service import fast_query, write_query, get_pool_status
from services.logging_service import log_info, log_warning, log_error, log_wallet_event
from services.request_cache import cache_get, cache_set


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success"))


def _utcnow():
    return datetime.now(timezone.utc)


def _wallet_dict(row):
    return {
        "id": str(row["id"]),
        "profile_id": str(row["profile_id"]),
        "balance_cents": int(row["balance_cents"]),
        "pending_balance_cents": int(row["pending_balance_cents"]),
        "lifetime_earned_cents": int(row["lifetime_earned_cents"]),
        "lifetime_spent_cents": int(row["lifetime_spent_cents"]),
        "currency": row.get("currency", "NAD"),
        "status": row.get("status", "active"),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def get_or_create_wallet(profile_id):
    if not profile_id:
        return None
    if not _db_available():
        return _fake_wallet(profile_id)
    try:
        existing = fast_query(
            "SELECT * FROM chain_wallets WHERE profile_id = %s LIMIT 1",
            (profile_id,), default=[]
        )
    except Exception as e:
        log_warning("wallet_lookup_failed", profile_id=profile_id, error=str(e))
        return _fake_wallet(profile_id)
    if existing:
        return _wallet_dict(existing[0])
    try:
        rows = write_query(
            """
            INSERT INTO chain_wallets (id, profile_id)
            VALUES (%s, %s)
            ON CONFLICT (profile_id) DO NOTHING
            RETURNING *
            """,
            (str(uuid4()), profile_id), timeout_ms=3000
        )
        if rows:
            return _wallet_dict(rows[0])
    except Exception as e:
        log_warning("wallet_create_failed", profile_id=profile_id, error=str(e))
    existing = fast_query(
        "SELECT * FROM chain_wallets WHERE profile_id = %s LIMIT 1",
        (profile_id,), default=[]
    )
    if existing:
        return _wallet_dict(existing[0])
    return None


def _fake_wallet(profile_id):
    return {
        "id": str(uuid4()),
        "profile_id": profile_id,
        "balance_cents": 0,
        "pending_balance_cents": 0,
        "lifetime_earned_cents": 0,
        "lifetime_spent_cents": 0,
        "currency": "NAD",
        "status": "active",
        "created_at": _utcnow().isoformat(),
        "updated_at": _utcnow().isoformat(),
    }


def get_wallet(profile_id):
    if not profile_id:
        return None
    if not _db_available():
        return _fake_wallet(profile_id)
    cached = cache_get(f"wallet:{profile_id}")
    if cached is not None:
        return cached
    rows = fast_query(
        "SELECT * FROM chain_wallets WHERE profile_id = %s LIMIT 1",
        (profile_id,), default=[]
    )
    result = _wallet_dict(rows[0]) if rows else None
    return cache_set(f"wallet:{profile_id}", result)


def lock_wallet(profile_id):
    if not _db_available():
        return True
    try:
        write_query(
            "UPDATE chain_wallets SET status = 'locked', updated_at = now() WHERE profile_id = %s",
            (profile_id,)
        )
        return True
    except Exception as e:
        log_warning("wallet_lock_failed", profile_id=profile_id, error=str(e))
        return False


def unlock_wallet(profile_id):
    if not _db_available():
        return True
    try:
        write_query(
            "UPDATE chain_wallets SET status = 'active', updated_at = now() WHERE profile_id = %s",
            (profile_id,)
        )
        return True
    except Exception as e:
        log_warning("wallet_unlock_failed", profile_id=profile_id, error=str(e))
        return False


def credit_wallet(profile_id, amount_cents, description="", transaction_type="credit", reference_type=None, reference_id=None, counterparty_profile_id=None, metadata=None):
    if amount_cents <= 0:
        return {"ok": False, "error": "amount_must_be_positive"}
    wallet = get_or_create_wallet(profile_id)
    if not wallet:
        return {"ok": False, "error": "wallet_not_found"}
    if wallet.get("status") == "locked":
        return {"ok": False, "error": "wallet_locked"}
    tx_id = str(uuid4())
    if not _db_available():
        return {"ok": True, "balance_cents": amount_cents, "pending_balance_cents": 0, "transaction_id": tx_id}
    try:
        direction = "in"
        if not metadata:
            metadata = {}
        metadata["description"] = description
        write_query(
            """UPDATE chain_wallets SET
                balance_cents = balance_cents + %s,
                lifetime_earned_cents = lifetime_earned_cents + %s,
                updated_at = now()
               WHERE profile_id = %s""",
            (amount_cents, amount_cents, profile_id)
        )
        create_wallet_transaction(
            wallet_id=wallet["id"],
            profile_id=profile_id,
            counterparty_profile_id=counterparty_profile_id,
            transaction_type=transaction_type,
            direction=direction,
            amount_cents=amount_cents,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
            metadata=metadata,
            tx_id=tx_id,
        )
        updated = get_wallet(profile_id)
        log_wallet_event("wallet_credited", profile_id=profile_id, amount_cents=amount_cents, transaction_type=transaction_type)
        return {"ok": True, "balance_cents": updated["balance_cents"] if updated else wallet["balance_cents"] + amount_cents, "transaction_id": tx_id}
    except Exception as e:
        log_error("wallet_credit_failed", profile_id=profile_id, amount_cents=amount_cents, error=str(e))
        return {"ok": False, "error": f"credit_failed: {e}"}


def debit_wallet(profile_id, amount_cents, description="", transaction_type="debit", reference_type=None, reference_id=None, counterparty_profile_id=None, metadata=None):
    if amount_cents <= 0:
        return {"ok": False, "error": "amount_must_be_positive"}
    wallet = get_or_create_wallet(profile_id)
    if not wallet:
        return {"ok": False, "error": "wallet_not_found"}
    if wallet.get("status") == "locked":
        return {"ok": False, "error": "wallet_locked"}
    if wallet["balance_cents"] < amount_cents:
        return {"ok": False, "error": "insufficient_balance"}
    tx_id = str(uuid4())
    if not _db_available():
        return {"ok": True, "balance_cents": 0, "pending_balance_cents": 0, "transaction_id": tx_id}
    try:
        direction = "out"
        if not metadata:
            metadata = {}
        metadata["description"] = description
        write_query(
            """UPDATE chain_wallets SET
                balance_cents = balance_cents - %s,
                lifetime_spent_cents = lifetime_spent_cents + %s,
                updated_at = now()
               WHERE profile_id = %s AND balance_cents >= %s""",
            (amount_cents, amount_cents, profile_id, amount_cents)
        )
        create_wallet_transaction(
            wallet_id=wallet["id"],
            profile_id=profile_id,
            counterparty_profile_id=counterparty_profile_id,
            transaction_type=transaction_type,
            direction=direction,
            amount_cents=amount_cents,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description,
            metadata=metadata,
            tx_id=tx_id,
        )
        updated = get_wallet(profile_id)
        log_wallet_event("wallet_debited", profile_id=profile_id, amount_cents=amount_cents, transaction_type=transaction_type)
        return {"ok": True, "balance_cents": updated["balance_cents"] if updated else wallet["balance_cents"] - amount_cents, "transaction_id": tx_id}
    except Exception as e:
        log_error("wallet_debit_failed", profile_id=profile_id, amount_cents=amount_cents, error=str(e))
        return {"ok": False, "error": f"debit_failed: {e}"}


def transfer_between_wallets(from_profile_id, to_profile_id, amount_cents, description="", reference_type=None, reference_id=None):
    if from_profile_id == to_profile_id:
        return {"ok": False, "error": "self_transfer_not_allowed"}
    if amount_cents <= 0:
        return {"ok": False, "error": "amount_must_be_positive"}
    debit = debit_wallet(from_profile_id, amount_cents, description=f"Transfer: {description}", transaction_type="transfer_out", reference_type=reference_type, reference_id=reference_id, counterparty_profile_id=to_profile_id)
    if not debit.get("ok"):
        return debit
    credit = credit_wallet(to_profile_id, amount_cents, description=f"Transfer: {description}", transaction_type="transfer_in", reference_type=reference_type, reference_id=reference_id, counterparty_profile_id=from_profile_id)
    if not credit.get("ok"):
        credit_wallet(from_profile_id, amount_cents, description=f"Reversal: {description}", transaction_type="reversal", reference_type=reference_type, reference_id=reference_id)
        return {"ok": False, "error": "transfer_reversed"}
    return {"ok": True, "transaction_id": debit.get("transaction_id")}


def create_wallet_transaction(wallet_id, profile_id, amount_cents, transaction_type="unknown", direction="in", counterparty_profile_id=None, currency="NAD", status="completed", reference_type=None, reference_id=None, description="", metadata=None, tx_id=None):
    if not tx_id:
        tx_id = str(uuid4())
    if not metadata:
        metadata = {}
    if not _db_available():
        return tx_id
    try:
        write_query(
            """INSERT INTO chain_wallet_transactions
               (id, wallet_id, profile_id, counterparty_profile_id, transaction_type, direction, amount_cents, currency, status, reference_type, reference_id, description, metadata)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (tx_id, wallet_id, profile_id, counterparty_profile_id, transaction_type, direction, amount_cents, currency, status, reference_type, reference_id, description, json.dumps(metadata))
        )
        return tx_id
    except Exception as e:
        log_error("wallet_tx_create_failed", error=str(e), profile_id=profile_id)
        return tx_id


def get_wallet_transactions(profile_id, limit=50, offset=0, transaction_type=None):
    if not _db_available():
        return []
    cache_key_str = f"wallet_tx:{profile_id}:{limit}:{offset}:{transaction_type or ''}"
    cached = cache_get(cache_key_str)
    if cached is not None:
        return cached
    params = [profile_id]
    where = "profile_id = %s"
    if transaction_type:
        where += " AND transaction_type = %s"
        params.append(transaction_type)
    rows = fast_query(
        f"SELECT * FROM chain_wallet_transactions WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
        tuple(params + [limit, offset]), default=[]
    )
    result = []
    for r in rows:
        row = dict(r)
        row["id"] = str(row["id"])
        row["wallet_id"] = str(row["wallet_id"])
        row["profile_id"] = str(row["profile_id"])
        if row.get("counterparty_profile_id"):
            row["counterparty_profile_id"] = str(row["counterparty_profile_id"])
        if row.get("reference_id"):
            row["reference_id"] = str(row["reference_id"])
        row["amount_cents"] = int(row["amount_cents"])
        if row.get("created_at"):
            row["created_at"] = row["created_at"].isoformat()
        result.append(row)
    cache_set(cache_key_str, result)
    return result


def get_wallet_summary(profile_id):
    wallet = get_wallet(profile_id)
    if not wallet:
        return None
    if not _db_available():
        return {"wallet": wallet, "recent_transactions": [], "total_transactions": 0}
    rows = fast_query(
        "SELECT COUNT(*) AS cnt FROM chain_wallet_transactions WHERE profile_id = %s",
        (profile_id,), default=[{"cnt": 0}]
    )
    total_tx = int(rows[0]["cnt"]) if rows else 0
    recent = get_wallet_transactions(profile_id, limit=10)
    return {
        "wallet": wallet,
        "recent_transactions": recent,
        "total_transactions": total_tx,
    }


# ---------- backward-compat wrappers for existing importers ----------

def ensure_wallet(profile_id):
    w = get_or_create_wallet(profile_id)
    if w:
        return {"profile_id": w["profile_id"], "coin_balance": w["balance_cents"], "gift_earnings": 0}
    return {"profile_id": profile_id, "coin_balance": 0, "gift_earnings": 0}


def get_wallet_home(profile_id):
    return get_wallet_summary(profile_id)


def top_up_wallet(profile_id, amount_cents):
    return credit_wallet(profile_id, amount_cents, description="Top-up", transaction_type="top_up")


def get_wallet_data(profile_id):
    w = get_wallet(profile_id)
    if not w:
        w = get_or_create_wallet(profile_id)
    return w
