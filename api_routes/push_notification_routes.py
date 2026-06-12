import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, session

from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile, get_lightweight_profile
from engines.cache_engine import cache_key, get_cache, set_cache
from services.logging_service import log_info
from services.push_notification_service import (
    get_preferences,
    get_vapid_public_key,
    remove_subscription,
    save_subscription,
    update_preferences,
    send_push_notification,
    send_message_notification,
    send_call_notification,
    send_missed_call_notification,
    send_security_notification,
    send_group_call_invite,
)
from services.push_token_service import register_push_token, remove_push_token, get_push_tokens
from services.notification_queue_service import get_notification_history
from services.request_cache import request_get, request_set

push_notifications_api_bp = Blueprint("push_notifications_api", __name__, url_prefix="/notifications")


@push_notifications_api_bp.route("/api/register-token", methods=["POST"])
@login_required
def api_register_token():
    profile_id = session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    data = request.json or {}
    token = data.get("token")
    platform = data.get("platform", "web")
    if not token:
        return jsonify({"ok": False, "error": "token_required"}), 400
    result = register_push_token(profile_id, token, platform=platform)
    if result.get("ok"):
        return jsonify({"ok": True}), 200
    return jsonify({"ok": False, "error": result.get("error", "register_failed")}), 500


@push_notifications_api_bp.route("/api/remove-token", methods=["POST"])
@login_required
def api_remove_token():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    data = request.json or {}
    token = data.get("token")
    if not token:
        return jsonify({"ok": False, "error": "token_required"}), 400
    result = remove_push_token(profile["id"], token)
    if result.get("ok"):
        return jsonify({"ok": True}), 200
    return jsonify({"ok": False, "error": result.get("error", "remove_failed")}), 500


@push_notifications_api_bp.route("/api/tokens", methods=["GET"])
@login_required
def api_get_tokens():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    tokens = get_push_tokens(profile["id"])
    return jsonify({"ok": True, "tokens": tokens}), 200


@push_notifications_api_bp.route("/api/test", methods=["POST"])
@login_required
def api_test_notification():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    data = request.json or {}
    title = data.get("title", "Test Notification")
    body = data.get("body", "This is a test notification from NamVibe")
    result = send_push_notification(profile["id"], title, body, {"test": True})
    if result.get("ok"):
        return jsonify({"ok": True, "message": "Test notification queued"}), 200
    return jsonify({"ok": False, "error": result.get("error", "send_failed")}), 500


@push_notifications_api_bp.route("/api/history", methods=["GET"])
@login_required
def api_notification_history():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    limit = request.args.get("limit", 50, type=int)
    history = get_notification_history(profile["id"], limit=min(limit, 200))
    return jsonify({"ok": True, "history": history}), 200


@push_notifications_api_bp.route("/api/unread-count", methods=["GET"])
@login_required
def api_unread_count():
    profile_id = session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    cached = get_cache(cache_key("unread_count_notif", profile_id))
    if cached is not None:
        return jsonify({"ok": True, "unread_count": cached}), 200
    try:
        from services.neon_service import fast_query
        rows = fast_query(
            "SELECT COUNT(*) AS cnt FROM chain_notification_queue WHERE profile_id = %s AND status = 'pending'",
            (profile_id,),
            default=[{"cnt": 0}],
        )
        count = rows[0]["cnt"] if rows else 0
        set_cache(cache_key("unread_count_notif", profile_id), count, ttl=30)
        return jsonify({"ok": True, "unread_count": count}), 200
    except Exception:
        return jsonify({"ok": True, "unread_count": 0}), 200


@push_notifications_api_bp.route("/api/mark-read", methods=["POST"])
@login_required
def api_mark_read():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    data = request.json or {}
    notification_id = data.get("notification_id")
    if notification_id:
        try:
            from services.neon_service import write_query
            write_query(
                "UPDATE chain_notification_queue SET status = 'read' WHERE id = %s AND profile_id = %s",
                (notification_id, profile["id"]),
            )
        except Exception:
            pass
    return jsonify({"ok": True}), 200


@push_notifications_api_bp.route("/api/vapid-public-key")
def api_vapid_public_key():
    key = get_vapid_public_key()
    return jsonify({"publicKey": key, "available": bool(key)}), 200


@push_notifications_api_bp.route("/api/preferences", methods=["GET"])
@login_required
def api_get_preferences():
    profile_id = (get_current_profile() or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    prefs = get_preferences(profile_id)
    return jsonify({"ok": True, "preferences": prefs}), 200


@push_notifications_api_bp.route("/api/preferences", methods=["POST"])
@login_required
def api_set_preferences():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "profile_not_found"}), 400
    data = request.json or {}
    result = update_preferences(profile["id"], data)
    if result.get("ok"):
        return jsonify({"ok": True}), 200
    return jsonify({"ok": False, "error": result.get("error", "update_failed")}), 500
