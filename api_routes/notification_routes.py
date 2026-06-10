import time

from flask import Blueprint, jsonify, render_template, session, redirect, request
from services.notification_center_service import (
    create_notification, list_notifications, unread_count,
    mark_read, mark_all_read, delete_notification, delete_selected,
    get_preferences, update_preferences, mute_type,
)
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile

notification_engine_bp = Blueprint("notification_engine", __name__)
_LOGGED_OUT_UNREAD_CACHE = {"expires_at": 0.0, "payload": {"count": 0}}

_TABS = [
    {"key": "all", "label": "All"},
    {"key": "unread", "label": "Unread"},
    {"key": "mentions", "label": "Mentions"},
    {"key": "messages", "label": "Messages"},
    {"key": "activity", "label": "Activity"},
    {"key": "system", "label": "System"},
]

@notification_engine_bp.route("/notifications/")
@login_required
def index():
    profile = get_current_profile()
    return render_template("notifications/index.html", profile=profile, tabs=_TABS)

@notification_engine_bp.route("/api/notifications")
@login_required
def api_list():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    tab = request.args.get("tab", "all")
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 30, type=int)
    try:
        items, has_more = list_notifications(profile_id, tab=tab, page=page, limit=limit)
        return jsonify({
            "ok": True,
            "tab": tab,
            "items": items,
            "page": page,
            "has_more": has_more,
            "next_page": page + 1 if has_more else None,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@notification_engine_bp.route("/api/notifications/unread-count")
def api_unread_count():
    if "auth_user_id" not in session:
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
    response.headers["Cache-Control"] = "public, max-age=10, stale-while-revalidate=30"
    return response, 200

@notification_engine_bp.route("/api/notifications/<notification_id>/read", methods=["POST"])
@login_required
def api_mark_read(notification_id):
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "Profile setup incomplete"}), 400
    ok = mark_read(profile_id, notification_id)
    return jsonify({"ok": ok}), 200 if ok else 500

@notification_engine_bp.route("/api/notifications/read-all", methods=["POST"])
@login_required
def api_mark_all_read():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "Profile setup incomplete"}), 400
    ok = mark_all_read(profile_id)
    return jsonify({"ok": ok}), 200 if ok else 500

@notification_engine_bp.route("/api/notifications/<notification_id>/delete", methods=["POST"])
@login_required
def api_delete(notification_id):
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "Profile setup incomplete"}), 400
    ok = delete_notification(profile_id, notification_id)
    return jsonify({"ok": ok}), 200 if ok else 500

@notification_engine_bp.route("/api/notifications/delete-selected", methods=["POST"])
@login_required
def api_delete_selected():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "Profile setup incomplete"}), 400
    data = request.json or {}
    ids = data.get("ids", [])
    if not ids:
        return jsonify({"ok": False, "error": "no_ids_provided"}), 400
    ok = delete_selected(profile_id, ids)
    return jsonify({"ok": ok}), 200 if ok else 500

@notification_engine_bp.route("/api/notifications/preferences", methods=["GET"])
@login_required
def api_get_preferences():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    prefs = get_preferences(profile_id)
    return jsonify({"ok": True, "preferences": prefs}), 200

@notification_engine_bp.route("/api/notifications/preferences", methods=["POST"])
@login_required
def api_set_preferences():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    data = request.json or {}
    ok = update_preferences(profile_id, data)
    return jsonify({"ok": ok}), 200 if ok else 500

@notification_engine_bp.route("/api/notifications/mute-type", methods=["POST"])
@login_required
def api_mute_type():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "Profile setup incomplete"}), 400
    data = request.json or {}
    event_type = data.get("event_type")
    muted = data.get("muted", True)
    if not event_type:
        return jsonify({"ok": False, "error": "event_type_required"}), 400
    ok = mute_type(profile_id, event_type, muted=muted)
    return jsonify({"ok": ok}), 200 if ok else 500
