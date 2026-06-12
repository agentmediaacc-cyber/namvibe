import uuid
import os
from decimal import Decimal

from services.neon_service import fast_query, fetch_one_with_connection, get_connection, release_connection, transaction_query, safe_row_get
from services.notification_engine import create_notification
from services.logging_service import log_wallet_event
from services.request_cache import build_request_key, request_memoize


def _wallet_tx_id(kind, *parts, provided=None):
    return provided or f"{kind}-{'-'.join(str(part) for part in parts)}"


def _minute_bucket():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%d%H%M")


def _coerce_amount(value):
    amount = Decimal(str(value))
    if amount <= 0:
        raise ValueError("Amount must be positive")
    return amount


def _ensure_wallet_row(cursor, profile_id):
    cursor.execute(
        """
        INSERT INTO chain_wallets (profile_id, coin_balance, created_at, updated_at)
        VALUES (%s, 0, now(), now())
        ON CONFLICT (profile_id) DO NOTHING
        """,
        (profile_id,),
    )


def _lock_wallet_row(cursor, profile_id):
    _ensure_wallet_row(cursor, profile_id)
    cursor.execute(
        "SELECT profile_id, coin_balance FROM chain_wallets WHERE profile_id = %s FOR UPDATE",
        (profile_id,),
    )
    return cursor.fetchone()


def _transaction_exists(cursor, idempotency_key):
    if not idempotency_key:
        return False
    cursor.execute(
        "SELECT 1 FROM chain_wallet_transactions WHERE idempotency_key = %s LIMIT 1",
        (idempotency_key,),
    )
    return bool(cursor.fetchone())


def _completed_gift_by_idempotency(cursor, idempotency_key):
    if not idempotency_key:
        return None
    cursor.execute(
        """
        SELECT id, sender_profile_id, receiver_profile_id, coin_value
        FROM chain_gifts
        WHERE idempotency_key = %s
        LIMIT 1
        """,
        (idempotency_key,),
    )
    return cursor.fetchone()


