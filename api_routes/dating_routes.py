from flask import Blueprint, redirect, render_template, request, jsonify
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.dating_service import (
    get_dating_profile, get_or_create_dating_profile, update_dating_profile,
    set_dating_mode, get_discover_profiles,
    like_profile, pass_profile, super_like_profile, undo_last_action,
    get_matches, get_likes_you,
    block_user, report_user, is_blocked, is_blocked_by, unmatch_users,
    get_dating_preferences, update_dating_preferences,
    calculate_compatibility, restrict_dating_visibility,
    become_friends, sos_alert,
)
from services.ai.interaction_service import track_interaction_safe

dating_bp = Blueprint("dating", __name__, url_prefix="/dating")


# ─── HTML PAGES ──────────────────────────────────────────────

@dating_bp.route("/")
def dating_home():
    return render_template("dating/index.html")


@dating_bp.route("/discover")
@login_required
def discover():
    profile = get_current_profile()
    if not profile:
        return redirect("/auth/login")
    profiles = get_discover_profiles(profile["id"])
    return render_template("dating/discover.html", items=profiles, current=profile)


@dating_bp.route("/matches")
@login_required
def matches_page():
    profile = get_current_profile()
    return render_template("dating/index.html", profile=profile, start_tab="matches")


@dating_bp.route("/preferences")
@login_required
def preferences_page():
    profile = get_current_profile()
    return render_template("dating/index.html", profile=profile, start_tab="premium")


@dating_bp.route("/safety")
@login_required
def safety_page():
    profile = get_current_profile()
    return render_template("dating/index.html", profile=profile, start_tab="premium")


@dating_bp.route("/profile/<profile_id>")
def dating_profile(profile_id):
    from services.profile_service import get_profile_bundle
    profile = get_profile_bundle(profile_id=profile_id)
    dating_prof = get_dating_profile(profile_id)
    # Strip phone from profile for dating context — only premium with show_phone_publicly may see it
    viewer = get_current_profile()
    if not viewer:
        profile.pop("phone", None)
    else:
        from services.dating_service import _may_see_phone
        if not _may_see_phone(viewer, dating_prof):
            profile.pop("phone", None)
        if viewer.get("id") and str(viewer.get("id")) != str(profile_id):
            track_interaction_safe(viewer["id"], "dating_profile", profile_id, "open", source_surface="dating")
    return render_template("dating/profile.html", profile=profile, dating_profile=dating_prof)


# ─── API ─── DISCOVER ───────────────────────────────────────

@dating_bp.route("/api/discover")
@login_required
def api_discover():
    profile = get_current_profile()
    limit = request.args.get("limit", 30, type=int)
    offset = request.args.get("offset", 0, type=int)
    data = get_discover_profiles(profile["id"], limit=limit, offset=offset)
    # Strip phone from every result
    for row in data:
        row.pop("phone", None)
    return jsonify({"ok": True, "data": data})


# ─── API ─── LIKE / PASS / SUPER LIKE / UNDO ────────────────

@dating_bp.route("/api/like", methods=["POST"])
@login_required
def api_like():
    profile = get_current_profile()
    body = request.get_json(silent=True) or {}
    target_id = body.get("target_id")
    if not target_id:
        return jsonify({"ok": False, "error": "target_id_required"}), 400
    result = like_profile(profile["id"], target_id)
    if result.get("ok"):
        track_interaction_safe(profile["id"], "dating_profile", target_id, "like", source_surface="dating")
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@dating_bp.route("/api/pass", methods=["POST"])
@login_required
def api_pass():
    profile = get_current_profile()
    body = request.get_json(silent=True) or {}
    target_id = body.get("target_id")
    if not target_id:
        return jsonify({"ok": False, "error": "target_id_required"}), 400
    result = pass_profile(profile["id"], target_id)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@dating_bp.route("/api/super-like", methods=["POST"])
@login_required
def api_super_like():
    profile = get_current_profile()
    body = request.get_json(silent=True) or {}
    target_id = body.get("target_id")
    if not target_id:
        return jsonify({"ok": False, "error": "target_id_required"}), 400
    result = super_like_profile(profile["id"], target_id)
    if result.get("ok"):
        track_interaction_safe(profile["id"], "dating_profile", target_id, "like", source_surface="dating")
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@dating_bp.route("/api/undo", methods=["POST"])
@login_required
def api_undo():
    profile = get_current_profile()
    result = undo_last_action(profile["id"])
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


# ─── API ─── MATCHES ─────────────────────────────────────────

@dating_bp.route("/api/matches")
@login_required
def api_matches():
    profile = get_current_profile()
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    data = get_matches(profile["id"], limit=limit, offset=offset)
    return jsonify({"ok": True, "data": data})


# ─── API ─── LIKES YOU ───────────────────────────────────────

@dating_bp.route("/api/likes-you")
@login_required
def api_likes_you():
    profile = get_current_profile()
    limit = request.args.get("limit", 30, type=int)
    offset = request.args.get("offset", 0, type=int)
    data = get_likes_you(profile["id"], limit=limit, offset=offset)
    return jsonify({"ok": True, "data": data})


