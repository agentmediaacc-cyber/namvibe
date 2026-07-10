from datetime import datetime, timezone, timedelta

from services.neon_service import execute, fetch_all, fetch_one


def _today_start():
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _days_ago(days):
    return (_today_start() - timedelta(days=days)).isoformat()


# ── Overview ──────────────────────────────────────────────────────────

def get_overview_stats():
    today = _today_start().isoformat()
    week_ago = _days_ago(7)
    month_ago = _days_ago(30)
    return {
        "total_users": _count("chain_profiles"),
        "active_today": _count_gt("chain_profiles", "last_login_at", today),
        "active_week": _count_gt("chain_profiles", "last_login_at", week_ago),
        "new_today": _count_gt("chain_profiles", "created_at", today),
        "new_week": _count_gt("chain_profiles", "created_at", week_ago),
        "new_month": _count_gt("chain_profiles", "created_at", month_ago),
        "total_posts": _count("chain_posts"),
        "total_reels": _count("chain_reels"),
        "total_stories": _count("chain_stories"),
        "total_live_rooms": _count("chain_live_rooms"),
        "total_messages": _count("chain_messages"),
        "total_wallets": _count("chain_wallets"),
        "total_transactions": _count("chain_wallet_transactions"),
        "total_comments": _count("chain_post_comments"),
        "total_likes": _count("chain_likes"),
        "total_follows": _count("chain_follows"),
        "creators": _count_where("chain_profiles", "is_creator", True),
        "verified_users": _count_where("chain_profiles", "identity_verified", True),
        "live_now": _count_where("chain_live_rooms", "status", "live"),
    }


def get_user_growth(days=30):
    rows = fetch_all("""
        SELECT DATE(created_at) as day, COUNT(*) as count
        FROM chain_profiles
        WHERE created_at >= %s
        GROUP BY DATE(created_at)
        ORDER BY day
    """, (_days_ago(days),), timeout_ms=30000)
    return [{"day": str(r["day"]), "count": r["count"]} for r in (rows or [])]


# ── Users ─────────────────────────────────────────────────────────────

def get_all_users(limit=100, offset=0):
    return fetch_all("""
        SELECT id, username, full_name, email, is_creator, is_verified,
               identity_verified, gold_badge, premium_tier, completion_percentage,
               created_at, last_login_at
        FROM chain_profiles
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """, (limit, offset), timeout_ms=30000) or []


def search_users(query, limit=50):
    like = f"%{query}%"
    return fetch_all("""
        SELECT id, username, full_name, email, is_creator, is_verified,
               identity_verified, completion_percentage, created_at
        FROM chain_profiles
        WHERE username ILIKE %s OR full_name ILIKE %s OR email ILIKE %s
        ORDER BY created_at DESC LIMIT %s
    """, (like, like, like, limit), timeout_ms=30000) or []


def get_user_detail(profile_id):
    return fetch_one("""
        SELECT * FROM chain_profiles WHERE id = %s
    """, (profile_id,), timeout_ms=30000)


# ── Finance ───────────────────────────────────────────────────────────

def get_finance_summary():
    total_nad = fetch_one("""
        SELECT COALESCE(SUM(balance_cents), 0) as total_cents,
               COUNT(*) as wallet_count
        FROM chain_wallets
    """, timeout_ms=30000)
    recent_revenue = fetch_one("""
        SELECT COALESCE(SUM(amount_cents), 0) as revenue_cents
        FROM chain_wallet_transactions
        WHERE direction = 'in' AND created_at >= %s
    """, (_days_ago(30),), timeout_ms=30000)
    pending_payouts = fetch_one("""
        SELECT COALESCE(SUM(amount_coins), 0) as pending_coins
        FROM chain_creator_payouts WHERE status = 'pending'
    """, timeout_ms=30000)
    return {
        "total_balance_nad": (total_nad["total_cents"] / 100) if total_nad else 0,
        "wallet_count": total_nad["wallet_count"] if total_nad else 0,
        "revenue_30d_nad": (recent_revenue["revenue_cents"] / 100) if recent_revenue else 0,
        "pending_payouts_nad": (pending_payouts["pending_coins"] / 100) if pending_payouts else 0,
    }


def get_recent_transactions(limit=50):
    return fetch_all("""
        SELECT wt.*, p.username
        FROM chain_wallet_transactions wt
        LEFT JOIN chain_profiles p ON wt.profile_id = p.id
        ORDER BY wt.created_at DESC LIMIT %s
    """, (limit,), timeout_ms=30000) or []


def get_payout_requests():
    return fetch_all("""
        SELECT cp.*, p.username, p.full_name
        FROM chain_creator_payouts cp
        LEFT JOIN chain_profiles p ON cp.creator_profile_id = p.id
        ORDER BY cp.created_at DESC LIMIT 100
    """, timeout_ms=30000) or []


# ── NVC Coins ─────────────────────────────────────────────────────────

