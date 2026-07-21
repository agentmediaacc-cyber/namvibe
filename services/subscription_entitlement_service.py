"""Server-authoritative subscription entitlement resolution."""

from __future__ import annotations

from datetime import datetime, timezone

from services.neon_service import fast_query, get_pool_status


def _iso(value):
    if not value:
        return None
    if isinstance(value, str):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _active(row):
    if not row:
        return False
    status = str(row.get("status") or row.get("subscription_status") or "").lower()
    if status in {"active", "trialing", "granted"}:
        expires_at = row.get("expires_at") or row.get("ends_at")
        if not expires_at:
            return True
        try:
            if isinstance(expires_at, str):
                dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            else:
                dt = expires_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt > datetime.now(timezone.utc)
        except Exception:
            return False
    return False


def _first_active_subscription(profile_id):
    candidates = [
        (
            "chain_premium_subscriptions",
            """
            SELECT id, profile_id, premium_tier, tier, status, subscription_status, starts_at, started_at, expires_at, ends_at, source, source_type, source_id, created_at, updated_at
            FROM chain_premium_subscriptions
            WHERE profile_id = %s
            ORDER BY COALESCE(updated_at, created_at, starts_at, started_at) DESC NULLS LAST
            LIMIT 1
            """,
        ),
        (
            "chain_subscriptions",
            """
            SELECT id, subscriber_profile_id AS profile_id, plan AS premium_tier, tier, status, subscription_status, starts_at, started_at, expires_at, ends_at, source, source_type, source_id, created_at, updated_at
            FROM chain_subscriptions
            WHERE subscriber_profile_id = %s
            ORDER BY COALESCE(updated_at, created_at, starts_at, started_at) DESC NULLS LAST
            LIMIT 1
            """,
        ),
    ]
    for source_name, query in candidates:
        try:
            rows = fast_query(query, (profile_id,), default=[]) or []
        except Exception:
            rows = []
        if rows:
            row = dict(rows[0])
            row["_source_table"] = source_name
            return row
    return {}


def get_entitlement(profile_id, *, profile=None):
    profile = profile or {}
    status = {}
    try:
        status = get_pool_status() or {}
    except Exception:
        status = {}
    if not (status.get("pool_ready") or status.get("recent_success") or status.get("configured")):
        return {
            "effective_plan": "free",
            "subscription_status": "free",
            "is_premium": False,
            "starts_at": None,
            "expires_at": None,
            "features": [],
            "source": "free_default",
            "verification_status": "separate",
            "promotion_eligible": False,
            "subscription": {},
        }
    subscription = _first_active_subscription(profile_id)
    active = _active(subscription)
    plan = str(subscription.get("premium_tier") or subscription.get("tier") or subscription.get("plan") or "free").lower()
    status = str(subscription.get("subscription_status") or subscription.get("status") or ("active" if active else "free")).lower()
    if not active:
        plan = "free"
        status = "free" if not subscription else "inactive"
    return {
        "effective_plan": plan,
        "subscription_status": status,
        "is_premium": bool(active and plan not in {"", "free", "inactive"}),
        "starts_at": _iso(subscription.get("starts_at") or subscription.get("started_at")),
        "expires_at": _iso(subscription.get("expires_at") or subscription.get("ends_at")),
        "features": [],
        "source": subscription.get("_source_table") or ("db_subscription" if subscription else "free_default"),
        "verification_status": "separate",
        "promotion_eligible": bool(active),
        "subscription": subscription,
    }
