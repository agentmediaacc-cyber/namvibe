import os
import json
from datetime import datetime, timezone
from uuid import uuid4

from services.neon_service import fast_query, write_query, get_pool_status
from services.logging_service import log_info, log_warning, log_error, log_wallet_event, log_security
from services.wallet_service import credit_wallet, debit_wallet, get_or_create_wallet
from services.socketio_service import emit_to_profile
from services.notification_engine import create_notification


PLATFORM_FEE_PERCENT = 10


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _utcnow():
    return datetime.now(timezone.utc)


def calculate_platform_fee(amount_cents):
    return int(amount_cents * PLATFORM_FEE_PERCENT / 100)


def _log_risk(profile_id, event_type, severity="medium", metadata=None):
    if not _db_available():
        return
    try:
        write_query(
            "INSERT INTO chain_wallet_risk_events (id, profile_id, event_type, severity, metadata) VALUES (%s, %s, %s, %s, %s)",
            (str(uuid4()), profile_id, event_type, severity, json.dumps(metadata or {}))
        )
    except Exception:
        pass


def _record_creator_earning(creator_profile_id, source_profile_id, earning_type, gross_amount_cents, platform_fee_cents, net_amount_cents, reference_type=None, reference_id=None):
    if not _db_available():
        return {"ok": True}
    try:
        write_query(
            """INSERT INTO chain_creator_earnings
               (id, creator_profile_id, source_profile_id, earning_type, gross_amount_cents, platform_fee_cents, net_amount_cents, reference_type, reference_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (str(uuid4()), creator_profile_id, source_profile_id, earning_type, gross_amount_cents, platform_fee_cents, net_amount_cents, reference_type, reference_id)
        )
        return {"ok": True}
    except Exception as e:
        log_error("earning_record_failed", creator_profile_id=creator_profile_id, error=str(e))
        return {"ok": False, "error": str(e)}


def send_tip(sender_profile_id, receiver_profile_id, amount_cents, message=None):
    if sender_profile_id == receiver_profile_id:
        log_security("self_tip_blocked", profile_id=sender_profile_id)
        return {"ok": False, "error": "self_tip_not_allowed"}
    if amount_cents <= 0:
        return {"ok": False, "error": "amount_must_be_positive"}
    try:
        from services.safety_rate_limit_service import check_action_rate_limit
        from services.fraud_detection_service import analyze_tip, record_fraud_event, is_high_risk_wallet_action
        from services.moderation_service import add_to_moderation_queue
        rate = check_action_rate_limit(sender_profile_id, "tip")
        if rate.get("blocked"):
            return {"ok": False, "error": "rate_limited"}
        fraud = analyze_tip(sender_profile_id, receiver_profile_id, amount_cents)
        if fraud.get("score", 0) >= 35:
            record_fraud_event(sender_profile_id, "tip_risk_detected", fraud.get("score", 0), fraud.get("severity"), metadata=fraud)
        if is_high_risk_wallet_action(fraud):
            add_to_moderation_queue(sender_profile_id, "wallet_tip", None, "fraud", fraud.get("severity", "high"), "high_risk_tip", {"fraud": fraud})
            return {"ok": False, "error": "high_risk_wallet_action", "fraud": fraud}
    except Exception:
        pass
    if amount_cents > 5000000:
        _log_risk(sender_profile_id, "abnormal_tip_amount", severity="high", metadata={"amount_cents": amount_cents, "receiver": receiver_profile_id})
        return {"ok": False, "error": "amount_exceeds_limit"}
    fee = calculate_platform_fee(amount_cents)
    net = amount_cents - fee
    debit = debit_wallet(sender_profile_id, amount_cents, description=f"Tip to {receiver_profile_id}", transaction_type="tip", counterparty_profile_id=receiver_profile_id)
    if not debit.get("ok"):
        return debit
    credit = credit_wallet(receiver_profile_id, net, description=f"Tip from {sender_profile_id}", transaction_type="tip", counterparty_profile_id=sender_profile_id)
    if not credit.get("ok"):
        credit_wallet(sender_profile_id, amount_cents, description=f"Reversal: tip to {receiver_profile_id}", transaction_type="tip_reversal", counterparty_profile_id=receiver_profile_id)
        return {"ok": False, "error": "tip_failed_reversed"}
    if _db_available():
        tx_id = debit.get("transaction_id")
        try:
            write_query(
                """INSERT INTO chain_tips (id, sender_profile_id, receiver_profile_id, amount_cents, message, transaction_id)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (str(uuid4()), sender_profile_id, receiver_profile_id, amount_cents, message, tx_id)
            )
        except Exception as e:
            log_warning("tip_record_failed", error=str(e))
    _record_creator_earning(receiver_profile_id, sender_profile_id, "tip", amount_cents, fee, net, reference_type="tip", reference_id=debit.get("transaction_id"))
    log_wallet_event("tip_sent", sender=sender_profile_id, receiver=receiver_profile_id, amount_cents=amount_cents)
    emit_to_profile(sender_profile_id, "wallet:balance-updated", {"balance_cents": debit.get("balance_cents", 0)})
    emit_to_profile(receiver_profile_id, "wallet:tip-received", {"from": sender_profile_id, "amount_cents": net, "message": message})
    emit_to_profile(receiver_profile_id, "wallet:balance-updated", {"balance_cents": credit.get("balance_cents", 0)})
    try:
        create_notification(
            recipient_profile_id=receiver_profile_id,
            event_type="tip_received",
            title="Tip Received!",
            body=f"You received a tip of N$ {amount_cents / 100:.2f}",
            actor_profile_id=sender_profile_id,
            entity_type="tip",
            action_url="/wallet/",
        )
    except Exception:
        log_warning("tip_notification_failed", receiver=receiver_profile_id)
    return {"ok": True, "transaction_id": debit.get("transaction_id"), "amount_cents": amount_cents, "fee_cents": fee, "net_cents": net}


