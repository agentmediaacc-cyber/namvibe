import json
import time
import uuid
from datetime import datetime, timezone, timedelta, date
from functools import wraps

from services.creator_service import (
    get_creator_dashboard_data as _legacy_dashboard,
    get_creator_analytics as _legacy_analytics,
    get_creator_earnings_breakdown as _legacy_earnings_breakdown,
    support_creator as _legacy_support,
    get_creator_profile_upgrade as _legacy_profile_upgrade,
    record_analytics_event as _legacy_record_analytics,
)
from services.creator_monetization_service import (
    send_tip as _cm_send_tip,
    send_gift as _cm_send_gift,
    get_available_gifts as _cm_available_gifts,
    get_creator_earnings as _cm_earnings,
    subscribe_to_creator as _cm_subscribe,
    cancel_creator_subscription as _cm_unsubscribe,
    is_subscribed as _cm_is_subscribed,
    get_creator_dashboard as _cm_dashboard,
)
from services.creator_earnings_service import (
    record_earnings as _ce_record,
    get_earnings_summary as _ce_summary,
    get_earnings_history as _ce_history,
)
from services.profile_service import get_current_profile
from services.performance_monitor import track_timing
from services.supabase_safe import safe_select, safe_insert, safe_update, safe_delete, safe_count
from services.neon_service import fast_query, write_query


def _now():
    return datetime.now(timezone.utc)


def _now_iso():
    return _now().isoformat()


def _today():
    return date.today()


def _uuid(value=None):
    if value:
        try:
            return str(uuid.UUID(str(value)))
        except (TypeError, ValueError):
            pass
    return str(uuid.uuid4())


def _cents(v):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError, OverflowError):
        return 0


def _track_op(name):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                track_timing(f"creator.{name}", round((time.perf_counter() - start) * 1000, 2))
                return result
            except Exception as e:
                track_timing(f"creator.{name}.error", round((time.perf_counter() - start) * 1000, 2))
                return {"ok": False, "error": str(e)}
        return wrapper
    return decorator


# ─── Dashboard ───

@_track_op("dashboard")
def get_studio_dashboard(profile_id):
    profile_id = _uuid(profile_id)
    legacy = _legacy_dashboard(profile_id)
    earnings = _ce_summary(profile_id)
    monet = _cm_dashboard(profile_id) if callable(getattr(_cm_dashboard, '__call__', None)) else {}

    total_earnings = legacy.get("earnings", {}).get("total_cents", 0) or 0
    available = earnings.get("available_cents", 0) or 0
    pending = earnings.get("pending_cents", 0) or 0
    withdrawn = earnings.get("withdrawn_cents", 0) or 0

    overview = {
        "total_followers": legacy.get("total_followers", 0) or 0,
        "total_views": legacy.get("total_views", 0) or 0,
        "total_earnings_cents": total_earnings,
        "available_cents": available,
        "pending_cents": pending,
        "withdrawn_cents": withdrawn,
        "reel_count": legacy.get("reels_performance", {}).get("count", 0) or 0,
        "story_count": legacy.get("story_performance", {}).get("count", 0) or 0,
        "live_count": legacy.get("live_performance", {}).get("count", 0) or 0,
        "engagement_rate": legacy.get("reels_performance", {}).get("engagement_rate", 0) or 0,
        "subscriber_count": legacy.get("subscriptions", {}).get("active_count", 0) or monet.get("active_subscribers", 0) or 0,
    }

    followers_growth = _get_followers_growth(profile_id, days=30)
    revenue_summary = _get_revenue_summary(profile_id)

    return {
        "ok": True,
        "overview": overview,
        "followers_growth": followers_growth,
        "revenue_summary": revenue_summary,
        "earnings_breakdown": legacy.get("earnings", {}).get("breakdown", {}),
        "reels_performance": legacy.get("reels_performance", {}),
        "story_performance": legacy.get("story_performance", {}),
        "live_performance": legacy.get("live_performance", {}),
        "profile": legacy.get("profile"),
    }


