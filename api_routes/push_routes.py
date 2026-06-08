import json
from flask import Blueprint, jsonify, request, session
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.push_notification_service import (
    get_preferences,
    get_vapid_public_key,
    remove_subscription,
    save_subscription,
    update_preferences,
)
from services.request_cache import request_get, request_set

push_bp = Blueprint("push", __name__, url_prefix="/push")


@push_bp.route("/vapid-public-key")
@login_required
def vapid_public_key():
    key = get_vapid_public_key()
    if not key:
        return jsonify({"error": "VAPID keys not configured", "available": False}), 200
    return jsonify({"publicKey": key, "available": True}), 200


@push_bp.route("/subscribe", methods=["POST"])
@login_required
def subscribe():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"error": "Profile not found"}), 400
    data = request.json or {}
    endpoint = data.get("endpoint") or (data.get("subscription") or {}).get("endpoint")
    keys = data.get("keys") or (data.get("subscription") or {}).get("keys") or {}
    if not endpoint:
        return jsonify({"error": "Missing endpoint"}), 400
    result = save_subscription(
        profile_id=profile["id"],
        endpoint=endpoint,
        p256dh=keys.get("p256dh", ""),
        auth_key=keys.get("auth", ""),
        user_agent=request.headers.get("User-Agent", ""),
        device_type="web",
    )
    if result.get("ok"):
        return jsonify({"ok": True}), 200
    return jsonify({"error": result.get("error", "save_failed")}), 500


@push_bp.route("/unsubscribe", methods=["POST"])
@login_required
def unsubscribe():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"error": "Profile not found"}), 400
    data = request.json or {}
    endpoint = data.get("endpoint") or (data.get("subscription") or {}).get("endpoint") or ""
    result = remove_subscription(profile["id"], endpoint)
    if result.get("ok"):
        return jsonify({"ok": True}), 200
    return jsonify({"error": result.get("error", "remove_failed")}), 500


@push_bp.route("/preferences", methods=["GET"])
@login_required
def preferences_get():
    profile_id = (get_current_profile() or {}).get("id") or session.get("profile_id")
    if not profile_id:
        return jsonify({"error": "Profile not found"}), 400
    prefs = get_preferences(profile_id)
    return jsonify(prefs), 200


@push_bp.route("/preferences", methods=["POST"])
@login_required
def preferences_set():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"error": "Profile not found"}), 400
    data = request.json or {}
    result = update_preferences(profile["id"], data)
    if result.get("ok"):
        return jsonify({"ok": True}), 200
    return jsonify({"error": result.get("error", "update_failed")}), 500


@push_bp.route("/settings")
@login_required
def settings_page():
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or session.get("profile_id")
    prefs = get_preferences(profile_id) if profile_id else {}
    return jsonify({"profile": profile, "preferences": prefs}), 200