def send_gift(sender_profile_id, receiver_profile_id, gift_id, gift_name=None, gift_emoji=None, gift_price_cents=None):
    if sender_profile_id == receiver_profile_id:
        log_security("self_gift_blocked", profile_id=sender_profile_id)
        return {"ok": False, "error": "self_gift_not_allowed"}
    try:
        from services.safety_rate_limit_service import check_action_rate_limit
        from services.fraud_detection_service import analyze_gift, record_fraud_event, is_high_risk_wallet_action
        from services.moderation_service import add_to_moderation_queue
        rate = check_action_rate_limit(sender_profile_id, "gift")
        if rate.get("blocked"):
            return {"ok": False, "error": "rate_limited"}
        fraud = analyze_gift(sender_profile_id, receiver_profile_id, gift_price_cents or 0)
        if fraud.get("score", 0) >= 35:
            record_fraud_event(sender_profile_id, "gift_risk_detected", fraud.get("score", 0), fraud.get("severity"), metadata=fraud)
        if is_high_risk_wallet_action(fraud):
            add_to_moderation_queue(sender_profile_id, "wallet_gift", None, "fraud", fraud.get("severity", "high"), "high_risk_gift", {"fraud": fraud})
            return {"ok": False, "error": "high_risk_wallet_action", "fraud": fraud}
    except Exception:
        pass
    if not _db_available():
        return {"ok": False, "error": "db_unavailable"}
    gift = None
    if gift_id:
        rows = fast_query("SELECT * FROM chain_gifts WHERE id = %s AND active = TRUE LIMIT 1", (gift_id,), default=[])
        gift = rows[0] if rows else None
    if not gift and gift_price_cents and gift_price_cents > 0:
        gift = {"id": gift_id, "name": gift_name or "Custom", "emoji": gift_emoji or "🎁", "price_cents": gift_price_cents}
    if not gift:
        return {"ok": False, "error": "gift_not_found"}
    price = int(gift["price_cents"])
    if price <= 0:
        return {"ok": False, "error": "invalid_gift_price"}
    fee = calculate_platform_fee(price)
    net = price - fee
    gift_name_str = gift["name"] if isinstance(gift, dict) and gift.get("name") else gift.get("gift_type", "Gift")
    gift_emoji_str = gift["emoji"] if isinstance(gift, dict) and gift.get("emoji") else "🎁"
    debit = debit_wallet(sender_profile_id, price, description=f"Gift: {gift_emoji_str} {gift_name_str}", transaction_type="gift", counterparty_profile_id=receiver_profile_id)
    if not debit.get("ok"):
        return debit
    credit = credit_wallet(receiver_profile_id, net, description=f"Gift: {gift_emoji_str} {gift_name_str} from {sender_profile_id}", transaction_type="gift", counterparty_profile_id=sender_profile_id)
    if not credit.get("ok"):
        credit_wallet(sender_profile_id, price, description=f"Reversal: gift to {receiver_profile_id}", transaction_type="gift_reversal", counterparty_profile_id=receiver_profile_id)
        return {"ok": False, "error": "gift_failed_reversed"}
    tx_id = debit.get("transaction_id")
    try:
        write_query(
            """INSERT INTO chain_gifts (id, sender_profile_id, receiver_profile_id, gift_type, coin_value, amount_cents, name, emoji, price_cents, transaction_id, active)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE)""",
            (str(uuid4()), sender_profile_id, receiver_profile_id, gift_name_str, price, price, gift_name_str, gift_emoji_str, price, tx_id)
        )
    except Exception as e:
        log_warning("gift_record_failed", error=str(e))
    _record_creator_earning(receiver_profile_id, sender_profile_id, "gift", price, fee, net, reference_type="gift", reference_id=tx_id)
    log_wallet_event("gift_sent", sender=sender_profile_id, receiver=receiver_profile_id, gift_name=gift_name_str, amount_cents=price)
    emit_to_profile(sender_profile_id, "wallet:balance-updated", {"balance_cents": debit.get("balance_cents", 0)})
    emit_to_profile(receiver_profile_id, "wallet:gift-received", {"from": sender_profile_id, "gift_name": gift_name_str, "gift_emoji": gift_emoji_str, "amount_cents": net})
    emit_to_profile(receiver_profile_id, "wallet:balance-updated", {"balance_cents": credit.get("balance_cents", 0)})
    try:
        create_notification(
            recipient_profile_id=receiver_profile_id,
            event_type="gift_received",
            title="Gift Received!",
            body=f"You received a {gift_emoji_str} {gift_name_str} gift!",
            actor_profile_id=sender_profile_id,
            entity_type="gift",
            action_url="/wallet/",
        )
    except Exception:
        log_warning("gift_notification_failed", receiver=receiver_profile_id)
    return {"ok": True, "transaction_id": tx_id, "amount_cents": price, "fee_cents": fee, "net_cents": net, "gift": {"name": gift_name_str, "emoji": gift_emoji_str}}