def _get_followers_growth(profile_id, days=30):
    try:
        rows = fast_query(
            """
            SELECT DATE(created_at) AS day, COUNT(*) AS count
            FROM chain_follows
            WHERE following_profile_id = %s AND created_at >= NOW() - INTERVAL '%s days'
            GROUP BY day ORDER BY day
            """,
            (profile_id, days), default=[]
        )
        return [{"date": str(r["day"]), "count": r["count"]} for r in rows]
    except Exception:
        return []


def _get_revenue_summary(profile_id):
    try:
        earnings = _ce_summary(profile_id)
        history = _ce_history(profile_id, limit=500)
        by_type = {}
        for e in history:
            st = e.get("source_type", "other")
            amt = _cents(e.get("amount", 0))
            by_type[st] = by_type.get(st, 0) + amt
        return {
            "total_cents": earnings.get("total_gross", 0),
            "available_cents": earnings.get("available_cents", 0),
            "pending_cents": earnings.get("pending_cents", 0),
            "withdrawn_cents": earnings.get("withdrawn_cents", 0),
            "by_type": by_type,
        }
    except Exception:
        return {"total_cents": 0, "available_cents": 0, "pending_cents": 0, "withdrawn_cents": 0, "by_type": {}}


# ─── Advanced Analytics ───

@_track_op("analytics")
def get_studio_analytics(profile_id, period="weekly", days=30):
    profile_id = _uuid(profile_id)
    legacy = _legacy_analytics(profile_id, days=days) if callable(getattr(_legacy_analytics, '__call__', None)) else _get_legacy_analytics_fallback(profile_id, days)

    trends = _get_trend_data(profile_id, period, days)
    top_content = _get_top_content(profile_id, limit=10)
    traffic = _get_traffic_sources(profile_id, days)

    result = {
        "ok": True,
        "period": period,
        "days": days,
        "views_series": legacy.get("views_series", trends.get("views", [])),
        "engagement_series": legacy.get("engagement_series", trends.get("engagement", [])),
        "follower_growth_series": legacy.get("follower_growth_series", trends.get("followers", [])),
        "earnings_series": legacy.get("earnings_series", trends.get("earnings", [])),
        "top_content": top_content,
        "traffic_sources": traffic,
        "totals": {
            "views": legacy.get("total_views", 0) or sum(t.get("v", 0) for t in trends.get("views", [])),
            "likes": legacy.get("total_likes", 0) or 0,
            "comments": legacy.get("total_comments", 0) or 0,
            "shares": legacy.get("total_shares", 0) or 0,
            "followers_gained": legacy.get("total_followers_gained", 0) or sum(t.get("c", 0) for t in trends.get("followers", [])),
            "earnings_cents": legacy.get("total_earnings_cents", 0) or sum(t.get("e", 0) for t in trends.get("earnings", [])),
        },
    }

    retention = _get_retention_data(profile_id)
    if retention:
        result["retention"] = retention

    completion = _get_completion_rates(profile_id)
    if completion:
        result["completion_rates"] = completion

    return result


def _get_legacy_analytics_fallback(profile_id, days):
    views = _get_trend_data(profile_id, "daily", days)
    return {
        "views_series": views.get("views", []),
        "engagement_series": views.get("engagement", []),
        "follower_growth_series": views.get("followers", []),
        "earnings_series": views.get("earnings", []),
        "total_views": 0,
        "total_likes": 0,
        "total_comments": 0,
        "total_shares": 0,
        "total_followers_gained": 0,
        "total_earnings_cents": 0,
    }


def _get_trend_data(profile_id, period, days):
    try:
        interval = "day" if period == "daily" else ("week" if period == "weekly" else "month")
        rows = fast_query(
            f"""
            SELECT DATE_TRUNC(%s, created_at) AS bucket,
                   COUNT(*) AS total
            FROM chain_creator_analytics_events
            WHERE profile_id = %s AND created_at >= NOW() - INTERVAL '%s days'
            GROUP BY bucket ORDER BY bucket
            """,
            (interval, profile_id, days), default=[]
        )
        return {"views": [{"d": str(r["bucket"]), "v": r["total"]} for r in rows]}
    except Exception:
        return {"views": [], "engagement": [], "followers": [], "earnings": []}