def _insert_transaction(cursor, profile_id, amount_delta, tx_type, description, source_profile_id=None, entity_type=None, entity_id=None, idempotency_key=None, status="completed", balance_after=None):
    tx_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO chain_wallet_transactions (
            id, profile_id, tx_type, amount, source_profile_id, entity_type, entity_id,
            description, status, idempotency_key, balance_after, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
        RETURNING id
        """,
        (
            tx_id,
            profile_id,
            tx_type,
            amount_delta,
            source_profile_id,
            entity_type,
            entity_id,
            description,
            status,
            idempotency_key,
            balance_after,
        ),
    )
    row = cursor.fetchone()
    return safe_row_get(row, "id", safe_row_get(row, 0, tx_id))


def _apply_wallet_delta(cursor, profile_id, amount_delta):
    _lock_wallet_row(cursor, profile_id)
    if amount_delta < 0:
        cursor.execute(
            """
            UPDATE chain_wallets
            SET coin_balance = coin_balance + %s, updated_at = now()
            WHERE profile_id = %s AND coin_balance + %s >= 0
            RETURNING coin_balance
            """,
            (amount_delta, profile_id, amount_delta),
        )
    else:
        cursor.execute(
            """
            UPDATE chain_wallets
            SET coin_balance = coin_balance + %s, updated_at = now()
            WHERE profile_id = %s
            RETURNING coin_balance
            """,
            (amount_delta, profile_id),
        )
    row = cursor.fetchone()
    if not row:
        raise ValueError("insufficient_balance")
    return safe_row_get(row, "coin_balance", safe_row_get(row, 0, 0))


def _atomic_wallet_transaction(profile_id, amount_delta, tx_type, description, source_profile_id=None, entity_type=None, entity_id=None, idempotency_key=None, status="completed", cursor=None):
    if cursor is None:
        raise ValueError("cursor is required for atomic wallet updates")
    if _transaction_exists(cursor, idempotency_key):
        return {"status": "duplicate", "idempotency_key": idempotency_key}
    balance = _apply_wallet_delta(cursor, profile_id, Decimal(str(amount_delta)))
    tx_id = _insert_transaction(
        cursor,
        profile_id,
        Decimal(str(amount_delta)),
        tx_type,
        description,
        source_profile_id=source_profile_id,
        entity_type=entity_type,
        entity_id=entity_id,
        idempotency_key=idempotency_key,
        status=status,
        balance_after=balance,
    )
    return {"status": "ok", "transaction_id": tx_id, "coin_balance": balance}


def safe_wallet_transaction(
    idempotency_key,
    sender_profile_id,
    receiver_profile_id,
    amount,
    tx_type,
    gift_type=None,
    entity_type=None,
    entity_id=None,
):
    amount = _coerce_amount(amount)

    def _callback(cursor):
        existing_gift = _completed_gift_by_idempotency(cursor, idempotency_key)
        if existing_gift:
            return {"status": "duplicate", "gift_id": existing_gift["id"] if isinstance(existing_gift, dict) else existing_gift[0], "idempotent": True}
        _lock_wallet_row(cursor, sender_profile_id)
        _lock_wallet_row(cursor, receiver_profile_id)
        debit = _atomic_wallet_transaction(
            sender_profile_id,
            -amount,
            f"{tx_type}_sent",
            f"Sent {gift_type or tx_type}",
            source_profile_id=receiver_profile_id,
            entity_type=entity_type,
            entity_id=entity_id,
            idempotency_key=f"{idempotency_key}:debit",
            cursor=cursor,
        )
        credit = _atomic_wallet_transaction(
            receiver_profile_id,
            amount,
            f"{tx_type}_received",
            f"Received {gift_type or tx_type}",
            source_profile_id=sender_profile_id,
            entity_type=entity_type,
            entity_id=entity_id,
            idempotency_key=f"{idempotency_key}:credit",
            cursor=cursor,
        )
        gift_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO chain_gifts (
                id, sender_profile_id, receiver_profile_id, gift_type, coin_value, entity_type, entity_id, idempotency_key, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING id
            """,
            (gift_id, sender_profile_id, receiver_profile_id, gift_type or tx_type, amount, entity_type, entity_id, idempotency_key),
        )
        inserted = cursor.fetchone()
        return {
            "status": "ok",
            "gift_id": inserted["id"] if inserted else gift_id,
            "idempotent": False,
            "sender_balance": debit["coin_balance"],
            "receiver_balance": credit["coin_balance"],
        }

    return transaction_query(_callback, timeout_ms=1500)


def ensure_wallet(profile_id):
    if os.getenv("FLASK_TESTING") == "1" or (os.getenv("CHAIN_FAST_LOCAL") == "1" and os.getenv("FLASK_ENV", "development") != "production"):
        return {"profile_id": profile_id, "coin_balance": 0, "gift_earnings": 0}
    connection = None
    try:
        connection = get_connection(statement_timeout_ms=500, fast_fail=True)
        with connection:
            with connection.cursor() as cursor:
                _ensure_wallet_row(cursor, profile_id)
        row = fetch_one_with_connection(connection, "SELECT * FROM chain_wallets WHERE profile_id = %s LIMIT 1", (profile_id,), timeout_ms=300)
        return row
    except Exception as error:
        print(f"[wallet_engine] Failed to ensure wallet: {error}")
        return {"profile_id": profile_id, "coin_balance": 0, "gift_earnings": 0}
    finally:
        release_connection(connection)


def get_wallet_summary(profile_id):
    return request_memoize(build_request_key("wallet_summary", profile_id), lambda: ensure_wallet(profile_id))