def get_available_gifts():
    if not _db_available():
        return []
    rows = fast_query("SELECT * FROM chain_gifts WHERE active = TRUE ORDER BY price_cents ASC", default=[])
    result = []
    seen = set()
    for r in rows:
        gid = str(r["id"])
        if gid in seen:
            continue
        seen.add(gid)
        result.append({
            "id": gid,
            "name": r.get("name") or r.get("gift_type", "Gift"),
            "emoji": r.get("emoji") or "🎁",
            "price_cents": int(r.get("price_cents") or r.get("coin_value", 0)),
            "currency": r.get("currency", "NAD"),
            "active": bool(r["active"]),
        })
    return result


def subscribe_to_creator(subscriber_profile_id, creator_profile_id, tier_name="basic", price_cents=0):
    if subscriber_profile_id == creator_profile_id:
        return {"ok": False, "error": "self_subscription_not_allowed"}
    if price_cents < 0:
        return {"ok": False, "error": "invalid_price"}
    try:
        from services.fraud_detection_service import analyze_subscription, record_fraud_event, is_high_risk_wallet_action
        from services.moderation_service import add_to_moderation_queue
        fraud = analyze_subscription(subscriber_profile_id, creator_profile_id, price_cents)
        if fraud.get("score", 0) >= 35:
            record_fraud_event(subscriber_profile_id, "subscription_risk_detected", fraud.get("score", 0), fraud.get("severity"), metadata=fraud)
        if is_high_risk_wallet_action(fraud):
            add_to_moderation_queue(subscriber_profile_id, "subscription", None, "fraud", fraud.get("severity", "high"), "high_risk_subscription", {"fraud": fraud})
            return {"ok": False, "error": "high_risk_wallet_action", "fraud": fraud}
    except Exception:
        pass
    if price_cents > 5000000:
        return {"ok": False, "error": "amount_exceeds_limit"}
    existing = None
    if _db_available():
        rows = fast_query(
            "SELECT * FROM chain_creator_subscriptions WHERE subscriber_profile_id = %s AND creator_profile_id = %s AND status = 'active' LIMIT 1",
            (subscriber_profile_id, creator_profile_id), default=[]
        )
        existing = rows[0] if rows else None
    if existing:
        return {"ok": False, "error": "already_subscribed"}
    if price_cents > 0:
        fee = calculate_platform_fee(price_cents)
        net = price_cents - fee
        debit = debit_wallet(subscriber_profile_id, price_cents, description=f"Subscription to {creator_profile_id}", transaction_type="subscription", counterparty_profile_id=creator_profile_id)
        if not debit.get("ok"):
            return debit
        credit = credit_wallet(creator_profile_id, net, description=f"Subscription from {subscriber_profile_id}", transaction_type="subscription", counterparty_profile_id=subscriber_profile_id)
        if not credit.get("ok"):
            credit_wallet(subscriber_profile_id, price_cents, description=f"Reversal: subscription to {creator_profile_id}", transaction_type="subscription_reversal")
            return {"ok": False, "error": "subscription_failed_reversed"}
        tx_id = debit.get("transaction_id")
        _record_creator_earning(creator_profile_id, subscriber_profile_id, "subscription", price_cents, fee, net, reference_type="subscription", reference_id=tx_id)
    if _db_available():
        try:
            sub_id = str(uuid4())
            write_query(
                """INSERT INTO chain_creator_subscriptions
                   (id, subscriber_profile_id, creator_profile_id, tier_name, price_cents)
                   VALUES (%s, %s, %s, %s, %s)""",
                (sub_id, subscriber_profile_id, creator_profile_id, tier_name, price_cents)
            )
            log_wallet_event("subscription_created", subscriber=subscriber_profile_id, creator=creator_profile_id, tier=tier_name, price_cents=price_cents)
            emit_to_profile(subscriber_profile_id, "wallet:balance-updated", {"balance_cents": debit.get("balance_cents", 0) if price_cents > 0 else 0})
            emit_to_profile(creator_profile_id, "wallet:subscription-created", {"subscriber": subscriber_profile_id, "tier": tier_name})
            if price_cents > 0:
                try:
                    create_notification(
                        recipient_profile_id=creator_profile_id,
                        event_type="new_subscriber",
                        title="New Subscriber!",
                        body=f"Someone subscribed to your {tier_name} tier",
                        actor_profile_id=subscriber_profile_id,
                        entity_type="subscription",
                        action_url="/wallet/",
                    )
                except Exception:
                    log_warning("subscription_notification_failed", creator=creator_profile_id)
            return {"ok": True, "subscription_id": sub_id}
        except Exception as e:
            log_error("subscription_create_failed", error=str(e))
            return {"ok": False, "error": str(e)}
    return {"ok": True, "subscription_id": str(uuid4())}