def _get_top_content(profile_id, limit=10):
    try:
        reels = fast_query(
            "SELECT id, caption, views_count, likes_count, comments_count, created_at FROM chain_reels WHERE profile_id = %s ORDER BY views_count DESC LIMIT %s",
            (profile_id, limit), default=[]
        )
        posts = fast_query(
            "SELECT id, caption, view_count, like_count, comment_count, created_at FROM chain_posts WHERE profile_id = %s ORDER BY view_count DESC LIMIT %s",
            (profile_id, limit), default=[]
        )
        result = []
        for r in reels:
            result.append({"type": "reel", "id": str(r["id"]), "title": (r.get("caption") or "")[:80], "views": r.get("views_count", 0) or 0, "likes": r.get("likes_count", 0) or 0, "comments": r.get("comments_count", 0) or 0})
        for p in posts:
            result.append({"type": "post", "id": str(p["id"]), "title": (p.get("caption") or "")[:80], "views": p.get("view_count", 0) or 0, "likes": p.get("like_count", 0) or 0, "comments": p.get("comment_count", 0) or 0})
        result.sort(key=lambda x: x["views"], reverse=True)
        return result[:limit]
    except Exception:
        return []


def _get_traffic_sources(profile_id, days):
    try:
        rows = fast_query(
            """
            SELECT source, COUNT(*) AS count
            FROM chain_analytics_events
            WHERE profile_id = %s AND event_type = 'profile_view'
              AND created_at >= NOW() - INTERVAL '%s days'
            GROUP BY source ORDER BY count DESC
            """,
            (profile_id, days), default=[]
        )
        return [{"source": r.get("source", "direct") or "direct", "count": r["count"]} for r in rows]
    except Exception:
        return []


def _get_retention_data(profile_id):
    try:
        rows = fast_query(
            """
            SELECT AVG(completion_percent) AS avg_retention,
                   COUNT(*) AS total_watches
            FROM chain_reel_watch_events
            WHERE reel_id IN (SELECT id FROM chain_reels WHERE profile_id = %s)
            """,
            (profile_id,), default=[]
        )
        if rows and rows[0].get("avg_retention"):
            return {"avg_completion_pct": round(float(rows[0]["avg_retention"]), 1), "total_watches": rows[0]["total_watches"]}
        return None
    except Exception:
        return None


def _get_completion_rates(profile_id):
    try:
        rows = fast_query(
            """
            SELECT
                SUM(CASE WHEN completion_percent >= 75 THEN 1 ELSE 0 END) AS completed,
                COUNT(*) AS total
            FROM chain_reel_watch_events
            WHERE reel_id IN (SELECT id FROM chain_reels WHERE profile_id = %s)
            """,
            (profile_id,), default=[]
        )
        if rows and rows[0].get("total", 0) > 0:
            total = rows[0]["total"]
            completed = rows[0]["completed"] or 0
            return {"completed_count": completed, "total_count": total, "completion_rate": round(completed / total * 100, 1)}
        return None
    except Exception:
        return None


# ─── Monetization ───

@_track_op("earnings")
def get_studio_earnings(profile_id):
    profile_id = _uuid(profile_id)
    summary = _ce_summary(profile_id)
    history = _ce_history(profile_id, limit=200)

    total_gross = summary.get("total_gross", 0) or 0
    available = summary.get("available_cents", 0) or 0
    pending = summary.get("pending_cents", 0) or 0

    return {
        "ok": True,
        "summary": {
            "total_gross_cents": total_gross,
            "available_cents": available,
            "pending_cents": pending,
            "withdrawn_cents": summary.get("withdrawn_cents", 0) or 0,
            "reversed_cents": summary.get("reversed_cents", 0) or 0,
        },
        "history": history,
        "available_gifts": _cm_available_gifts() if callable(getattr(_cm_available_gifts, '__call__', None)) else [],
        "gift_catalog": _get_gift_catalog(),
    }