# ─── API ─── BLOCK ──────────────────────────────────────────

@dating_bp.route("/api/block", methods=["POST"])
@login_required
def api_block():
    profile = get_current_profile()
    body = request.get_json(silent=True) or {}
    target_id = body.get("target_id")
    if not target_id:
        return jsonify({"ok": False, "error": "target_id_required"}), 400
    result = block_user(profile["id"], target_id)
    if result.get("ok"):
        track_interaction_safe(profile["id"], "dating_profile", target_id, "block", source_surface="dating")
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


# ─── API ─── REPORT ─────────────────────────────────────────

@dating_bp.route("/api/report", methods=["POST"])
@login_required
def api_report():
    profile = get_current_profile()
    body = request.get_json(silent=True) or {}
    target_id = body.get("target_id")
    reason = body.get("reason", "other")
    details = body.get("details", "")
    if not target_id:
        return jsonify({"ok": False, "error": "target_id_required"}), 400
    if not reason:
        return jsonify({"ok": False, "error": "reason_required"}), 400
    result = report_user(profile["id"], target_id, reason, details)
    if result.get("ok"):
        track_interaction_safe(profile["id"], "dating_profile", target_id, "report", source_surface="dating")
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@dating_bp.route("/api/unmatch", methods=["POST"])
@login_required
def api_unmatch():
    profile = get_current_profile()
    body = request.get_json(silent=True) or {}
    target_id = body.get("target_id")
    if not target_id:
        return jsonify({"ok": False, "error": "target_id_required"}), 400
    result = unmatch_users(profile["id"], target_id)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


# ─── API ─── PREFERENCES ────────────────────────────────────

@dating_bp.route("/api/preferences", methods=["GET", "POST"])
@login_required
def api_preferences():
    profile = get_current_profile()
    if request.method == "GET":
        prefs = get_dating_preferences(profile["id"])
        dating_prof = get_or_create_dating_profile(profile["id"])
        dating_prof.pop("phone", None)
        return jsonify({"ok": True, "preferences": prefs, "dating_profile": dating_prof})
    body = request.get_json(silent=True) or {}
    # Separate dating profile fields from preference fields
    dating_fields = {"dating_mode_on", "relationship_goal", "bio", "interests", "photos",
                     "age_range_min", "age_range_max", "location_preference",
                     "show_phone_publicly", "hide_from_contacts", "visible_to_verified_only"}
    dating_kw = {k: v for k, v in body.items() if k in dating_fields}
    pref_kw = {k: v for k, v in body.items() if k in {"interested_in", "min_age", "max_age", "max_distance_km", "show_me", "only_verified", "hide_from_contacts"}}
    if dating_kw:
        update_dating_profile(profile["id"], **dating_kw)
    if pref_kw:
        update_dating_preferences(profile["id"], **pref_kw)
    return jsonify({"ok": True}), 200


# ─── API ─── MODE ───────────────────────────────────────────

@dating_bp.route("/api/mode", methods=["POST"])
@login_required
def api_mode():
    profile = get_current_profile()
    body = request.get_json(silent=True) or {}
    on = body.get("on", True)
    result = set_dating_mode(profile["id"], on)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


# ─── API ─── COMPATIBILITY ──────────────────────────────────

@dating_bp.route("/api/compatibility/<target_id>")
@login_required
def api_compatibility(target_id):
    profile = get_current_profile()
    score = calculate_compatibility(profile["id"], target_id)
    return jsonify({"ok": True, "compatibility_score": score})


# ─── API ─── DATING PROFILE ─────────────────────────────────

@dating_bp.route("/api/profile", methods=["GET", "POST"])
@login_required
def api_dating_profile():
    profile = get_current_profile()
    if request.method == "GET":
        dating_prof = get_or_create_dating_profile(profile["id"])
        return jsonify({"ok": True, "dating_profile": dating_prof})
    body = request.get_json(silent=True) or {}
    result = update_dating_profile(profile["id"], **body)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


# ─── API ─── RESTRICT VISIBILITY ────────────────────────────

@dating_bp.route("/api/restrict", methods=["POST"])
@login_required
def api_restrict():
    profile = get_current_profile()
    body = request.get_json(silent=True) or {}
    hide = body.get("hide_from_contacts", False)
    verified_only = body.get("visible_to_verified_only", False)
    result = restrict_dating_visibility(profile["id"], hide, verified_only)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


# ─── API ─── BECOME FRIENDS ──────────────────────────────────

@dating_bp.route("/api/become-friends/<match_id>", methods=["POST"])
@login_required
def api_become_friends(match_id):
    profile = get_current_profile()
    result = become_friends(profile["id"], match_id)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


# ─── API ─── SOS / EMERGENCY ─────────────────────────────────

@dating_bp.route("/api/sos", methods=["POST"])
@login_required
def api_sos():
    profile = get_current_profile()
    body = request.get_json(silent=True) or {}
    lat = body.get("lat")
    lng = body.get("lng")
    result = sos_alert(profile["id"], lat=lat, lng=lng)
    return jsonify(result)