def cancel_creator_subscription(subscriber_profile_id, creator_profile_id):
    if not _db_available():
        return {"ok": False, "error": "db_unavailable"}
    try:
        write_query(
            "UPDATE chain_creator_subscriptions SET status = 'cancelled', cancelled_at = now() WHERE subscriber_profile_id = %s AND creator_profile_id = %s AND status = 'active'",
            (subscriber_profile_id, creator_profile_id)
        )
        log_wallet_event("subscription_cancelled", subscriber=subscriber_profile_id, creator=creator_profile_id)
        return {"ok": True}
    except Exception as e:
        log_error("subscription_cancel_failed", error=str(e))
        return {"ok": False, "error": str(e)}


def is_subscribed(subscriber_profile_id, creator_profile_id):
    if not _db_available():
        return False
    rows = fast_query(
        "SELECT id FROM chain_creator_subscriptions WHERE subscriber_profile_id = %s AND creator_profile_id = %s AND status = 'active' LIMIT 1",
        (subscriber_profile_id, creator_profile_id), default=[]
    )
    return len(rows) > 0


def create_paid_content(creator_profile_id, content_type, price_cents, content_id=None):
    if price_cents <= 0:
        return {"ok": False, "error": "price_must_be_positive"}
    if not _db_available():
        return {"ok": False, "error": "db_unavailable"}
    try:
        cid = str(uuid4())
        write_query(
            """INSERT INTO chain_paid_content (id, creator_profile_id, content_type, content_id, price_cents)
               VALUES (%s, %s, %s, %s, %s)""",
            (cid, creator_profile_id, content_type, content_id or cid, price_cents)
        )
        return {"ok": True, "paid_content_id": cid}
    except Exception as e:
        log_error("paid_content_create_failed", error=str(e))
        return {"ok": False, "error": str(e)}


