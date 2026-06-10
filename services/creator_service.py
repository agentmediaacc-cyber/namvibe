import os, uuid, json
from datetime import datetime, timezone, timedelta
from services.neon_service import fast_query, write_query, get_pool_status
from services.creator_feature_service import (
    creator_dashboard as _feat_dashboard,
    get_subscriptions, get_paid_posts, get_premium_content,
    get_sponsorships, get_creator_badges,
)
from services.creator_monetization_service import (
    get_creator_dashboard as _monetization_dashboard,
    get_creator_earnings, send_tip, send_gift, subscribe_to_creator,
    get_available_gifts, create_paid_content,
)
from services.creator_analytics_engine import get_creator_stats, get_daily_views
from services.creator_verification_service import (
    get_creator_verification_status, submit_verification_request,
)

CREATOR_LEVELS_ORDER = [
    "creator", "verified_creator", "premium_creator", "business_creator",
]
CREATOR_LEVELS_DISPLAY = {
    "creator": "Creator",
    "verified_creator": "Verified Creator",
    "premium_creator": "Premium Creator",
    "business_creator": "Business Creator",
}


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _uuid(value=None):
    if value:
        try:
            return str(uuid.UUID(str(value)))
        except (TypeError, ValueError):
            pass
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


def get_creator_dashboard_data(profile_id):
    profile_id = _uuid(profile_id)
    feat = _feat_dashboard(profile_id)
    stats = get_creator_stats(profile_id)
    monet = _monetization_dashboard(profile_id) if _db_available() else {}
    ver = get_creator_verification_status(profile_id)
    profile = _get_profile_basics(profile_id)

    earnings_breakdown = _get_earnings_breakdown(profile_id)
    total_followers = (profile or {}).get("total_followers", 0) or (stats.get("followers_count", 0) or 0)
    total_views = (profile or {}).get("total_views", 0) or (stats.get("total_reel_views", 0) or 0)
    total_earnings = (profile or {}).get("total_earnings_cents", 0) or 0
    creator_level = (profile or {}).get("creator_level", "creator") or "creator"
    subscriber_count = (profile or {}).get("total_subscribers", 0) or feat.get("subscriptions", {}).get("active_count", 0) or 0
    total_tips = (profile or {}).get("total_tips_cents", 0) or 0
    total_gifts = (profile or {}).get("total_gifts_cents", 0) or 0

    return {
        "profile": profile,
        "total_followers": int(total_followers),
        "total_views": int(total_views),
        "earnings": {
            "total_cents": int(total_earnings),
            "total_coins": int(total_earnings / 100) if total_earnings else 0,
            "breakdown": earnings_breakdown,
        },
        "reels_performance": {
            "views": int(stats.get("total_reel_views", 0) or 0),
            "likes": int(stats.get("total_reel_likes", 0) or 0),
            "engagement_rate": float(stats.get("engagement_rate", 0) or 0),
        },
        "live_performance": {
            "earnings_cents": int(stats.get("total_live_earnings", 0) or 0),
            "earnings_coins": int((stats.get("total_live_earnings", 0) or 0) / 100),
        },
        "subscribers": int(subscriber_count),
        "tips_cents": int(total_tips),
        "gifts_cents": int(total_gifts),
        "creator_level": creator_level,
        "creator_level_display": CREATOR_LEVELS_DISPLAY.get(creator_level, creator_level),
        "verification_status": ver.get("status", "not_submitted"),
        "subscriptions": {
            "active_count": int(subscriber_count),
            "tiers": get_subscriptions(profile_id, limit=10),
        },
        "top_supporters": feat.get("top_supporters", []),
        "badges": get_creator_badges(profile_id, limit=20),
    }


def get_creator_analytics(profile_id, days=30):
    profile_id = _uuid(profile_id)
    result = {
        "views": _get_analytics_series(profile_id, "view", days),
        "engagement": _get_analytics_series(profile_id, "engagement", days),
        "follower_growth": _get_analytics_series(profile_id, "follower_growth", days),
        "earnings": _get_analytics_series(profile_id, "earnings", days),
        "summary": {},
    }
    for key in ["views", "engagement", "follower_growth", "earnings"]:
        series = result[key]
        total = sum(s.get("value", 0) for s in series)
        result["summary"][key] = {
            "total": total,
            "average": round(total / len(series), 2) if series else 0,
            "days": len(series),
        }
    return result


