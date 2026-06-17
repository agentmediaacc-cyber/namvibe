"""
Social Routes — Friends and Followers management.
"""
from flask import Blueprint, jsonify, request, session, render_template, redirect, url_for, flash
from services.friend_service import (
    send_friend_request, accept_friend_request, decline_friend_request,
    cancel_friend_request, remove_friend, list_friends, list_friend_requests,
    get_mutual_friends, suggest_friends, set_friend_status, are_friends
)
from services.social_service import list_followers, list_following
from services.profile_service import get_current_profile, get_profile_by_username
from api_routes.profile_routes import login_required, invalidate_profile_cache

social_bp = Blueprint("social", __name__)

@social_bp.route("/api/friends")
@login_required
def api_friends():
    profile = get_current_profile()
    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 20)), 50)
    return jsonify(list_friends(profile['id'], limit=limit, cursor=cursor))

@social_bp.route("/follow/<profile_id>", methods=["POST"])
@login_required
def api_follow(profile_id):
    profile = get_current_profile()
    from services.engagement_service import is_following, unfollow_profile
    from services.follow_request_service import send_follow_request
    
    # Toggle logic: if already following, unfollow.
    if is_following(profile["id"], profile_id):
        res = unfollow_profile(profile["id"], profile_id)
        following = False
        status = "none"
    else:
        # Use follow_request_service to handle private accounts
        res = send_follow_request(profile["id"], profile_id)
        if not res.get("ok"):
            return jsonify({"status": "error", "error": res.get("error")}), 400
        
        status = res.get("status")
        following = (status == "following")
        
    invalidate_profile_cache(profile["id"])
    invalidate_profile_cache(profile_id)
    return jsonify({
        "status": "ok", 
        "following": following, 
        "requested": (status == "request_pending"),
        "follow_status": status
    })

@social_bp.route("/block/<profile_id>", methods=["POST"])
@login_required
def api_block(profile_id):
    profile = get_current_profile()
    from services.profile_service import block_profile
    ok = block_profile(profile["id"], profile_id)
    invalidate_profile_cache(profile["id"])
    return jsonify({"status": "ok" if ok else "error"})

@social_bp.route("/followers/remove/<follower_id>", methods=["POST"])
@login_required
def api_remove_follower(follower_id):
    profile = get_current_profile()
    from services.engagement_service import unfollow_profile
    # For remove follower, the target profile unfollows the current profile
    res = unfollow_profile(follower_id, profile["id"])
    invalidate_profile_cache(profile["id"])
    invalidate_profile_cache(follower_id)
    return jsonify({"status": "ok" if res.get("success") else "error"})

@social_bp.route("/following/remove/<following_id>", methods=["POST"])
@login_required
def api_remove_following(following_id):
    profile = get_current_profile()
    from services.engagement_service import unfollow_profile
    res = unfollow_profile(profile["id"], following_id)
    invalidate_profile_cache(profile["id"])
    invalidate_profile_cache(following_id)
    return jsonify({"status": "ok" if res.get("success") else "error"})

@social_bp.route("/unblock/<target_id>", methods=["POST"])
@login_required
def api_unblock(target_id):
    profile = get_current_profile()
    from services.profile_service import unblock_profile
    ok = unblock_profile(profile["id"], target_id)
    invalidate_profile_cache(profile["id"])
    return jsonify({"status": "ok" if ok else "error"})

@social_bp.route("/friends/request", methods=["POST"])
@login_required
def api_send_request():
    profile = get_current_profile()
    recipient_id = request.form.get("recipient_id") or request.json.get("recipient_id") or request.json.get("receiver_profile_id")
    if not recipient_id:
        return jsonify({"success": False, "error": "Recipient ID is required."}), 400
    res = send_friend_request(profile['id'], recipient_id)
    if res.get("success"):
        invalidate_profile_cache(profile["id"])
    return jsonify(res)

@social_bp.route("/friends/accept", methods=["POST"])
@login_required
def api_accept_request():
    profile = get_current_profile()
    request_id = request.form.get("request_id") or request.json.get("request_id")
    if not request_id:
        return jsonify({"success": False, "error": "Request ID is required."}), 400
    res = accept_friend_request(profile['id'], request_id)
    if res.get("success"):
        invalidate_profile_cache(profile["id"])
    return jsonify(res)

@social_bp.route("/friends/decline", methods=["POST"])
@login_required
def api_decline_request():
    profile = get_current_profile()
    request_id = request.form.get("request_id") or request.json.get("request_id")
    res = decline_friend_request(profile['id'], request_id)
    return jsonify(res)

@social_bp.route("/friends/cancel", methods=["POST"])
@login_required
def api_cancel_request():
    profile = get_current_profile()
    request_id = request.form.get("request_id") or request.json.get("request_id")
    res = cancel_friend_request(profile['id'], request_id)
    return jsonify(res)

@social_bp.route("/friends/remove", methods=["POST"])
@login_required
def api_remove_friend():
    profile = get_current_profile()
    friend_id = request.form.get("friend_id") or request.json.get("friend_id")
    res = remove_friend(profile['id'], friend_id)
    if res.get("success"):
        invalidate_profile_cache(profile["id"])
    return jsonify(res)

@social_bp.route("/friends")
@login_required
def view_friends():
    profile = get_current_profile()
    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 20)), 50)
    
    friends_data = list_friends(profile['id'], limit=limit, cursor=cursor)
    pending = list_friend_requests(profile['id'], direction='received', limit=20)
    outbound = list_friend_requests(profile['id'], direction='sent', limit=20)
    
    return render_template(
        "profile/friends.html",
        profile=profile,
        total=profile.get('friends_count', 0),
        friends=friends_data['friends'],
        pending_requests=pending['requests'],
        outbound_requests=outbound['requests'],
        next_cursor=friends_data['next_cursor'],
        has_more=friends_data['has_more']
    )