def purchase_paid_content(buyer_profile_id, creator_profile_id, paid_content_id):
    if buyer_profile_id == creator_profile_id:
        return {"ok": False, "error": "self_purchase_not_allowed"}
    if not _db_available():
        return {"ok": False, "error": "db_unavailable"}
    existing_purchase = fast_query(
        "SELECT id FROM chain_content_purchases WHERE buyer_profile_id = %s AND paid_content_id = %s LIMIT 1",
        (buyer_profile_id, paid_content_id), default=[]
    )
    if existing_purchase:
        return {"ok": False, "error": "already_purchased"}
    content = fast_query(
        "SELECT * FROM chain_paid_content WHERE id = %s AND active = TRUE LIMIT 1",
        (paid_content_id,), default=[]
    )
    if not content:
        return {"ok": False, "error": "content_not_found"}
    content = content[0]
    price = int(content["price_cents"])
    fee = calculate_platform_fee(price)
    net = price - fee
    debit = debit_wallet(buyer_profile_id, price, description=f"Purchase: {content.get('content_type', 'content')}", transaction_type="content_purchase", counterparty_profile_id=creator_profile_id)
    if not debit.get("ok"):
        return debit
    credit = credit_wallet(creator_profile_id, net, description=f"Content purchase from {buyer_profile_id}", transaction_type="content_purchase", counterparty_profile_id=buyer_profile_id)
    if not credit.get("ok"):
        credit_wallet(buyer_profile_id, price, description=f"Reversal: content purchase", transaction_type="content_purchase_reversal")
        return {"ok": False, "error": "purchase_failed_reversed"}
    tx_id = debit.get("transaction_id")
    if _db_available():
        try:
            write_query(
                """INSERT INTO chain_content_purchases (id, buyer_profile_id, creator_profile_id, paid_content_id, amount_cents, transaction_id)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (str(uuid4()), buyer_profile_id, creator_profile_id, paid_content_id, price, tx_id)
            )
        except Exception as e:
            log_warning("purchase_record_failed", error=str(e))
    _record_creator_earning(creator_profile_id, buyer_profile_id, "content_purchase", price, fee, net, reference_type="content_purchase", reference_id=tx_id)
    log_wallet_event("content_purchased", buyer=buyer_profile_id, creator=creator_profile_id, content_id=paid_content_id, amount_cents=price)
    emit_to_profile(buyer_profile_id, "wallet:balance-updated", {"balance_cents": debit.get("balance_cents", 0)})
    emit_to_profile(creator_profile_id, "wallet:paid-content-purchased", {"buyer": buyer_profile_id, "content_id": paid_content_id})
    emit_to_profile(creator_profile_id, "wallet:balance-updated", {"balance_cents": credit.get("balance_cents", 0)})
    try:
        create_notification(
            recipient_profile_id=creator_profile_id,
            event_type="content_purchased",
            title="Content Purchased!",
            body=f"Your content was purchased for N$ {price / 100:.2f}",
            actor_profile_id=buyer_profile_id,
            entity_type="content_purchase",
            action_url="/wallet/",
        )
    except Exception:
        log_warning("purchase_notification_failed", creator=creator_profile_id)
    return {"ok": True, "transaction_id": tx_id}


def has_purchased_content(buyer_profile_id, paid_content_id):
    if not _db_available():
        return False
    rows = fast_query(
        "SELECT id FROM chain_content_purchases WHERE buyer_profile_id = %s AND paid_content_id = %s LIMIT 1",
        (buyer_profile_id, paid_content_id), default=[]
    )
    return len(rows) > 0


def get_creator_earnings(creator_profile_id, limit=50, offset=0):
    if not _db_available():
        return []
    rows = fast_query(
        "SELECT * FROM chain_creator_earnings WHERE creator_profile_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
        (creator_profile_id, limit, offset), default=[]
    )
    result = []
    for r in rows:
        result.append({
            "id": str(r["id"]),
            "creator_profile_id": str(r["creator_profile_id"]),
            "source_profile_id": str(r["source_profile_id"]) if r.get("source_profile_id") else None,
            "earning_type": r["earning_type"],
            "gross_amount_cents": int(r["gross_amount_cents"]),
            "platform_fee_cents": int(r["platform_fee_cents"]),
            "net_amount_cents": int(r["net_amount_cents"]),
            "currency": r.get("currency", "NAD"),
            "status": r.get("status", "available"),
            "reference_type": r.get("reference_type"),
            "reference_id": str(r["reference_id"]) if r.get("reference_id") else None,
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
        })
    return result


def get_creator_dashboard(creator_profile_id):
    wallet = get_or_create_wallet(creator_profile_id)
    if not wallet:
        return None
    result = {
        "wallet": wallet,
        "total_earnings_cents": 0,
        "total_fees_cents": 0,
        "total_net_cents": 0,
        "tip_count": 0,
        "gift_count": 0,
        "subscription_count": 0,
        "purchase_count": 0,
        "recent_earnings": [],
        "subscriber_count": 0,
    }
    if not _db_available():
        return result
    earnings_rows = fast_query(
        "SELECT COALESCE(SUM(gross_amount_cents), 0) AS gross, COALESCE(SUM(platform_fee_cents), 0) AS fees, COALESCE(SUM(net_amount_cents), 0) AS net FROM chain_creator_earnings WHERE creator_profile_id = %s",
        (creator_profile_id,), default=[{"gross": 0, "fees": 0, "net": 0}]
    )
    if earnings_rows:
        result["total_earnings_cents"] = int(earnings_rows[0]["gross"])
        result["total_fees_cents"] = int(earnings_rows[0]["fees"])
        result["total_net_cents"] = int(earnings_rows[0]["net"])
    counts = fast_query(
        "SELECT earning_type, COUNT(*) AS cnt FROM chain_creator_earnings WHERE creator_profile_id = %s GROUP BY earning_type",
        (creator_profile_id,), default=[]
    )
    if counts:
        for c in counts:
            t = c["earning_type"]
            n = int(c["cnt"])
            if t == "tip":
                result["tip_count"] = n
            elif t == "gift":
                result["gift_count"] = n
            elif t == "subscription":
                result["subscription_count"] = n
            elif t == "content_purchase":
                result["purchase_count"] = n
    sub_rows = fast_query(
        "SELECT COUNT(*) AS cnt FROM chain_creator_subscriptions WHERE creator_profile_id = %s AND status = 'active'",
        (creator_profile_id,), default=[{"cnt": 0}]
    )
    if sub_rows:
        result["subscriber_count"] = int(sub_rows[0]["cnt"])
    result["recent_earnings"] = get_creator_earnings(creator_profile_id, limit=20)
    return result