def list_transactions(profile_id, limit=30):
    sql = """
        SELECT t.*, p.username as source_username
        FROM chain_wallet_transactions t
        LEFT JOIN chain_profiles p ON t.source_profile_id = p.id
        WHERE t.profile_id = %s AND t.deleted_at IS NULL
        ORDER BY t.created_at DESC
        LIMIT %s
    """
    return fast_query(sql, (profile_id, limit), timeout_ms=500, default=[])


def send_gift(sender_profile_id, receiver_profile_id, gift_type, coin_value, entity_type=None, entity_id=None, idempotency_key=None):
    if sender_profile_id == receiver_profile_id:
        return False, "You cannot gift yourself"
    try:
        coin_value = _coerce_amount(coin_value)
    except Exception:
        return False, "Invalid gift value"

    idempotency_key = _wallet_tx_id(
        "gift",
        sender_profile_id,
        receiver_profile_id,
        entity_type or "entity",
        entity_id or "none",
        gift_type,
        int(coin_value),
        _minute_bucket(),
        provided=idempotency_key,
    )

    try:
        result = safe_wallet_transaction(
            idempotency_key=idempotency_key,
            sender_profile_id=sender_profile_id,
            receiver_profile_id=receiver_profile_id,
            amount=coin_value,
            tx_type="gift",
            gift_type=gift_type,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        create_notification(
            recipient_profile_id=receiver_profile_id,
            actor_profile_id=sender_profile_id,
            event_type="gift_received",
            title="New Gift Received!",
            body=f"received a {gift_type} gift ({int(coin_value)} coins).",
            action_url="/wallet/",
        )
        log_wallet_event("gift_success", sender_profile_id=sender_profile_id, receiver_profile_id=receiver_profile_id, amount=int(coin_value), idempotent=bool(result.get("idempotent")))
        return True, result
    except Exception as error:
        if "insufficient_balance" in str(error):
            return False, "Insufficient balance"
        print(f"[wallet_engine] Gift failed: {error}")
        return False, "Transaction failed"


def request_payout(profile_id, amount, idempotency_key=None):
    try:
        amount = _coerce_amount(amount)
    except Exception:
        return False, "invalid_amount"

    idempotency_key = _wallet_tx_id("payout", profile_id, int(amount), provided=idempotency_key)
    try:
        def _callback(cursor):
                if _transaction_exists(cursor, idempotency_key):
                    return {"status": "duplicate"}
                _atomic_wallet_transaction(
                    profile_id,
                    -amount,
                    "payout_pending",
                    f"Pending payout request for {amount} coins",
                    idempotency_key=idempotency_key,
                    status="pending",
                    cursor=cursor,
                )
                cursor.execute(
                    """
                    INSERT INTO chain_wallet_payouts (id, profile_id, amount_nad, status, created_at, idempotency_key)
                    VALUES (%s, %s, %s, 'pending', now(), %s)
                    ON CONFLICT (idempotency_key) DO NOTHING
                    """,
                    (str(uuid.uuid4()), profile_id, amount, idempotency_key),
                )
                return {"status": "pending"}
        transaction_query(_callback, timeout_ms=1200)
        return True, "pending"
    except Exception as error:
        if "insufficient_balance" in str(error):
            return False, "insufficient_balance"
        print(f"[wallet_engine] request_payout failed: {error}")
        return False, "setup_required"


def add_creator_earning(profile_id, amount, source_profile_id=None, entity_type=None, entity_id=None, idempotency_key=None):
    try:
        amount = _coerce_amount(amount)
    except Exception:
        return False
    try:
        def _callback(cursor):
                _atomic_wallet_transaction(
                    profile_id,
                    amount,
                    "earning",
                    "Creator earning",
                    source_profile_id=source_profile_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    idempotency_key=idempotency_key or _wallet_tx_id("earning", profile_id, entity_type or "entity", entity_id or "none", int(amount)),
                    cursor=cursor,
                )
                return True
        transaction_query(_callback, timeout_ms=900)
        return True
    except Exception as error:
        print(f"[wallet_engine] Failed to add earning: {error}")
        return False
