import json
from datetime import datetime, timezone, timedelta

import os

from flask import Blueprint, jsonify, redirect, render_template, request, session

from services.admin_auth_service import (
    admin_redirect_target,
    authenticate_admin,
    current_admin,
    get_site_setting,
    log_admin_action,
    login_admin_session,
    logout_admin_session,
    require_admin,
    require_master_admin,
    set_site_setting,
)
from services.marketplace_service import (
    approve_marketplace_item as approve_marketplace_item_action,
    approve_verification as approve_verification_action,
    feature_marketplace_item,
    reject_verification,
    reject_marketplace_item,
    unfeature_marketplace_item,
)
from services.supabase_safe import safe_count, safe_select
from services.wallet_action_service import (
    approve_topup as approve_topup_action,
    approve_withdrawal as approve_withdrawal_action,
    execute_withdrawal,
    reject_topup,
    reject_withdrawal,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _admin_metrics():
    creator_count = safe_count("chain_profiles", filters={"is_creator": True})
    seller_count = safe_count("chain_profiles", filters={"seller_mode_enabled": True})
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    return {
        "users": safe_count("chain_profiles"),
        "profiles": safe_count("chain_profiles"),
        "live_rooms": safe_count("chain_live_rooms"),
        "posts": safe_count("chain_posts"),
        "stories": safe_count("chain_status_posts") or safe_count("chain_stories"),
        "conversations": safe_count("chain_conversations"),
        "messages_today": safe_count("chain_messages", filters={"created_at": ("gt", today)}),
        "recent_calls": safe_count("chain_call_sessions", filters={"started_at": ("gt", (now - timedelta(days=7)).isoformat())}),
        "gifts": safe_count("chain_live_gifts") or safe_count("chain_gift_events"),
        "wallets": safe_count("chain_wallets"),
        "notifications": safe_count("chain_notifications"),
        "admins": safe_count("chain_admin_users"),
        "pending_topups": safe_count("chain_wallet_topups", filters={"status": "pending"}),
        "pending_withdrawals": safe_count("chain_wallet_withdrawals", filters={"status": "pending"}),
        "pending_marketplace_items": safe_count("chain_marketplace_items", filters={"approval_status": "pending"}),
        "pending_verifications": safe_count("chain_user_verifications", filters={"verification_status": "pending"}),
        "dating_opt_ins": safe_count("chain_dating_profiles", filters={"is_enabled": True}),
        "creators_sellers": creator_count + seller_count,
        "total_follows": safe_count("chain_follows"),
        "total_comments": safe_count("chain_post_comments") + safe_count("chain_live_comments_v2"),
        "total_reactions": safe_count("chain_post_reactions") + safe_count("chain_live_reactions"),
        "online_users": safe_count("chain_online_presence", filters={"is_online": True}),
    }


def _dashboard_context(section="overview"):
    from services.system_health_service import get_platform_health_snapshot
    from services.reporting_service import get_revenue_summary
    
    admin = current_admin()
    metrics = _admin_metrics()
    health = get_platform_health_snapshot()
    revenue = get_revenue_summary()
    settings_rows = safe_select("chain_site_settings", limit=12)
    recent_profiles = safe_select(
        "chain_profiles",
        columns="id,username,full_name,email,profile_completed,is_verified,created_at",
        limit=8,
    )
    recent_rooms = safe_select(
        "chain_live_rooms",
        columns="id,title,host_name,status,category,viewer_count,created_at",
        limit=8,
    )
    recent_posts = safe_select(
        "chain_posts",
        columns="id,profile_id,caption,body,created_at",
        limit=8,
    )
    audit_rows = safe_select(
        "chain_admin_audit_log",
        columns="id,admin_id,action,target_type,target_id,metadata,created_at",
        limit=12,
    )
    wallet_transactions = safe_select(
        "chain_wallet_transactions",
        columns="id,profile_id,transaction_type,direction,coins,amount_nad,status,description,created_at",
        limit=12,
    )
    topups = safe_select("chain_wallet_topups", limit=30)
    withdrawals = safe_select("chain_wallet_withdrawals", limit=30)
    marketplace_items = safe_select("chain_marketplace_items", limit=30)
    verifications = safe_select("chain_user_verifications", limit=30)
    admins = safe_select(
        "chain_admin_users",
        columns="id,username,email,full_name,role,is_master,is_active,created_at",
        limit=12,
    )

    feature_cards = [
        {"title": "Users", "value": metrics["users"], "href": "/admin/users", "copy": "Review member growth and profile completion."},
        {"title": "Profiles", "value": metrics["profiles"], "href": "/admin/users", "copy": "Open creator profiles and verification readiness."},
        {"title": "Live Rooms", "value": metrics["live_rooms"], "href": "/admin/content", "copy": "Monitor active rooms, categories and audience."},
        {"title": "Posts", "value": metrics["posts"], "href": "/admin/content", "copy": "Keep the feed polished and creator-safe."},
        {"title": "Stories", "value": metrics["stories"], "href": "/admin/content", "copy": "Track short-form momentum and recency."},
        {"title": "Gifts", "value": metrics["gifts"], "href": "/admin/content", "copy": "Watch the gift economy and premium support."},
        {"title": "Wallets", "value": metrics["wallets"], "href": "/admin/topups", "copy": "Review creator balances and wallet coverage."},
        {"title": "Reports", "value": len(audit_rows), "href": "/admin/audit", "copy": "Inspect operational actions and moderation notes."},
        {"title": "Site Settings", "value": len(settings_rows), "href": "/admin/settings", "copy": "Update homepage, moderation and platform switches."},
        {"title": "Homepage Controls", "value": "Live", "href": "/admin/settings", "copy": "Tune highlighted categories and featured moods."},
        {"title": "Creator Verification", "value": metrics["profiles"], "href": "/admin/users", "copy": "Review premium and verified creator pipelines."},
        {"title": "Content Moderation", "value": metrics["posts"] + metrics["stories"], "href": "/admin/content", "copy": "Keep posts, stories and rooms clean."},
        {"title": "Payment/Gift Economy", "value": metrics["gifts"], "href": "/admin/topups", "copy": "Track coins, gifts and wallet movement."},
        {"title": "System Health", "value": "Stable", "href": "/developer/dashboard", "copy": "Review route, content and control-center readiness."},
        {"title": "Pending Top-ups", "value": metrics["pending_topups"], "href": "/admin/topups", "copy": "Manual top-up approvals waiting for review."},
        {"title": "Pending Withdrawals", "value": metrics["pending_withdrawals"], "href": "/admin/withdrawals", "copy": "Creator withdrawals waiting for admin action."},
        {"title": "Pending Marketplace Items", "value": metrics["pending_marketplace_items"], "href": "/admin/marketplace", "copy": "Music, video and art listings pending approval."},
        {"title": "Pending Verifications", "value": metrics["pending_verifications"], "href": "/admin/verifications", "copy": "Human verification queue for trust and safety."},
        {"title": "Total Conversations", "value": metrics["conversations"], "href": "/admin/content", "copy": "Monitor total communication threads across the app."},
        {"title": "Messages Today", "value": metrics["messages_today"], "href": "/admin/content", "copy": "Track daily messaging volume and engagement."},
        {"title": "Active Statuses", "value": metrics["stories"], "href": "/admin/content", "copy": "Current user stories active on the rail."},
        {"title": "Recent Calls (7d)", "value": metrics["recent_calls"], "href": "/admin/content", "copy": "Audio and video call activity over the last week."},
        {"title": "Social Follows", "value": metrics["total_follows"], "href": "/admin/users", "copy": "Monitor connection growth between members."},
        {"title": "Community Comments", "value": metrics["total_comments"], "href": "/admin/content", "copy": "Track conversation volume across posts and rooms."},
        {"title": "Engagement Reactions", "value": metrics["total_reactions"], "href": "/admin/content", "copy": "Total likes and reactions across the platform."},
        {"title": "Users Online Now", "value": metrics["online_users"], "href": "/admin/users", "copy": "Current active members using the application."},
        {"title": "Dating Opt-ins", "value": metrics["dating_opt_ins"], "href": "/admin/users", "copy": "Members who enabled dating mode on the same account."},
        {"title": "Creators/Sellers", "value": metrics["creators_sellers"], "href": "/admin/users", "copy": "Profiles preparing to monetize music, video and art."},
    ]

    return {
        "section": section,
        "admin_user": admin,
        "metrics": metrics,
        "health": health,
        "revenue": revenue,
        "feature_cards": feature_cards,
        "settings_rows": settings_rows,
        "recent_profiles": recent_profiles,
        "recent_rooms": recent_rooms,
        "active_rooms": [r for r in recent_rooms if r.get("status") == "live"],
        "recent_posts": recent_posts,
        "audit_rows": audit_rows,
        "wallet_transactions": wallet_transactions,
        "topups": topups,
        "withdrawals": withdrawals,
        "marketplace_items": marketplace_items,
        "verifications": verifications,
        "admin_rows": admins,
        "site_settings_json": json.dumps(get_site_setting("homepage_controls", {"hero_mode": "premium", "featured_categories": []}), indent=2),
    }

@admin_bp.route("/streams/<room_id>/end", methods=["POST"])
@require_master_admin
def admin_end_stream(room_id):
    from services.live_service import end_live
    end_live(room_id)
    return redirect("/admin/dashboard")

@admin_bp.route("/system-audit")
@require_master_admin
def system_audit():
    return render_template("admin/system_audit.html", **_dashboard_context("audit"))


@admin_bp.route("/system-health")
@require_admin
def system_health():
    from services.system_health_service import get_platform_health_snapshot
    health = get_platform_health_snapshot()
    
    from services.content_service import upload_folder_status, verify_content_tables
    return render_template(
        "admin/system_health.html",
        admin_user=current_admin(),
        health=health,
        upload_folders=upload_folder_status(),
        content_tables=verify_content_tables(),
    )

@admin_bp.route("/reports/payouts/latest")
@require_master_admin
def report_payouts():
    from services.reporting_service import generate_creator_payout_csv
    from flask import Response
    csv_data = generate_creator_payout_csv(None) # Get all for now
    return Response(csv_data, mimetype="text/csv", headers={"Content-disposition": "attachment; filename=payouts.csv"})

@admin_bp.route("/reports/revenue/latest")
@require_master_admin
def report_revenue():
    from services.reporting_service import get_revenue_summary
    summary = get_revenue_summary()
    return jsonify(summary)


def _matches_query(row, query):
    if not query:
        return True
    needle = query.lower()
    hay = " ".join(str(value or "") for value in row.values()).lower()
    return needle in hay


def _filter_rows(rows, status_key, default_status_keys=None):
    status = (request.args.get("status") or "").strip().lower()
    query = (request.args.get("q") or "").strip()
    filtered = rows
    if status:
        keys = default_status_keys or [status_key]
        filtered = [row for row in filtered if any(str(row.get(key) or "").lower() == status for key in keys)]
    if query:
        filtered = [row for row in filtered if _matches_query(row, query)]
    return filtered, status, query


@admin_bp.route("/")
def admin_home():
    if session.get("admin_id"):
        admin = current_admin()
        if admin:
            return redirect(admin_redirect_target(admin))
    return redirect("/admin/login")


@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        ok, result = authenticate_admin(request.form.get("username"), request.form.get("password"))
        if ok:
            login_admin_session(result)
            log_admin_action(result["id"], "login", "admin_user", result["id"], {"username": result.get("username")})
            return redirect(admin_redirect_target(result))
        error = result
    return render_template("admin/login.html", error=error, next_path=request.args.get("next"))


@admin_bp.route("/logout")
def admin_logout():
    admin = current_admin()
    if admin:
        log_admin_action(admin["id"], "logout", "admin_user", admin["id"])
    logout_admin_session()
    return redirect("/admin/login")


@admin_bp.route("/dashboard")
@require_admin
def admin_dashboard():
    return render_template("admin/dashboard.html", **_dashboard_context("dashboard"))


@admin_bp.route("/settings", methods=["GET", "POST"])
@require_admin
def admin_settings():
    admin = current_admin()
    success = None
    error = None
    if request.method == "POST":
        setting_key = (request.form.get("setting_key") or "homepage_controls").strip()
        raw_value = request.form.get("setting_value") or "{}"
        try:
            parsed = json.loads(raw_value)
            set_site_setting(setting_key, parsed, admin_id=admin["id"])
            log_admin_action(admin["id"], "update_setting", "site_setting", setting_key, {"setting_key": setting_key})
            success = f"{setting_key} saved."
        except json.JSONDecodeError:
            error = "Setting value must be valid JSON."
    return render_template("admin/settings.html", success=success, error=error, **_dashboard_context("settings"))


@admin_bp.route("/users")
@require_admin
def admin_users():
    return render_template("admin/dashboard.html", **_dashboard_context("users"))


@admin_bp.route("/content")
@require_admin
def admin_content():
    return render_template("admin/dashboard.html", **_dashboard_context("content"))


@admin_bp.route("/audit")
@require_admin
def admin_audit():
    context = _dashboard_context("audit")
    context["audit_rows"], context["status_filter"], context["query_filter"] = _filter_rows(context["audit_rows"], "action")
    return render_template("admin/audit.html", **context)


@admin_bp.route("/topups")
@require_admin
def admin_topups():
    context = _dashboard_context("topups")
    context["topups"], context["status_filter"], context["query_filter"] = _filter_rows(context["topups"], "status")
    return render_template("admin/topups.html", **context)


@admin_bp.route("/topups/<topup_id>/approve", methods=["POST"])
@require_admin
def approve_topup_route(topup_id):
    admin = current_admin()
    ok, result = approve_topup_action(admin["id"], topup_id)
    return redirect("/admin/topups")


@admin_bp.route("/topups/<topup_id>/reject", methods=["POST"])
@require_admin
def reject_topup_route(topup_id):
    admin = current_admin()
    reject_topup(admin["id"], topup_id, request.form.get("reason") or "Rejected by admin.")
    return redirect("/admin/topups")


@admin_bp.route("/withdrawals")
@require_admin
def admin_withdrawals():
    context = _dashboard_context("withdrawals")
    context["withdrawals"], context["status_filter"], context["query_filter"] = _filter_rows(context["withdrawals"], "status")
    return render_template("admin/withdrawals.html", **context)


@admin_bp.route("/withdrawals/<withdrawal_id>/approve", methods=["POST"])
@require_admin
def approve_withdrawal_route(withdrawal_id):
    admin = current_admin()
    ok, result = approve_withdrawal_action(admin["id"], withdrawal_id)
    return redirect("/admin/withdrawals")


@admin_bp.route("/withdrawals/<withdrawal_id>/reject", methods=["POST"])
@require_admin
def reject_withdrawal_route(withdrawal_id):
    admin = current_admin()
    reject_withdrawal(admin["id"], withdrawal_id, request.form.get("reason") or "Rejected by admin.")
    return redirect("/admin/withdrawals")


@admin_bp.route("/withdrawals/<withdrawal_id>/execute", methods=["POST"])
@require_admin
def execute_withdrawal_route(withdrawal_id):
    admin = current_admin()
    execute_withdrawal(admin["id"], withdrawal_id, request.form.get("payout_reference") or "CHAIN-PAYOUT")
    return redirect("/admin/withdrawals")


@admin_bp.route("/marketplace")
@require_admin
def admin_marketplace():
    context = _dashboard_context("marketplace")
    context["marketplace_items"], context["status_filter"], context["query_filter"] = _filter_rows(context["marketplace_items"], "approval_status", ["approval_status", "moderation_status"])
    return render_template("admin/marketplace.html", **context)


@admin_bp.route("/marketplace/<item_id>/approve", methods=["POST"])
@require_admin
def approve_marketplace_route(item_id):
    admin = current_admin()
    ok, result = approve_marketplace_item_action(admin["id"], item_id)
    return redirect("/admin/marketplace")


@admin_bp.route("/marketplace/<item_id>/reject", methods=["POST"])
@require_admin
def reject_marketplace_route(item_id):
    admin = current_admin()
    reject_marketplace_item(admin["id"], item_id, request.form.get("reason") or "Rejected by admin.")
    return redirect("/admin/marketplace")


@admin_bp.route("/marketplace/<item_id>/feature", methods=["POST"])
@require_admin
def feature_marketplace_route(item_id):
    admin = current_admin()
    feature_marketplace_item(admin["id"], item_id)
    return redirect("/admin/marketplace")


@admin_bp.route("/marketplace/<item_id>/unfeature", methods=["POST"])
@require_admin
def unfeature_marketplace_route(item_id):
    admin = current_admin()
    unfeature_marketplace_item(admin["id"], item_id)
    return redirect("/admin/marketplace")


@admin_bp.route("/verifications")
@require_admin
def admin_verifications():
    context = _dashboard_context("verifications")
    context["verifications"], context["status_filter"], context["query_filter"] = _filter_rows(context["verifications"], "verification_status")
    return render_template("admin/verifications.html", **context)


@admin_bp.route("/verifications/<verification_id>/approve", methods=["POST"])
@require_admin
def approve_verification_route(verification_id):
    admin = current_admin()
    ok, result = approve_verification_action(admin["id"], verification_id)
    return redirect("/admin/verifications")


@admin_bp.route("/verifications/<verification_id>/reject", methods=["POST"])
@require_admin
def reject_verification_route(verification_id):
    admin = current_admin()
    reject_verification(admin["id"], verification_id, request.form.get("reason") or "Rejected by admin.")
    return redirect("/admin/verifications")


developer_bp = Blueprint("developer", __name__)


@developer_bp.route("/developer")
def developer_root():
    if not session.get("admin_id"):
        return redirect("/admin/login?next=/developer/dashboard")
    return redirect("/developer/dashboard")


@developer_bp.route("/developer/dashboard")
@require_master_admin
def developer_dashboard():
    return render_template("admin/developer_dashboard.html", **_dashboard_context("developer"))

@admin_bp.route("/moderation")
@require_admin
def admin_moderation():
    from services.neon_service import fast_query
    context = _dashboard_context("moderation")
    
    reports = fast_query("""
        SELECT r.*, reporter.username as reporter_username, target.username as target_username
        FROM chain_reports r
        LEFT JOIN chain_profiles reporter ON r.reporter_profile_id = reporter.id
        LEFT JOIN chain_profiles target ON r.target_profile_id = target.id
        ORDER BY r.created_at DESC LIMIT 50
    """)
    
    spam_reports = fast_query("""
        SELECT r.*, reporter.username as reporter_username, target.username as target_username
        FROM chain_spam_reports r
        LEFT JOIN chain_profiles reporter ON r.reporter_profile_id = reporter.id
        LEFT JOIN chain_profiles target ON r.target_profile_id = target.id
        ORDER BY r.created_at DESC LIMIT 50
    """)
    
    fake_accounts = fast_query("SELECT id, username, full_name, trust_score, last_ip FROM chain_profiles WHERE is_fake = TRUE LIMIT 20")
    
    return render_template(
        "admin/moderation.html",
        **context,
        reports=reports,
        spam_reports=spam_reports,
        fake_accounts=fake_accounts
    )

@admin_bp.route("/moderation/action", methods=["POST"])
@require_admin
def admin_moderation_action():
    from services.neon_service import write_query
    admin = current_admin()
    target_id = request.form.get("target_id")
    target_type = request.form.get("target_type")
    action = request.form.get("action")
    reason = request.form.get("reason")
    
    log_admin_action(admin["id"], f"moderation_{action}", target_type, target_id, {"reason": reason})
    
    if target_type == "user":
        if action == "suspend":
            write_query("UPDATE chain_profiles SET deleted_at = now() WHERE id = %s", (target_id,))
        elif action == "restrict":
            write_query("UPDATE chain_profiles SET trust_score = 0.1 WHERE id = %s", (target_id,))
        elif action == "warn":
            # Placeholder for sending a warning notification
            pass
            
    report_id = request.form.get("report_id")
    if report_id:
        write_query("UPDATE chain_reports SET status = 'resolved' WHERE id = %s", (report_id,))
        write_query("UPDATE chain_spam_reports SET status = 'resolved' WHERE id = %s", (report_id,))

    return redirect("/admin/moderation")

@admin_bp.route("/verification")
@require_admin
def admin_verification():
    from services.verification_engine import list_pending_verifications
    pending = list_pending_verifications()
    context = _dashboard_context("verification")
    return render_template("admin/verifications.html", **context, pending=pending)

@admin_bp.route("/verification/action", methods=["POST"])
@require_admin
def admin_verification_action():
    from services.verification_engine import update_verification_status
    admin = current_admin()
    request_id = request.form.get("request_id")
    status = request.form.get("status") # approved / rejected
    notes = request.form.get("notes")
    
    update_verification_status(request_id, status, reviewer_profile_id=admin["id"], notes=notes)
    flash(f"Verification {status}", "success")
    return redirect(url_for("admin.admin_verification"))

@admin_bp.route("/security")
@require_admin
def admin_security():
    from services.neon_service import fast_query
    context = _dashboard_context("security")
    
    anomalies = fast_query("""
        SELECT h.*, p.username 
        FROM chain_login_history h
        JOIN chain_profiles p ON h.profile_id = p.id
        WHERE is_anomaly = TRUE
        ORDER BY h.created_at DESC LIMIT 50
    """)
    
    ip_reputation = fast_query("SELECT * FROM chain_ip_reputation ORDER BY last_seen_at DESC LIMIT 50")
    
    return render_template("admin/security.html", **context, anomalies=anomalies, ip_reputation=ip_reputation)

@admin_bp.route("/observability")
@require_admin
def admin_observability():
    from services.neon_service import fast_query
    context = _dashboard_context("observability")
    
    slow_queries = fast_query("""
        SELECT request_path, method, status_code, latency_ms, created_at
        FROM chain_performance_logs
        WHERE latency_ms > 1000
        ORDER BY latency_ms DESC LIMIT 50
    """)
    
    avg_latency = fast_query("SELECT request_path, AVG(latency_ms) as avg_ms, COUNT(*) as count FROM chain_performance_logs GROUP BY request_path ORDER BY avg_ms DESC LIMIT 20")
    
    return render_template("admin/observability.html", **context, slow_queries=slow_queries, avg_latency=avg_latency)


@admin_bp.route("/performance")
@require_admin
def admin_performance():
    from services.homepage_cache_service import cache_status
    from services.query_optimizer import get_performance_summary
    context = _dashboard_context("performance")
    return render_template(
        "admin/performance.html",
        **context,
        cache_status=cache_status(),
        summary=get_performance_summary(),
    )
