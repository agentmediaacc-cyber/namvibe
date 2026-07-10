import time
from datetime import datetime, timezone

from flask import Blueprint, jsonify, redirect, render_template, request, session, current_app
from flask_wtf.csrf import generate_csrf

from services.founder_auth_service import (
    authenticate_founder,
    current_founder,
    login_founder_session,
    logout_founder_session,
    require_founder,
    update_founder_password,
    update_founder_profile,
)
from services.logging_service import log_info
from services.founder_dashboard_service import (
    get_all_users,
    get_coin_summary,
    get_content_stats,
    get_finance_summary,
    get_moderation_queue,
    get_overview_stats,
    get_payout_requests,
    get_recent_messages,
    get_recent_transactions,
    get_security_events,
    get_support_tickets,
    get_system_health,
    get_user_detail,
    get_user_growth,
    search_users,
)

founder_bp = Blueprint("founder", __name__, url_prefix="/system")


@founder_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("founder_id"):
        return redirect("/system/")
    error = None
    if request.method == "POST":
        # Rate limit: max 5 login attempts per IP per minute
        ip = request.remote_addr or "unknown"
        rate_key = f"founder_login:{ip}"
        attempts = session.get(rate_key, 0) + 1
        session[rate_key] = attempts
        session.modified = True
        if attempts > 5:
            log_info("founder_login_rate_limited", ip=ip)
            return render_template("founder/login.html", error="Too many login attempts. Please try again later.", now=datetime.now(timezone.utc).year), 429
        ok, result = authenticate_founder(
            request.form.get("username"), request.form.get("password")
        )
        if ok:
            # Clear rate limit on success
            session.pop(rate_key, None)
            session.pop("founder_login_count", None)
            login_founder_session(result)
            return redirect("/system/setup" if result.get("must_change_password") else "/system/")
        error = result
    else:
        # Reset rate limit on GET (fresh page load)
        for key in list(session.keys()):
            if key.startswith("founder_login:"):
                session.pop(key, None)
    return render_template("founder/login.html", error=error, now=datetime.now(timezone.utc).year)


@founder_bp.route("/logout", methods=["POST"])
def logout():
    logout_founder_session()
    return redirect("/system/login")


@founder_bp.route("/setup", methods=["GET", "POST"])
def setup():
    founder = current_founder()
    if not founder:
        return redirect("/system/login")
    error = None
    success = None
    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if new_password != confirm:
            error = "Passwords do not match."
        elif len(new_password) < 8:
            error = "Password must be at least 8 characters."
        else:
            ok, msg = update_founder_password(founder["id"], new_password)
            if ok:
                update_founder_profile(founder["id"], {
                    "full_name": request.form.get("full_name", ""),
                    "email": request.form.get("email", ""),
                    "phone": request.form.get("phone", ""),
                })
                session["founder_must_change"] = False
                return redirect("/system/")
            error = msg
    return render_template("founder/setup.html", founder=founder, error=error, now=datetime.now(timezone.utc).year)


@founder_bp.route("/")
@require_founder
def dashboard():
    founder = current_founder()
    try:
        stats = get_overview_stats()
    except Exception:
        stats = {}
    try:
        finance = get_finance_summary()
    except Exception:
        finance = {}
    try:
        coins = get_coin_summary()
    except Exception:
        coins = {}
    try:
        content = get_content_stats()
    except Exception:
        content = {}
    return render_template(
        "founder/dashboard.html",
        founder=founder,
        stats=stats,
        finance=finance,
        coins=coins,
        content=content,
        now=datetime.now(timezone.utc).year,
        section="overview",
    )


# ── API Endpoints ─────────────────────────────────────────────────────

@founder_bp.route("/api/stats")
@require_founder
def api_stats():
    return jsonify(get_overview_stats())


@founder_bp.route("/api/user-growth")
@require_founder
def api_user_growth():
    days = request.args.get("days", 30, type=int)
    return jsonify(get_user_growth(days))


@founder_bp.route("/api/users")
@require_founder
def api_users():
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    q = request.args.get("q", "").strip()
    if q:
        return jsonify(search_users(q, limit))
    return jsonify(get_all_users(limit, offset))


@founder_bp.route("/api/users/<int:profile_id>")
@require_founder
def api_user_detail(profile_id):
    return jsonify(get_user_detail(profile_id) or {})


