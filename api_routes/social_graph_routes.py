"""Social Graph Routes — Phase 158D enhanced social features."""
import json
from flask import Blueprint, jsonify, request, session, render_template, redirect, url_for, flash
from api_routes.profile_routes import login_required, invalidate_profile_cache
from services.profile_service import get_current_profile, get_profile_by_username, get_profile_by_id
from services.social_service import list_followers, list_following
from services.friend_service import (
    send_friend_request, accept_friend_request, decline_friend_request,
    cancel_friend_request, remove_friend, list_friends, list_friend_requests,
    get_mutual_friends, suggest_friends, are_friends
)
from services.notification_engine import create_notification
from services.relationship_cache_service import get_relationship_state
from services.profile_completion_service import get_completion, update_completion_percentage
from services.profile_sharing_service import get_share_data
from services.subscriber_content_service import can_access_content, check_media_access, get_locked_content, set_media_access_level
from services.business_page_service import (get_business_profile, update_business_profile, create_campaign,
                                            get_campaigns, pause_campaign, get_all_campaigns)
from services.verification_request_service import (submit_verification, get_verification_status,
                                                    get_pending_verifications, get_verification_detail,
                                                    approve_verification, reject_verification)
from services.trust_scam_service import get_trust_summary, add_signal
from services.location_privacy_service import (get_location_settings, start_sharing, stop_sharing,
                                                update_location, is_authorized_viewer)
from services.security_service import (get_device_sessions, revoke_device_session, logout_all_other_devices,
                                       get_security_events, upsert_privacy_settings, get_privacy_settings)
from services.logging_service import log_info

social_graph_bp = Blueprint("social_graph", __name__, url_prefix="/social/graph")
profile_extra_bp = Blueprint("profile_extra", __name__, url_prefix="/profile")

# --- Profile Completion ---

@profile_extra_bp.route("/completion")
@login_required
def view_completion():
    profile = get_current_profile()
    completion = get_completion(profile["id"])
    update_completion_percentage(profile["id"])
    return render_template("profile/completion.html", profile=profile, completion=completion)

@profile_extra_bp.route("/api/completion")
@login_required
def api_completion():
    profile = get_current_profile()
    completion = get_completion(profile["id"])
    return jsonify({"ok": True, **completion})

# --- Sent Requests ---

@social_graph_bp.route("/sent-requests")
@login_required
def view_sent_requests():
    profile = get_current_profile()
    sent = list_friend_requests(profile["id"], direction="sent", limit=50)
    return render_template("profile/sent_requests.html", profile=profile, sent=sent.get("requests", []))

# --- Friend Suggestions ---

@social_graph_bp.route("/suggestions")
@login_required
def view_suggestions():
    profile = get_current_profile()
    suggestions = suggest_friends(profile["id"], limit=30)
    mutual_suggestions = []
    for s in suggestions[:10]:
        mutual = get_mutual_friends(profile["id"], s["id"], limit=3)
        s["mutual_count"] = len(mutual)
        s["mutual_friends"] = mutual
        mutual_suggestions.append(s)
    return render_template("profile/suggestions.html", profile=profile, suggestions=mutual_suggestions)

@social_graph_bp.route("/api/suggestions/enhanced")
@login_required
def api_enhanced_suggestions():
    profile = get_current_profile()
    suggestions = suggest_friends(profile["id"], limit=30)
    blocked_ids = set()
    block_rows = __import__('services.profile_service', fromlist=['get_blocked_ids']).get_blocked_ids(profile["id"])
    blocked_ids = set(str(b) for b in (block_rows or []))
    results = []
    for s in suggestions:
        if str(s["id"]) in blocked_ids:
            continue
        mutual = get_mutual_friends(profile["id"], s["id"], limit=3)
        s["mutual_friends"] = mutual
        s["mutual_count"] = len(mutual)
        results.append(s)
    return jsonify({"ok": True, "suggestions": results})

# --- Enhanced Follower/Following with relationship checks ---

@social_graph_bp.route("/followers")
@login_required
def view_followers_enhanced():
    profile = get_current_profile()
    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 20)), 50)
    data = list_followers(profile["id"], limit=limit, cursor=cursor)
    for f in data.get("followers", []):
        pid = f.get("follower_profile_id") or f.get("profile_id")
        if pid:
            state = get_relationship_state(profile["id"], pid)
            f["i_follow_them"] = state.get("is_following", False) or state.get("follow_request_sent", False)
    return render_template("profile/followers.html", profile=profile, viewer=profile, **data)