def get_creator_earnings_breakdown(profile_id):
    profile_id = _uuid(profile_id)
    return _get_earnings_breakdown(profile_id)


def support_creator(actor_profile_id, target_profile_id, action, **kwargs):
    actor_profile_id = _uuid(actor_profile_id)
    target_profile_id = _uuid(target_profile_id)
    if action == "follow":
        return _follow_creator(actor_profile_id, target_profile_id)
    elif action == "subscribe":
        tier = kwargs.get("tier", "basic")
        price_cents = int(kwargs.get("price_cents", 0) or 0)
        return subscribe_to_creator(actor_profile_id, target_profile_id, tier, price_cents)
    elif action == "tip":
        amount_cents = int(kwargs.get("amount_cents", 0) or 0)
        message = kwargs.get("message")
        return send_tip(actor_profile_id, target_profile_id, amount_cents, message)
    elif action == "gift":
        gift_id = kwargs.get("gift_id")
        gift_name = kwargs.get("gift_name")
        gift_emoji = kwargs.get("gift_emoji")
        price_cents = int(kwargs.get("price_cents", 0) or 0)
        return send_gift(actor_profile_id, target_profile_id, gift_id, gift_name, gift_emoji, price_cents)
    return {"ok": False, "error": f"unknown_action_{action}"}


def get_creator_profile_upgrade(profile_id):
    profile_id = _uuid(profile_id)
    profile = _get_profile_basics(profile_id)
    if not profile:
        return {}
    ver = get_creator_verification_status(profile_id)
    badges = get_creator_badges(profile_id, limit=20)
    subs = get_subscriptions(profile_id, limit=10)
    level = profile.get("creator_level", "creator") or "creator"
    level_display = CREATOR_LEVELS_DISPLAY.get(level, level)
    level_idx = CREATOR_LEVELS_ORDER.index(level) if level in CREATOR_LEVELS_ORDER else 0
    next_level = CREATOR_LEVELS_ORDER[level_idx + 1] if level_idx + 1 < len(CREATOR_LEVELS_ORDER) else None
    return {
        "profile_id": profile_id,
        "username": profile.get("username", ""),
        "display_name": profile.get("full_name", "") or profile.get("display_name", ""),
        "profile_photo": profile.get("profile_photo", ""),
        "creator_level": level,
        "creator_level_display": level_display,
        "next_level": next_level,
        "next_level_display": CREATOR_LEVELS_DISPLAY.get(next_level, "") if next_level else None,
        "is_verified": profile.get("is_verified", False) or profile.get("verified", False),
        "verified_badge": profile.get("verified_badge", "none"),
        "earnings_badge": profile.get("earnings_badge", "none"),
        "supporter_count": int(profile.get("supporter_count", 0) or 0),
        "verification_status": ver.get("status", "not_submitted"),
        "badges": badges,
        "subscription_tiers": subs,
        "total_followers": int(profile.get("total_followers", 0) or 0),
        "total_subscribers": int(profile.get("total_subscribers", 0) or 0),
        "total_earnings_cents": int(profile.get("total_earnings_cents", 0) or 0),
    }