@founder_bp.route("/api/finance")
@require_founder
def api_finance():
    return jsonify({
        **get_finance_summary(),
        "transactions": get_recent_transactions(50),
        "payouts": get_payout_requests(),
    })


@founder_bp.route("/api/coins")
@require_founder
def api_coins():
    return jsonify(get_coin_summary())


@founder_bp.route("/api/content")
@require_founder
def api_content():
    return jsonify(get_content_stats())


@founder_bp.route("/api/moderation")
@require_founder
def api_moderation():
    return jsonify(get_moderation_queue())


@founder_bp.route("/api/support")
@require_founder
def api_support():
    return jsonify(get_support_tickets())


@founder_bp.route("/api/health")
@require_founder
def api_health():
    return jsonify(get_system_health())


@founder_bp.route("/api/security")
@require_founder
def api_security():
    return jsonify(get_security_events(100))


@founder_bp.route("/api/messages")
@require_founder
def api_messages():
    return jsonify(get_recent_messages(50))


@founder_bp.route("/api/profile", methods=["POST"])
@require_founder
def api_update_profile():
    founder = current_founder()
    data = {
        "full_name": request.form.get("full_name", ""),
        "email": request.form.get("email", ""),
        "phone": request.form.get("phone", ""),
    }
    update_founder_profile(founder["id"], data)
    return jsonify({"ok": True})


@founder_bp.route("/api/change-password", methods=["POST"])
@require_founder
def api_change_password():
    founder = current_founder()
    current_pw = request.form.get("current_password", "")
    new_pw = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")

    from services.founder_auth_service import verify_password
    if not verify_password(current_pw, founder.get("password_hash")):
        return jsonify({"ok": False, "error": "Current password is incorrect."}), 400
    if new_pw != confirm:
        return jsonify({"ok": False, "error": "Passwords do not match."}), 400
    if len(new_pw) < 8:
        return jsonify({"ok": False, "error": "Password must be at least 8 characters."}), 400

    ok, msg = update_founder_password(founder["id"], new_pw)
    if ok:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": msg}), 400


# ── Verification Admin ──────────────────────────────────────────────────

@founder_bp.route("/api/verifications")
@require_founder
def api_verifications():
    from services.verification_service import list_all_verifications, get_dashboard_stats
    status_filter = request.args.get("status", "pending,needs_review")
    if "," in status_filter:
        status_list = [s.strip() for s in status_filter.split(",")]
        all_reqs = []
        for s in status_list:
            all_reqs.extend(list_all_verifications(limit=200, status=s))
        all_reqs = sorted(all_reqs, key=lambda r: r.get("created_at") or "", reverse=True)[:100]
    else:
        all_reqs = list_all_verifications(limit=200, status=status_filter) if status_filter else list_all_verifications(limit=200)
    stats = get_dashboard_stats()
    return jsonify({"ok": True, "verifications": all_reqs, "stats": stats})


@founder_bp.route("/api/verifications/<request_id>/approve", methods=["POST"])
@require_founder
def api_verification_approve(request_id):
    from services.verification_service import approve_verification
    founder = current_founder()
    data = request.get_json(silent=True) or {}
    result = approve_verification(request_id, founder["id"], notes=data.get("notes"))
    return jsonify(result)


@founder_bp.route("/api/verifications/<request_id>/reject", methods=["POST"])
@require_founder
def api_verification_reject(request_id):
    from services.verification_service import reject_verification
    founder = current_founder()
    data = request.get_json(silent=True) or {}
    result = reject_verification(request_id, founder["id"], reason=data.get("reason"))
    return jsonify(result)


@founder_bp.route("/api/verifications/<request_id>/request-info", methods=["POST"])
@require_founder
def api_verification_request_info(request_id):
    from services.verification_service import request_more_info
    founder = current_founder()
    data = request.get_json(silent=True) or {}
    result = request_more_info(request_id, founder["id"], notes=data.get("notes"))
    return jsonify(result)


@founder_bp.route("/api/verifications/<request_id>/suspend", methods=["POST"])
@require_founder
def api_verification_suspend(request_id):
    from services.verification_service import suspend_verification
    founder = current_founder()
    data = request.get_json(silent=True) or {}
    result = suspend_verification(request_id, founder["id"], reason=data.get("reason"))
    return jsonify(result)