@social_graph_bp.route("/following")
@login_required
def view_following_enhanced():
    profile = get_current_profile()
    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 20)), 50)
    data = list_following(profile["id"], limit=limit, cursor=cursor)
    return render_template("profile/following.html", profile=profile, viewer=profile, **data)

# --- Notifications API ---

@social_graph_bp.route("/api/notifications/create-test", methods=["POST"])
@login_required
def api_create_test_notification():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    ntype = data.get("type", "follow")
    title = data.get("title", "Test Notification")
    body = data.get("body", "This is a test notification.")
    recipient_id = data.get("recipient_id") or profile["id"]
    actor_id = data.get("actor_id") or profile["id"]
    nid = create_notification(
        recipient_id, ntype, title, body,
        actor_profile_id=actor_id,
        action_url="/profile"
    )
    return jsonify({"ok": True, "notification_id": nid})

# --- Profile Sharing ---

@social_graph_bp.route("/api/share")
@login_required
def api_share():
    entity_type = request.args.get("type")
    entity_id = request.args.get("id")
    data = get_share_data(entity_type, entity_id)
    if not data:
        return jsonify({"ok": False, "error": "Cannot share this content."}), 400
    return jsonify({"ok": True, "share": data})

# --- Subscriber/Locked Content ---

@social_graph_bp.route("/api/media/<media_id>/access")
@login_required
def api_media_access(media_id):
    profile = get_current_profile()
    owner_id = request.args.get("owner_id")
    if not owner_id:
        return jsonify({"ok": False, "error": "owner_id required"}), 400
    result = check_media_access(profile["id"], media_id, owner_id)
    return jsonify({"ok": True, **result})

@social_graph_bp.route("/api/locked-content/<profile_id>")
@login_required
def api_locked_content(profile_id):
    viewer = get_current_profile()
    items = get_locked_content(profile_id, viewer["id"])
    return jsonify({"ok": True, "items": items})

# --- Business Pages ---

@social_graph_bp.route("/business/<profile_id>")
def view_business_page(profile_id):
    viewer = get_current_profile()
    business = get_business_profile(profile_id)
    if not business:
        return render_template("profile/not_found.html", username=""), 404
    campaigns = get_campaigns(profile_id) if viewer and str(viewer.get("id")) == str(profile_id) else []
    return render_template("profile/business.html", profile=business, viewer=viewer, campaigns=campaigns)

@social_graph_bp.route("/api/business/update", methods=["POST"])
@login_required
def api_update_business():
    profile = get_current_profile()
    data = request.get_json(silent=True) or request.form.to_dict()
    update_business_profile(profile["id"], **data)
    return jsonify({"ok": True})

# --- Ad Campaigns ---

@social_graph_bp.route("/advertising")
@login_required
def view_advertising():
    profile = get_current_profile()
    campaigns = get_campaigns(profile["id"])
    return render_template("profile/advertising.html", profile=profile, campaigns=campaigns)

@social_graph_bp.route("/api/campaign/create", methods=["POST"])
@login_required
def api_create_campaign():
    profile = get_current_profile()
    data = request.get_json(silent=True) or request.form
    name = data.get("name", "Campaign")
    objective = data.get("objective", "reach")
    media_url = data.get("media_url")
    media_type = data.get("media_type", "image")
    budget = float(data.get("budget", 0))
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    target_audience = data.get("target_audience", {})
    result = create_campaign(profile["id"], name, objective=objective, media_url=media_url,
                             media_type=media_type, target_audience=target_audience,
                             budget=budget, start_date=start_date, end_date=end_date)
    return jsonify(result)

@social_graph_bp.route("/api/campaign/<campaign_id>/pause", methods=["POST"])
@login_required
def api_pause_campaign(campaign_id):
    profile = get_current_profile()
    result = pause_campaign(campaign_id, profile["id"])
    return jsonify(result)

# --- Security Settings ---

@profile_extra_bp.route("/security")
@login_required
def view_security():
    profile = get_current_profile()
    devices = get_device_sessions(profile["id"])
    events = get_security_events(profile["id"], limit=20)
    privacy = get_privacy_settings(profile["id"])
    trust = get_trust_summary(profile["id"])
    verification = get_verification_status(profile["id"])
    return render_template("profile/security.html", profile=profile, devices=devices,
                          events=events, privacy=privacy, trust=trust, verification=verification)

