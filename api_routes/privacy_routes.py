from flask import Blueprint, request, jsonify
from services.profile_service import get_current_profile, get_profile_privacy, update_profile_privacy
from services.security_service import get_privacy_settings, upsert_privacy_settings
from api_routes.profile_routes import login_required

privacy_api_bp = Blueprint("privacy_api", __name__, url_prefix="/privacy")


@privacy_api_bp.route("/api/settings")
@login_required
def api_get_settings():
    profile = get_current_profile()
    settings = get_privacy_settings(profile["id"])
    rel_privacy = get_profile_privacy(profile["id"])
    settings.update(rel_privacy)
    return jsonify({"ok": True, "settings": settings})


@privacy_api_bp.route("/api/settings", methods=["POST"])
@login_required
def api_update_settings():
    profile = get_current_profile()
    data = request.json or {}
    
    # Separate general settings from relationship privacy settings
    bool_keys = [
        "show_online_status", "show_last_seen", "show_read_receipts",
        "show_typing_indicator", "show_profile_photo", "allow_calls", "allow_group_invites",
    ]
    
    rel_keys = [
        "profile_visibility", "who_can_see_posts", "who_can_see_reels", "who_can_see_stories",
        "who_can_see_followers", "who_can_see_following", "who_can_send_friend_requests",
        "who_can_follow_me", "who_can_message_me"
    ]

    settings = {}
    for key in bool_keys:
        if key in data:
            settings[key] = bool(data[key])
    
    if settings:
        upsert_privacy_settings(profile["id"], settings)
    
    rel_payload = {}
    for key in rel_keys:
        if key in data:
            rel_payload[key] = str(data[key])
    
    if rel_payload:
        update_profile_privacy(profile["id"], rel_payload)
        
    updated = get_privacy_settings(profile["id"])
    updated.update(get_profile_privacy(profile["id"]))
    
    return jsonify({"ok": True, "settings": updated})