@_track_op("earnings_by_type")
def get_earnings_by_type(profile_id, days=90):
    profile_id = _uuid(profile_id)
    history = _ce_history(profile_id, limit=500)
    by_type = {}
    period_start = _now() - timedelta(days=days)
    for e in history:
        created = e.get("created_at")
        if created and hasattr(created, 'tzinfo'):
            if created < period_start:
                continue
        st = e.get("source_type", "other")
        amt = _cents(e.get("amount", 0))
        by_type[st] = by_type.get(st, 0) + amt
    return {"ok": True, "by_type": by_type, "days": days}


@_track_op("transaction_history")
def get_transaction_history(profile_id, limit=50, offset=0):
    history = _ce_history(profile_id, limit=limit, offset=offset)
    enriched = []
    for e in history:
        enriched.append({
            "id": str(e.get("id", "")),
            "source_type": e.get("source_type", "other"),
            "amount_cents": _cents(e.get("amount", 0)),
            "currency": e.get("currency", "NAD"),
            "status": e.get("status", "pending"),
            "created_at": e.get("created_at").isoformat() if hasattr(e.get("created_at"), 'isoformat') else str(e.get("created_at", "")),
        })
    return {"ok": True, "transactions": enriched}


# ─── Content Management ───

@_track_op("drafts_list")
def get_drafts(profile_id, content_type=None, limit=50):
    filters = {"profile_id": _uuid(profile_id)}
    if content_type:
        filters["content_type"] = content_type
    drafts = safe_select("chain_creator_drafts", limit=limit, filters=filters, order_by="updated_at", desc=True)
    return {"ok": True, "drafts": drafts}


@_track_op("draft_create")
def create_draft(profile_id, content_type="post", title="", body="", media_url="", metadata=None):
    payload = {
        "profile_id": _uuid(profile_id),
        "content_type": content_type or "post",
        "title": (title or "").strip(),
        "body": (body or "").strip(),
        "media_url": (media_url or "").strip(),
        "metadata": json.dumps(metadata or {}),
    }
    inserted = safe_insert("chain_creator_drafts", payload)
    if inserted:
        draft = inserted[0] if isinstance(inserted, list) and inserted else inserted
        return {"ok": True, "draft": draft}
    return {"ok": False, "error": "create_failed"}


@_track_op("draft_update")
def update_draft(draft_id, title=None, body=None, media_url=None, metadata=None):
    updates = {}
    if title is not None:
        updates["title"] = title.strip()
    if body is not None:
        updates["body"] = body.strip()
    if media_url is not None:
        updates["media_url"] = media_url.strip()
    if metadata is not None:
        updates["metadata"] = json.dumps(metadata)
    if not updates:
        return {"ok": True}
    updates["updated_at"] = _now_iso()
    ok = safe_update("chain_creator_drafts", updates, eq={"id": draft_id})
    return {"ok": bool(ok)}


@_track_op("draft_delete")
def delete_draft(draft_id):
    ok = safe_delete("chain_creator_drafts", eq={"id": draft_id})
    return {"ok": bool(ok)}


# ─── Scheduled Publishing ───

@_track_op("scheduled_list")
def get_scheduled_posts(profile_id, status=None, limit=50):
    filters = {"profile_id": _uuid(profile_id)}
    if status:
        filters["status"] = status
    posts = safe_select("chain_creator_scheduled_posts", limit=limit, filters=filters, order_by="scheduled_at", desc=False)
    return {"ok": True, "posts": posts}


@_track_op("scheduled_create")
def create_scheduled_post(profile_id, scheduled_at, content_type="post", title="", body="", media_url="", metadata=None):
    payload = {
        "profile_id": _uuid(profile_id),
        "content_type": content_type or "post",
        "title": (title or "").strip(),
        "body": (body or "").strip(),
        "media_url": (media_url or "").strip(),
        "metadata": json.dumps(metadata or {}),
        "scheduled_at": scheduled_at,
    }
    inserted = safe_insert("chain_creator_scheduled_posts", payload)
    if inserted:
        post = inserted[0] if isinstance(inserted, list) and inserted else inserted
        return {"ok": True, "post": post}
    return {"ok": False, "error": "create_failed"}