@profile_extra_bp.route("/api/security/change-password", methods=["POST"])
@login_required
def api_change_password():
    profile = get_current_profile()
    data = request.get_json(silent=True) or request.form
    current = data.get("current_password")
    new = data.get("new_password")
    if not current or not new:
        return jsonify({"ok": False, "error": "Current and new passwords required."}), 400
    if len(new) < 8:
        return jsonify({"ok": False, "error": "Password must be at least 8 characters."}), 400
    from services.auth_service import change_password
    result = change_password(profile["auth_user_id"], current, new)
    return jsonify(result or {"ok": False, "error": "Failed to change password."})

@profile_extra_bp.route("/api/security/change-email", methods=["POST"])
@login_required
def api_change_email():
    profile = get_current_profile()
    if profile.get("is_verified"):
        return jsonify({"ok": False, "error": "Verified users must contact admin to change email."}), 403
    data = request.get_json(silent=True) or request.form
    new_email = data.get("email")
    if not new_email:
        return jsonify({"ok": False, "error": "Email required."}), 400
    from services.auth_service import update_email
    result = update_email(profile["id"], new_email)
    return jsonify(result or {"ok": False, "error": "Failed to update email."})

@profile_extra_bp.route("/api/security/change-phone", methods=["POST"])
@login_required
def api_change_phone():
    profile = get_current_profile()
    if profile.get("is_verified"):
        return jsonify({"ok": False, "error": "Verified users must contact admin to change phone."}), 403
    data = request.get_json(silent=True) or request.form
    new_phone = data.get("phone")
    if not new_phone:
        return jsonify({"ok": False, "error": "Phone required."}), 400
    from services.profile_service import update_profile
    result = update_profile(profile["id"], phone=new_phone)
    return jsonify({"ok": bool(result)})

@profile_extra_bp.route("/api/security/logout-devices", methods=["POST"])
@login_required
def api_logout_devices():
    profile = get_current_profile()
    revoke_all = request.get_json(silent=True) or {}
    if revoke_all.get("all"):
        devices = get_device_sessions(profile["id"])
        for d in devices:
            revoke_device_session(d["id"], profile["id"])
        from services.session_service import clear_auth_session
        clear_auth_session()
        return jsonify({"ok": True, "logged_out": True})
    device_id = revoke_all.get("device_id")
    if device_id:
        revoke_device_session(device_id, profile["id"])
    return jsonify({"ok": True})

@profile_extra_bp.route("/api/security/request-data", methods=["POST"])
@login_required
def api_request_data():
    profile = get_current_profile()
    from services.neon_service import write_query
    write_query("UPDATE chain_profiles SET account_data_requested_at = now() WHERE id = %s", (profile["id"],))
    create_notification(
        profile["id"], "system_announcement",
        "Data Request Received",
        "Your account data request has been received. We will email you a download link within 48 hours.",
        action_url="/profile/security"
    )
    return jsonify({"ok": True})

@profile_extra_bp.route("/api/security/delete-account", methods=["POST"])
@login_required
def api_delete_account():
    profile = get_current_profile()
    from services.neon_service import write_query
    write_query("UPDATE chain_profiles SET account_delete_requested_at = now(), deleted_at = now() WHERE id = %s",
               (profile["id"],))
    from services.session_service import clear_auth_session
    clear_auth_session()
    return jsonify({"ok": True, "redirect": "/"})

@profile_extra_bp.route("/api/security/report-problem", methods=["POST"])
@login_required
def api_report_problem():
    profile = get_current_profile()
    data = request.get_json(silent=True) or request.form
    subject = data.get("subject", "Report")
    message = data.get("message", "")
    if not message:
        return jsonify({"ok": False, "error": "Message required."}), 400
    from services.neon_service import write_query
    import uuid
    write_query(
        "INSERT INTO chain_support_reports (id, profile_id, subject, message) VALUES (%s, %s, %s, %s)",
        (str(uuid.uuid4()), profile["id"], subject, message)
    )
    return jsonify({"ok": True})

# --- Privacy Settings ---

