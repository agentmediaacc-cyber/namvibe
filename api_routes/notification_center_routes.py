import time
from flask import Blueprint, jsonify, render_template, session, request
from services.notification_engine import (
    list_notifications_tab, unread_count, mark_read, mark_all_read,
    delete_notification, delete_selected_notifications, mute_notification_type,
    get_notification_preferences, update_notification_preferences,
)
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile

notification_center_bp = Blueprint("notification_center", __name__)
_LOGGED_OUT_UNREAD_CACHE = {"expires_at": 0.0, "payload": {"count": 0}}

_TABS_CONFIG = [
    {"key": "unread", "label": "Unread", "icon": "fa-bell"},
    {"key": "all", "label": "All", "icon": "fa-list"},
    {"key": "mentions", "label": "Mentions", "icon": "fa-at"},
    {"key": "messages", "label": "Messages", "icon": "fa-envelope"},
    {"key": "activity", "label": "Activity", "icon": "fa-chart-line"},
    {"key": "system", "label": "System", "icon": "fa-shield-alt"},
]

@notification_center_bp.route("/notifications/center")
@login_required
def index():
    profile = get_current_profile()
    tabs = _TABS_CONFIG
    return render_template(
        "notifications/center.html",
        profile=profile,
        tabs=tabs,
    )

@notification_center_bp.route("/api/notifications/center/list")
@login_required
def api_list():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    tab = request.args.get("tab", "all")
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 20, type=int)
    limit = min(limit, 50)
    try:
        items, has_more = list_notifications_tab(profile_id, tab=tab, page=page, limit=limit)
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

@notification_center_bp.route("/api/notifications/center/unread-count")
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
    return jsonify({"count": count}), 200

@notification_center_bp.route("/api/notifications/center/read/<notification_id>", methods=["POST"])
@login_required
def api_mark_read(notification_id):
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "Profile setup incomplete"}), 400
    mark_read(notification_id, profile_id)
    return jsonify({"ok": True}), 200

@notification_center_bp.route("/api/notifications/center/read-all", methods=["POST"])
@login_required
def api_mark_all_read():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "Profile setup incomplete"}), 400
    mark_all_read(profile_id)
    return jsonify({"ok": True}), 200

@notification_center_bp.route("/api/notifications/center/delete/<notification_id>", methods=["POST"])
@login_required
def api_delete(notification_id):
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "Profile setup incomplete"}), 400
    ok = delete_notification(notification_id, profile_id)
    return jsonify({"ok": ok}), 200 if ok else 500

@notification_center_bp.route("/api/notifications/center/delete-selected", methods=["POST"])
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
    ok = delete_selected_notifications(ids, profile_id)
    return jsonify({"ok": ok}), 200 if ok else 500

@notification_center_bp.route("/api/notifications/center/mute-type", methods=["POST"])
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
    ok = mute_notification_type(profile_id, event_type, muted=muted)
    return jsonify({"ok": ok}), 200 if ok else 500

@notification_center_bp.route("/api/notifications/center/preferences", methods=["GET"])
@login_required
def api_get_preferences():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    prefs = get_notification_preferences(profile_id)
    return jsonify({"ok": True, "preferences": prefs}), 200

@notification_center_bp.route("/api/notifications/center/preferences", methods=["POST"])
@login_required
def api_set_preferences():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    data = request.json or {}
    ok = update_notification_preferences(profile_id, data)
    return jsonify({"ok": ok}), 200 if ok else 500

@notification_center_bp.route("/api/notifications/center/tabs-config")
def api_tabs_config():
    return jsonify({"ok": True, "tabs": _TABS_CONFIG})