@_track_op("scheduled_cancel")
def cancel_scheduled_post(post_id):
    ok = safe_update("chain_creator_scheduled_posts", {"status": "cancelled"}, eq={"id": post_id})
    return {"ok": bool(ok)}


# ─── Archive / Restore / Delete ───

@_track_op("archive")
def archive_content(profile_id, entity_type, entity_id):
    existing = safe_select("chain_creator_content_archive", limit=1, filters={"entity_type": entity_type, "entity_id": entity_id}, order_by=None)
    if existing:
        return {"ok": True, "archived": True}
    payload = {"profile_id": _uuid(profile_id), "entity_type": entity_type, "entity_id": _uuid(entity_id)}
    inserted = safe_insert("chain_creator_content_archive", payload)
    return {"ok": bool(inserted), "archived": bool(inserted)}


@_track_op("restore")
def restore_content(entity_type, entity_id):
    ok = safe_update("chain_creator_content_archive", {"restored_at": _now_iso()}, eq={"entity_type": entity_type, "entity_id": entity_id})
    return {"ok": bool(ok), "restored": bool(ok)}


@_track_op("archived_list")
def get_archived_content(profile_id, limit=50):
    rows = safe_select("chain_creator_content_archive", limit=limit, filters={"profile_id": _uuid(profile_id), "restored_at": None}, order_by="archived_at", desc=True)
    return {"ok": True, "archived": rows}


# ─── Moderation ───

@_track_op("keyword_filters_list")
def get_keyword_filters(profile_id, is_active=None):
    filters = {"profile_id": _uuid(profile_id)}
    if is_active is not None:
        filters["is_active"] = bool(is_active)
    rows = safe_select("chain_creator_keyword_filters", limit=200, filters=filters, order_by="created_at", desc=True)
    return {"ok": True, "filters": rows}


@_track_op("keyword_filter_add")
def add_keyword_filter(profile_id, keyword, action="hide"):
    try:
        inserted = safe_insert("chain_creator_keyword_filters", {
            "profile_id": _uuid(profile_id),
            "keyword": keyword.strip().lower(),
            "action": action,
        })
        return {"ok": bool(inserted)}
    except Exception:
        return {"ok": False, "error": "duplicate_or_error"}


@_track_op("keyword_filter_remove")
def remove_keyword_filter(filter_id):
    ok = safe_delete("chain_creator_keyword_filters", eq={"id": filter_id})
    return {"ok": bool(ok)}


@_track_op("hidden_words_list")
def get_hidden_words(profile_id):
    rows = safe_select("chain_creator_hidden_words", limit=200, filters={"profile_id": _uuid(profile_id)}, order_by="created_at", desc=True)
    return {"ok": True, "words": [r["word"] for r in rows]}


@_track_op("hidden_word_add")
def add_hidden_word(profile_id, word):
    try:
        inserted = safe_insert("chain_creator_hidden_words", {
            "profile_id": _uuid(profile_id),
            "word": word.strip().lower(),
        })
        return {"ok": bool(inserted)}
    except Exception:
        return {"ok": False, "error": "duplicate_or_error"}


@_track_op("hidden_word_remove")
def remove_hidden_word(profile_id, word):
    ok = safe_delete("chain_creator_hidden_words", eq={"profile_id": _uuid(profile_id), "word": word.strip().lower()})
    return {"ok": bool(ok)}


@_track_op("review_queue")
def get_review_queue(profile_id, status="pending", limit=50):
    rows = safe_select("chain_creator_comment_review_queue", limit=limit, filters={"profile_id": _uuid(profile_id), "status": status}, order_by="created_at", desc=True)
    return {"ok": True, "queue": rows}


@_track_op("review_approve")
def approve_review_item(item_id):
    ok = safe_update("chain_creator_comment_review_queue", {"status": "approved", "reviewed_at": _now_iso()}, eq={"id": item_id})
    return {"ok": bool(ok)}