@profile_extra_bp.route("/api/privacy/update", methods=["POST"])
@login_required
def api_update_privacy():
    profile = get_current_profile()
    data = request.get_json(silent=True) or request.form
    vis_map = {
        "show_phone_publicly": "show_phone_publicly",
        "show_email_publicly": "show_email_publicly",
        "show_location_publicly": "show_location_publicly",
    }
    profile_updates = {}
    for key, col in vis_map.items():
        if key in data:
            val = str(data[key]).lower() in ("true", "1", "yes", "on")
            profile_updates[col] = val
    if profile_updates:
        sets = ", ".join(f'"{k}" = %s' for k in profile_updates)
        vals = list(profile_updates.values()) + [profile["id"]]
        from services.neon_service import write_query
        write_query(f"UPDATE chain_profiles SET {sets} WHERE id = %s", vals)
    privacy_updates = {}
    for key in ["show_online_status", "show_last_seen", "show_read_receipts",
                 "show_typing_indicator", "show_profile_photo", "allow_calls", "allow_group_invites"]:
        if key in data:
            privacy_updates[key] = str(data[key]).lower() in ("true", "1", "yes", "on")
    if privacy_updates:
        upsert_privacy_settings(profile["id"], privacy_updates)
    return jsonify({"ok": True, "profile_updates": profile_updates, "privacy_updates": privacy_updates})

# --- Location Privacy ---

@profile_extra_bp.route("/api/location/settings")
@login_required
def api_location_settings():
    profile = get_current_profile()
    settings = get_location_settings(profile["id"])
    return jsonify({"ok": True, "settings": settings})

@profile_extra_bp.route("/api/location/start-sharing", methods=["POST"])
@login_required
def api_location_start():
    profile = get_current_profile()
    data = request.get_json(silent=True) or request.form
    lat = float(data.get("latitude", 0))
    lng = float(data.get("longitude", 0))
    viewers = data.get("authorized_viewers", [])
    result = start_sharing(profile["id"], lat, lng, authorized_viewers=viewers)
    return jsonify(result)

@profile_extra_bp.route("/api/location/stop-sharing", methods=["POST"])
@login_required
def api_location_stop():
    profile = get_current_profile()
    result = stop_sharing(profile["id"])
    return jsonify(result)

# --- Verification Request ---

@profile_extra_bp.route("/verification")
@login_required
def view_verification():
    profile = get_current_profile()
    status = get_verification_status(profile["id"])
    return render_template("profile/verification_request.html", profile=profile, verification=status)

@profile_extra_bp.route("/api/verification/submit", methods=["POST"])
@login_required
def api_submit_verification():
    profile = get_current_profile()
    data = request.form.to_dict()
    files = request.files
    id_front_url = data.get("id_front_url")
    id_back_url = data.get("id_back_url")
    address_proof_url = data.get("address_proof_url")
    selfie_video_url = data.get("selfie_video_url")
    whatsapp_phone = data.get("whatsapp_phone")
    whatsapp_code = data.get("whatsapp_code")
    address_proof_type = data.get("address_proof_type", "water_bill")

    if files.get("id_front"):
        from services.storage_service import upload_verification_file
        res, err = upload_verification_file(profile["id"], files["id_front"], "id_front")
        if err:
            return jsonify({"ok": False, "error": err}), 400
        id_front_url = res.get("public_url")
    if files.get("id_back"):
        from services.storage_service import upload_verification_file
        res, err = upload_verification_file(profile["id"], files["id_back"], "id_back")
        if err:
            return jsonify({"ok": False, "error": err}), 400
        id_back_url = res.get("public_url")
    if files.get("address_proof"):
        from services.storage_service import upload_verification_file
        res, err = upload_verification_file(profile["id"], files["address_proof"], "address_proof")
        if err:
            return jsonify({"ok": False, "error": err}), 400
        address_proof_url = res.get("public_url")
    if files.get("selfie_video"):
        from services.storage_service import upload_verification_file
        res, err = upload_verification_file(profile["id"], files["selfie_video"], "selfie")
        if err:
            return jsonify({"ok": False, "error": err}), 400
        selfie_video_url = res.get("public_url")

    result = submit_verification(
        profile["id"], id_front_url=id_front_url, id_back_url=id_back_url,
        address_proof_url=address_proof_url, address_proof_type=address_proof_type,
        selfie_video_url=selfie_video_url, whatsapp_phone=whatsapp_phone,
        whatsapp_code=whatsapp_code
    )
    return jsonify(result)
