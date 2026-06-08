from flask import Blueprint, request, jsonify
from services.profile_service import get_current_profile
from services.security_service import get_privacy_settings, upsert_privacy_settings
from api_routes.profile_routes import login_required

privacy_api_bp = Blueprint("privacy_api", __name__, url_prefix="/privacy")


@privacy_api_bp.route("/api/settings")
@login_required
def api_get_settings():
    profile = get_current_profile()
    settings = get_privacy_settings(profile["id"])
    return jsonify({"ok": True, "settings": settings})


@privacy_api_bp.route("/api/settings", methods=["POST"])
@login_required
def api_update_settings():
    profile = get_current_profile()
    data = request.json or {}
    bool_keys = [
        "show_online_status", "show_last_seen", "show_read_receipts",
        "show_typing_indicator", "show_profile_photo", "allow_calls", "allow_group_invites",
    ]
    settings = {}
    for key in bool_keys:
        if key in data:
            settings[key] = bool(data[key])
    upsert_privacy_settings(profile["id"], settings)
    updated = get_privacy_settings(profile["id"])
    return jsonify({"ok": True, "settings": updated})