@_track_op("review_reject")
def reject_review_item(item_id):
    ok = safe_update("chain_creator_comment_review_queue", {"status": "rejected", "reviewed_at": _now_iso()}, eq={"id": item_id})
    return {"ok": bool(ok)}


# ─── Business Tools ───

@_track_op("link_hub_list")
def get_link_hub(profile_id):
    links = safe_select("chain_creator_link_hub", limit=50, filters={"profile_id": _uuid(profile_id), "is_active": True}, order_by="sort_order")
    return {"ok": True, "links": links}


@_track_op("link_hub_add")
def add_link_hub(profile_id, title, url, sort_order=0):
    try:
        inserted = safe_insert("chain_creator_link_hub", {
            "profile_id": _uuid(profile_id), "title": title.strip(), "url": url.strip(), "sort_order": int(sort_order),
        })
        return {"ok": bool(inserted)}
    except Exception:
        return {"ok": False, "error": "duplicate_or_error"}


@_track_op("link_hub_remove")
def remove_link_hub(link_id):
    ok = safe_delete("chain_creator_link_hub", eq={"id": link_id})
    return {"ok": bool(ok)}


@_track_op("contact_info_get")
def get_contact_info(profile_id):
    rows = safe_select("chain_creator_contact_info", limit=10, filters={"profile_id": _uuid(profile_id)}, order_by="contact_type")
    return {"ok": True, "contacts": rows}


@_track_op("contact_info_set")
def set_contact_info(profile_id, contact_type, contact_value, is_public=False):
    existing = safe_select("chain_creator_contact_info", limit=1, filters={"profile_id": _uuid(profile_id), "contact_type": contact_type}, order_by=None)
    if existing:
        ok = safe_update("chain_creator_contact_info", {"contact_value": contact_value.strip(), "is_public": bool(is_public)}, eq={"id": existing[0]["id"]})
    else:
        ok = safe_insert("chain_creator_contact_info", {
            "profile_id": _uuid(profile_id), "contact_type": contact_type, "contact_value": contact_value.strip(), "is_public": bool(is_public),
        })
    return {"ok": bool(ok)}


@_track_op("business_hours_get")
def get_business_hours(profile_id):
    rows = safe_select("chain_creator_business_hours", limit=7, filters={"profile_id": _uuid(profile_id)}, order_by="day_of_week")
    return {"ok": True, "hours": rows}


@_track_op("business_hours_set")
def set_business_hours(profile_id, day_of_week, open_time=None, close_time=None, is_closed=False):
    existing = safe_select("chain_creator_business_hours", limit=1, filters={"profile_id": _uuid(profile_id), "day_of_week": int(day_of_week)}, order_by=None)
    updates = {"is_closed": bool(is_closed)}
    if open_time:
        updates["open_time"] = open_time
    if close_time:
        updates["close_time"] = close_time
    if existing:
        ok = safe_update("chain_creator_business_hours", updates, eq={"id": existing[0]["id"]})
    else:
        updates.update({"profile_id": _uuid(profile_id), "day_of_week": int(day_of_week)})
        ok = safe_insert("chain_creator_business_hours", updates)
    return {"ok": bool(ok)}


@_track_op("business_profile_update")
def update_business_profile(profile_id, business_category=None, contact_button_label=None, contact_button_url=None):
    updates = {}
    if business_category is not None:
        updates["business_category"] = business_category.strip()
    if contact_button_label is not None:
        updates["contact_button_label"] = contact_button_label.strip()
    if contact_button_url is not None:
        updates["contact_button_url"] = contact_button_url.strip()
    if updates:
        from services.supabase_safe import safe_update as su
        su("chain_profiles", updates, eq={"id": _uuid(profile_id)})
    return {"ok": True}


# ─── Milestones & Notifications ───

@_track_op("milestones_list")
def get_milestones(profile_id, limit=20):
    rows = safe_select("chain_creator_milestones", limit=limit, filters={"profile_id": _uuid(profile_id)}, order_by="reached_at", desc=True)
    return {"ok": True, "milestones": rows}