@social_bp.route("/@<username>/friends")
def view_user_friends(username):
    viewer = get_current_profile()
    profile = get_profile_by_username(username)
    if not profile:
        return render_template("profile/not_found.html", username=username), 404
    cursor = request.args.get("cursor")
    limit = min(request.args.get("limit", 20, type=int), 20)
    result = list_friends(profile["id"], cursor=cursor, limit=limit)
    return render_template("profile/friends.html", profile=profile, viewer=viewer,
                           friends=result["friends"], total=profile.get("friends_count", 0),
                           next_cursor=result["next_cursor"])

@social_bp.route("/friend-requests")
@login_required
def view_requests():
    profile = get_current_profile()
    return redirect(url_for('social.view_friends'))

@social_bp.route("/followers")
@login_required
def view_followers():
    profile = get_current_profile()
    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 20)), 50)
    data = list_followers(profile['id'], limit=limit, cursor=cursor)
    return render_template("profile/followers.html", profile=profile, **data)

@social_bp.route("/following")
@login_required
def view_following():
    profile = get_current_profile()
    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 20)), 50)
    data = list_following(profile['id'], limit=limit, cursor=cursor)
    return render_template("profile/following.html", profile=profile, **data)

@social_bp.route("/@<username>/followers")
def view_user_followers(username):
    viewer = get_current_profile()
    profile = get_profile_by_username(username)
    if not profile:
        return render_template("profile/not_found.html", username=username), 404
    from services.relationship_privacy_service import can_view_followers
    viewer_id = viewer.get("id") if viewer else None
    if viewer_id and str(viewer_id) != str(profile["id"]):
        if not can_view_followers(viewer_id, profile):
            return jsonify({"ok": False, "error": "privacy_restricted", "message": "This user's followers are private."}), 403
    cursor = request.args.get("cursor")
    limit = min(request.args.get("limit", 20, type=int), 50)
    data = list_followers(profile['id'], limit=limit, cursor=cursor)
    return render_template("profile/followers.html", profile=profile, viewer=viewer, **data)

@social_bp.route("/@<username>/following")
def view_user_following(username):
    viewer = get_current_profile()
    profile = get_profile_by_username(username)
    if not profile:
        return render_template("profile/not_found.html", username=username), 404
    from services.relationship_privacy_service import can_view_following
    viewer_id = viewer.get("id") if viewer else None
    if viewer_id and str(viewer_id) != str(profile["id"]):
        if not can_view_following(viewer_id, profile):
            return jsonify({"ok": False, "error": "privacy_restricted", "message": "This user's following list is private."}), 403
    cursor = request.args.get("cursor")
    limit = min(request.args.get("limit", 20, type=int), 50)
    data = list_following(profile['id'], limit=limit, cursor=cursor)
    return render_template("profile/following.html", profile=profile, viewer=viewer, **data)

@social_bp.route("/api/followers")
@login_required
def api_followers():
    profile = get_current_profile()
    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 20)), 50)
    return jsonify(list_followers(profile['id'], limit=limit, cursor=cursor))

@social_bp.route("/api/following")
@login_required
def api_following():
    profile = get_current_profile()
    cursor = request.args.get("cursor")
    limit = min(int(request.args.get("limit", 20)), 50)
    return jsonify(list_following(profile['id'], limit=limit, cursor=cursor))

@social_bp.route("/api/mutual-friends/<other_id>")
@login_required
def api_mutual_friends(other_id):
    profile = get_current_profile()
    limit = min(int(request.args.get("limit", 20)), 50)
    offset = int(request.args.get("offset", 0))
    mutual = get_mutual_friends(profile['id'], other_id, limit=limit, offset=offset)
    return jsonify({"mutual_friends": mutual})

@social_bp.route("/api/suggestions")
@login_required
def api_friend_suggestions():
    profile = get_current_profile()
    suggestions = suggest_friends(profile["id"])
    return jsonify({"suggestions": suggestions})

@social_bp.route("/api/status/<target_id>")
@login_required
def api_social_status(target_id):
    profile = get_current_profile()
    status = "none"
    if are_friends(profile["id"], target_id):
        status = "friend"
    return jsonify({"status": status})

@social_bp.route("/api/social/action-policy/<profile_id>")
def api_action_policy(profile_id):
    from services.profile_service import get_current_profile, get_profile_by_id
    from services.social_action_policy import get_action_policy
    viewer = get_current_profile() if session.get("profile_id") else None
    viewer_id = viewer.get("id") if viewer else None
    target = get_profile_by_id(profile_id)
    if not target:
        return jsonify({"ok": False, "error": "Profile not found"}), 404
    policy = get_action_policy(viewer_id, target)
    return jsonify({"ok": True, "policy": policy})

@social_bp.route("/api/privacy/settings", methods=["GET"])
@login_required
def api_privacy_settings_get():
    from services.profile_service import get_current_profile, get_profile_privacy
    from services.security_service import get_privacy_settings
    profile = get_current_profile()
    settings = get_privacy_settings(profile["id"])
    rel_privacy = get_profile_privacy(profile["id"])
    settings.update(rel_privacy)
    return jsonify({"ok": True, "settings": settings})

@social_bp.route("/api/privacy/settings", methods=["POST"])
@login_required
def api_privacy_settings_post():
    from services.profile_service import get_current_profile, update_profile_privacy, get_profile_privacy
    from services.security_service import upsert_privacy_settings, get_privacy_settings
    profile = get_current_profile()
    data = request.json or request.form or {}
    
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
            settings[key] = str(data[key]).lower() in ("true", "1", "yes", "on")
    
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