def get_coin_summary():
    stats = fetch_one("""
        SELECT
            COALESCE(SUM(coin_balance), 0) as total_nvc,
            COUNT(*) as wallet_count
        FROM chain_wallets
    """, timeout_ms=30000) or {}
    topups = fetch_one("""
        SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total_amount
        FROM chain_wallet_transactions
        WHERE transaction_type = 'topup' AND created_at >= %s
    """, (_days_ago(30),), timeout_ms=30000) or {}
    gifts = fetch_one("""
        SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total_amount
        FROM chain_live_gifts
        WHERE created_at >= %s
    """, (_days_ago(30),), timeout_ms=30000) or {}
    return {
        "total_nvc": int(stats.get("total_nvc", 0)),
        "wallet_count": int(stats.get("wallet_count", 0)),
        "topups_30d": int(topups.get("count", 0)),
        "topup_coins_30d": int(topups.get("total_amount", 0)),
        "gifts_30d": int(gifts.get("count", 0)),
        "gift_coins_30d": int(gifts.get("total_amount", 0)),
    }


# ── Content ───────────────────────────────────────────────────────────

def get_content_stats():
    return {
        "posts": _count("chain_posts"),
        "reels": _count("chain_reels"),
        "stories": _count("chain_stories"),
        "live_rooms": _count_where("chain_live_rooms", "status", "live"),
        "comments": _count("chain_post_comments"),
        "likes": _count("chain_likes"),
        "media_uploads": _count("chain_media_uploads"),
        "groups": _count("chain_groups"),
        "marketplace_items": _count("chain_products"),
        "collections": _count("chain_collections"),
    }


# ── Reports / Moderation ──────────────────────────────────────────────

def get_moderation_queue():
    reports = fetch_all("""
        SELECT r.*, p.username as reporter_name, t.username as target_name
        FROM chain_reports r
        LEFT JOIN chain_profiles p ON r.reporter_profile_id = p.id
        LEFT JOIN chain_profiles t ON r.target_profile_id = t.id
        ORDER BY r.created_at DESC LIMIT 100
    """, timeout_ms=30000) or []
    flags = fetch_all("""
        SELECT cf.*
        FROM chain_content_flags cf
        ORDER BY cf.created_at DESC LIMIT 100
    """, timeout_ms=30000) or []
    appeals = fetch_all("""
        SELECT a.*
        FROM chain_appeals a
        ORDER BY a.created_at DESC LIMIT 100
    """, timeout_ms=30000) or []
    return {
        "reports": reports,
        "content_flags": flags,
        "appeals": appeals,
        "report_count": len(reports),
        "flag_count": len(flags),
        "appeal_count": len(appeals),
    }


def get_support_tickets():
    tickets = fetch_all("""
        SELECT sr.*, p.username
        FROM chain_support_reports sr
        LEFT JOIN chain_profiles p ON sr.profile_id = p.id
        ORDER BY sr.created_at DESC LIMIT 100
    """, timeout_ms=30000) or []
    return tickets


# ── System Health ─────────────────────────────────────────────────────

def get_system_health():
    db_check = fetch_one("SELECT 1 as ok", timeout_ms=30000)
    user_count = _count("chain_profiles")
    recent_errors = fetch_all("""
        SELECT COUNT(*) as count, component, severity
        FROM chain_system_health_events
        WHERE created_at >= %s AND severity = 'error'
        GROUP BY component, severity ORDER BY count DESC LIMIT 10
    """, (_days_ago(1),), timeout_ms=30000) or []
    return {
        "database_ok": db_check is not None,
        "total_profiles": user_count,
        "recent_errors": recent_errors,
        "error_count_24h": sum(e["count"] for e in recent_errors),
    }


def get_security_events(limit=50):
    return fetch_all("""
        SELECT * FROM chain_security_events
        ORDER BY created_at DESC LIMIT %s
    """, (limit,), timeout_ms=30000) or []


def get_recent_messages(limit=50):
    return fetch_all("""
        SELECT m.id, m.body as content, m.created_at, s.username as sender_name,
               m.sender_profile_id, m.recipient_profile_id
        FROM chain_messages m
        LEFT JOIN chain_profiles s ON m.sender_profile_id = s.id
        ORDER BY m.created_at DESC LIMIT %s
    """, (limit,), timeout_ms=30000) or []


# ── Helpers ───────────────────────────────────────────────────────────

def _count(table):
    r = fetch_one(f"SELECT COUNT(*) as c FROM {table}", timeout_ms=30000)
    return r["c"] if r else 0


def _count_gt(table, col, since):
    r = fetch_one(f"SELECT COUNT(*) as c FROM {table} WHERE {col} >= %s", (since,), timeout_ms=30000)
    return r["c"] if r else 0


def _count_where(table, col, val):
    r = fetch_one(f"SELECT COUNT(*) as c FROM {table} WHERE {col} = %s", (val,), timeout_ms=30000)
    return r["c"] if r else 0