@_track_op("check_milestones")
def check_and_notify_milestones(profile_id):
    profile_id = _uuid(profile_id)
    dashboard = get_studio_dashboard(profile_id)
    if not dashboard.get("ok"):
        return {"ok": False}
    ov = dashboard.get("overview", {})

    milestones_to_check = [
        ("followers", ov.get("total_followers", 0), [10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000]),
        ("earnings_cents", ov.get("total_earnings_cents", 0), [1000, 5000, 10000, 50000, 100000, 500000, 1000000]),
        ("views", ov.get("total_views", 0), [100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000]),
    ]

    new_milestones = []
    for mtype, current, thresholds in milestones_to_check:
        for threshold in thresholds:
            if current >= threshold:
                existing = safe_count("chain_creator_milestones", filters={"profile_id": profile_id, "milestone_type": mtype, "milestone_value": threshold})
                if existing == 0:
                    label = f"{threshold:,} {mtype.replace('_', ' ').title()}"
                    inserted = safe_insert("chain_creator_milestones", {
                        "profile_id": profile_id, "milestone_type": mtype,
                        "milestone_value": float(threshold), "label": label,
                    })
                    if inserted:
                        new_milestones.append({"type": mtype, "value": threshold, "label": label})
                        _send_milestone_notification(profile_id, label)

    return {"ok": True, "new_milestones": new_milestones}


def _send_milestone_notification(profile_id, label):
    try:
        from services.notification_center_service import create_notification as _notif
        _notif(
            recipient_profile_id=profile_id,
            notification_type="creator_milestone",
            title="Creator Milestone!",
            body=f"You reached {label}!",
            actor_profile_id=profile_id,
            action_url="/creator/dashboard",
        )
    except Exception:
        try:
            from services.notification_engine import create_notification as _notif
            _notif(
                recipient_profile_id=profile_id,
                event_type="creator_milestone",
                title="Creator Milestone!",
                body=f"You reached {label}!",
                actor_profile_id=profile_id,
                action_url="/creator/dashboard",
            )
        except Exception:
            pass


@_track_op("weekly_summary")
def get_or_create_weekly_summary(profile_id):
    profile_id = _uuid(profile_id)
    week_start = _today() - timedelta(days=_today().weekday())
    week_end = week_start + timedelta(days=6)

    existing = safe_select("chain_creator_weekly_summaries", limit=1, filters={"profile_id": profile_id, "week_start": week_start.isoformat()}, order_by=None)
    if existing:
        return {"ok": True, "summary": existing[0]}

    dashboard = get_studio_dashboard(profile_id)
    if not dashboard.get("ok"):
        return {"ok": False}

    ov = dashboard.get("overview", {})
    summary_data = {
        "total_followers": ov.get("total_followers", 0),
        "total_views": ov.get("total_views", 0),
        "total_earnings_cents": ov.get("total_earnings_cents", 0),
        "new_earnings_cents": ov.get("pending_cents", 0),
        "engagement_rate": ov.get("engagement_rate", 0),
        "generated_at": _now_iso(),
    }

    inserted = safe_insert("chain_creator_weekly_summaries", {
        "profile_id": profile_id,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "summary": json.dumps(summary_data),
    })
    if inserted:
        row = inserted[0] if isinstance(inserted, list) else inserted
        return {"ok": True, "summary": row}
    return {"ok": True, "summary": {"summary": summary_data}}


def _get_gift_catalog():
    try:
        from services.live_streaming_service import get_gift_catalog
        return get_gift_catalog()
    except Exception:
        return []


# ─── Payout Security (duplicate prevention) ───

@_track_op("check_duplicate_payout")
def check_duplicate_payout(profile_id, amount_cents, reference_id=None):
    if reference_id:
        existing = safe_count("chain_creator_earnings", filters={
            "creator_profile_id": _uuid(profile_id),
            "source_id": reference_id,
            "status": ("in", ["available", "withdrawn"]),
        })
        if existing > 0:
            return {"ok": True, "is_duplicate": True, "reason": "reference_id_already_paid"}
    return {"ok": True, "is_duplicate": False}
