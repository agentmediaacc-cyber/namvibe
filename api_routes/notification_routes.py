import time

from flask import Blueprint, jsonify, render_template, session, redirect, request
from services.notification_engine import list_notifications, unread_count, mark_read, mark_all_read
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile

notification_engine_bp = Blueprint("notification_engine", __name__)
_LOGGED_OUT_UNREAD_CACHE = {"expires_at": 0.0, "payload": {"count": 0}}

@notification_engine_bp.route("/notifications/")
@login_required
def index():
    profile = get_current_profile()
    notifications = list_notifications(profile['id']) if profile and profile.get("id") else []
    return render_template("notifications/index.html", notifications=notifications, profile=profile, setup_warning=bool(session.get("profile_warning")))

@notification_engine_bp.route("/api/notifications/unread-count")
def api_unread_count():
    if 'auth_user_id' not in session:
        now = time.monotonic()
        if _LOGGED_OUT_UNREAD_CACHE["expires_at"] <= now:
            _LOGGED_OUT_UNREAD_CACHE["payload"] = {"count": 0}
            _LOGGED_OUT_UNREAD_CACHE["expires_at"] = now + 60
        return jsonify(_LOGGED_OUT_UNREAD_CACHE["payload"]), 200

    profile_id = session.get("profile_id")
    if not profile_id:
        return jsonify({"count": 0}), 200

    try:
        count = unread_count(profile_id)
    except Exception:
        count = 0

    response = jsonify({"count": count})
    # Instruct clients/proxies to cache for 10 seconds to debounce polling
    response.headers["Cache-Control"] = "public, max-age=10, stale-while-revalidate=30"
    return response, 200

@notification_engine_bp.route("/api/notifications/<notification_id>/read", methods=["POST"])
@login_required
def api_mark_read(notification_id):
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"success": False, "error": "Profile setup incomplete"}), 400
    mark_read(notification_id, profile_id)
    return jsonify({"success": True}), 200

@notification_engine_bp.route("/api/notifications/read-all", methods=["POST"])
@login_required
def api_mark_all_read():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"success": False, "error": "Profile setup incomplete"}), 400
    mark_all_read(profile_id)
    return jsonify({"success": True}), 200