def upgrade_creator_level(profile_id, target_level=None):
    profile_id = _uuid(profile_id)
    profile = _get_profile_basics(profile_id)
    if not profile:
        return {"ok": False, "error": "profile_not_found"}
    current = profile.get("creator_level", "creator") or "creator"
    if not target_level:
        idx = CREATOR_LEVELS_ORDER.index(current) if current in CREATOR_LEVELS_ORDER else 0
        target_level = CREATOR_LEVELS_ORDER[idx + 1] if idx + 1 < len(CREATOR_LEVELS_ORDER) else current
    if target_level not in CREATOR_LEVELS_ORDER:
        return {"ok": False, "error": f"invalid_level_{target_level}"}
    current_idx = CREATOR_LEVELS_ORDER.index(current) if current in CREATOR_LEVELS_ORDER else 0
    target_idx = CREATOR_LEVELS_ORDER.index(target_level)
    if target_idx <= current_idx and current != target_level:
        return {"ok": False, "error": "level_already_attained"}
    try:
        if _db_available():
            write_query(
                "UPDATE chain_profiles SET creator_level = %s, creator_level_updated_at = now() WHERE id = %s",
                (target_level, profile_id),
            )
            write_query(
                "INSERT INTO chain_creator_profile_upgrades (id, profile_id, upgrade_type, previous_level, new_level) VALUES (%s, %s, 'level_upgrade', %s, %s)",
                (str(uuid.uuid4()), profile_id, current, target_level),
            )
        return {"ok": True, "previous_level": current, "new_level": target_level}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def record_analytics_event(profile_id, event_type, value=1, metadata=None):
    profile_id = _uuid(profile_id)
    try:
        if _db_available():
            write_query(
                """INSERT INTO chain_creator_analytics_events (id, profile_id, event_type, event_date, value, metadata)
                   VALUES (%s, %s, %s, CURRENT_DATE, %s, %s::jsonb)
                   ON CONFLICT (profile_id, event_type, event_date)
                   DO UPDATE SET value = chain_creator_analytics_events.value + EXCLUDED.value""",
                (str(uuid.uuid4()), profile_id, event_type, value, json.dumps(metadata or {})),
            )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _get_profile_basics(profile_id):
    try:
        if _db_available():
            rows = fast_query(
                """SELECT id, username, full_name, display_name, profile_photo, cover_photo,
                          is_verified, verified, creator_level, total_views, total_earnings_cents,
                          total_followers, total_subscribers, total_tips_cents, total_gifts_cents,
                          supporter_count, verified_badge, earnings_badge, is_creator, creator_category
                   FROM chain_profiles WHERE id = %s LIMIT 1""",
                (profile_id,), default=[],
            )
            return dict(rows[0]) if rows else None
        return None
    except Exception:
        return None


def _get_earnings_breakdown(profile_id):
    breakdown = {"subscriptions": 0, "gifts": 0, "tips": 0, "content_purchase": 0}
    if not _db_available():
        return breakdown
    try:
        rows = fast_query(
            "SELECT earning_type, COALESCE(SUM(gross_amount_cents), 0) AS total FROM chain_creator_earnings WHERE creator_profile_id = %s GROUP BY earning_type",
            (profile_id,), default=[],
        )
        if rows:
            for r in rows:
                t = r.get("earning_type", "")
                if t in breakdown:
                    breakdown[t] = int(r.get("total", 0) or 0)
        return breakdown
    except Exception:
        return breakdown


def _get_analytics_series(profile_id, event_type, days):
    if not _db_available():
        return []
    try:
        since = (_now() - timedelta(days=days)).strftime("%Y-%m-%d")
        rows = fast_query(
            "SELECT event_date, value FROM chain_creator_analytics_events WHERE profile_id = %s AND event_type = %s AND event_date >= %s ORDER BY event_date ASC",
            (profile_id, event_type, since), default=[],
        )
        return [{"date": str(r["event_date"]), "value": int(r.get("value", 0) or 0)} for r in rows]
    except Exception:
        return []


def _follow_creator(actor_profile_id, target_profile_id):
    try:
        if not _db_available():
            return {"ok": True}
        existing = fast_query(
            "SELECT id FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s LIMIT 1",
            (actor_profile_id, target_profile_id), default=[],
        )
        if existing:
            return {"ok": False, "error": "already_following"}
        follow_id = str(uuid.uuid4())
        write_query(
            "INSERT INTO chain_follows (id, follower_profile_id, following_profile_id) VALUES (%s, %s, %s)",
            (follow_id, actor_profile_id, target_profile_id),
        )
        write_query(
            "UPDATE chain_profiles SET total_followers = total_followers + 1 WHERE id = %s",
            (target_profile_id,),
        )
        return {"ok": True, "follow_id": follow_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}
