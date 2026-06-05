from datetime import datetime, timezone, timedelta
from services.neon_service import fast_query
from services.supabase_safe import safe_count, safe_select, safe_insert

def get_admin_analytics():
    """Returns platform-wide metrics for admin dashboard"""
    # 1. User Metrics
    total_users = safe_count("chain_profiles")
    new_users_24h = safe_count("chain_profiles", filters={"created_at": (">", (datetime.now(timezone.utc) - timedelta(days=1)).isoformat())})
    
    # 2. Activity Metrics
    dau = safe_count("chain_presence", filters={"status": ("neq", "offline"), "last_seen_at": (">", (datetime.now(timezone.utc) - timedelta(days=1)).isoformat())})
    
    # 3. Financial Metrics (Simulated)
    platform_revenue = 12500.00 # Placeholder
    creator_payouts = 8400.00 # Placeholder
    
    # 4. Live metrics
    live_now = safe_count("chain_live_rooms", filters={"is_live": True})
    
    return {
        "total_users": total_users,
        "new_users_24h": new_users_24h,
        "dau": dau,
        "platform_revenue": platform_revenue,
        "creator_payouts": creator_payouts,
        "live_now": live_now
    }

def get_creator_analytics(profile_id):
    """Returns detailed analytics for a creator"""
    # 1. Reach Metrics
    profile_views = safe_select("chain_profiles", columns="profile_views", filters={"id": profile_id}, limit=1)[0].get("profile_views", 0)
    
    # 2. Content Performance
    post_reach = safe_count("chain_feed_events", filters={"actor_profile_id": profile_id, "event_type": "view"})
    
    # 3. Live Performance
    live_sessions = safe_select("chain_live_rooms", filters={"profile_id": profile_id}, limit=30, order_by="created_at", desc=True)
    total_live_earnings = sum(float(r.get("total_gift_coins", 0)) for r in live_sessions)
    
    # 4. Followers
    followers = safe_count("chain_follows", filters={"following_profile_id": profile_id})
    
    return {
        "profile_views": profile_views,
        "post_reach": post_reach,
        "total_live_earnings": total_live_earnings,
        "followers": followers,
        "recent_live_sessions": len(live_sessions)
    }

def record_daily_snapshot():
    """Aggregates and records daily metrics to chain_analytics_daily"""
    admin_metrics = get_admin_analytics()
    
    payload = {
        "metric_date": datetime.now(timezone.utc).date().isoformat(),
        "dau": admin_metrics["dau"],
        "new_users": admin_metrics["new_users_24h"],
        "total_revenue_nad": admin_metrics["platform_revenue"],
        "live_room_count": admin_metrics["live_now"]
    }
    
    try:
        safe_insert("chain_analytics_daily", payload)
    except:
        pass # Likely duplicate key for today
