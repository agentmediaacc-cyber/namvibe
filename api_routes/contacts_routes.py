"""Contacts routes — list friends as contacts, message/call/block actions."""

from flask import Blueprint, jsonify, render_template, request, session
from services.neon_service import fast_query, write_query
from services.profile_service import get_current_profile
from services.blocking_service import is_blocked_any

contacts_bp = Blueprint("contacts", __name__, url_prefix="/contacts")
contacts_api_bp = Blueprint("contacts_api", __name__, url_prefix="/api/contacts")


def _current_profile():
    p = get_current_profile()
    if not p:
        return None
    return p


@contacts_bp.route("/")
def contacts_page():
    profile = _current_profile()
    if not profile:
        return render_template("auth/login.html", error="Please log in to view your contacts.")
    return render_template("profile/contacts.html", profile=profile)


@contacts_api_bp.route("/")
def api_contacts():
    profile = _current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    pid = profile["id"]
    
    # Phase 130: Add caching to prevent slow database queries (Cloudflare tunnel fix)
    from engines.cache_engine import cache_key, get_cache, set_cache
    cache_key_str = cache_key("contacts", pid)
    cached_contacts = get_cache(cache_key_str)
    if cached_contacts is not None:
        return jsonify({"ok": True, "contacts": cached_contacts})
    
    rows = fast_query(
        """
        SELECT
          f.id AS friendship_id, f.created_at AS friendship_date,
          p.id AS profile_id, p.username, p.display_name, p.full_name,
          p.avatar_url, p.is_online, p.is_verified
        FROM chain_friends f
        JOIN chain_profiles p ON p.id = CASE WHEN f.profile_id_1 = %s THEN f.profile_id_2 ELSE f.profile_id_1 END
        WHERE (f.profile_id_1 = %s OR f.profile_id_2 = %s)
          AND f.status = 'friend' AND f.deleted_at IS NULL AND p.deleted_at IS NULL
        ORDER BY p.display_name NULLS LAST, p.username
        """,
        (pid, pid, pid), default=[]
    )
    contacts = []
    for r in rows:
        fid = r["profile_id"]
        contacts.append({
            "profile_id": fid,
            "username": r["username"],
            "display_name": r.get("display_name") or r.get("full_name") or r["username"],
            "full_name": r.get("full_name") or "",
            "avatar_url": r.get("avatar_url") or "",
            "is_online": bool(r.get("is_online")),
            "is_verified": bool(r.get("is_verified")),
            "last_seen": "",
            "friendship_date": (r.get("friendship_date") or "").isoformat() if hasattr(r.get("friendship_date"), "isoformat") else (r.get("friendship_date") or ""),
            "message_url": f"/messages/start/{fid}",
            "audio_call_url": f"/calls/start/{fid}/audio",
            "video_call_url": f"/calls/start/{fid}/video",
            "profile_url": f"/profile/{r.get('username')}",
        })
    
    # Cache for 60 seconds to reduce database load
    set_cache(cache_key_str, contacts, ttl=60)
    return jsonify({"ok": True, "contacts": contacts})


@contacts_api_bp.route("/search")
def api_contacts_search():
    profile = _current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    q = (request.args.get("q") or "").strip()
    if not q or len(q) < 2:
        return jsonify({"ok": True, "contacts": []})
    pid = profile["id"]
    pattern = f"%{q}%"
    rows = fast_query(
        """
        SELECT p.id, p.username, p.display_name, p.full_name, p.avatar_url, p.is_online
        FROM chain_friends f
        JOIN chain_profiles p ON p.id = CASE WHEN f.profile_id_1 = %s THEN f.profile_id_2 ELSE f.profile_id_1 END
        WHERE (f.profile_id_1 = %s OR f.profile_id_2 = %s)
          AND f.status = 'friend' AND f.deleted_at IS NULL AND p.deleted_at IS NULL
          AND (p.username ILIKE %s OR p.display_name ILIKE %s OR p.full_name ILIKE %s)
        ORDER BY p.display_name NULLS LAST, p.username
        LIMIT 20
        """,
        (pid, pid, pid, pattern, pattern, pattern), default=[]
    )
    return jsonify({"ok": True, "contacts": [
        {"profile_id": r["id"], "username": r["username"],
         "display_name": r.get("display_name") or r.get("full_name") or r["username"],
         "avatar_url": r.get("avatar_url") or "", "is_online": bool(r.get("is_online"))}
        for r in rows
    ]})


@contacts_api_bp.route("/<profile_id>/remove", methods=["POST"])
def api_contact_remove(profile_id):
    profile = _current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    from services.social_relationship_service import unfriend
    res = unfriend(profile["id"], profile_id)
    return jsonify(res)


@contacts_api_bp.route("/<profile_id>/block", methods=["POST"])
def api_contact_block(profile_id):
    profile = _current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    from services.profile_service import block_profile
    ok = block_profile(profile["id"], profile_id)
    return jsonify({"ok": ok})


@contacts_api_bp.route("/<profile_id>/message", methods=["GET"])
def api_contact_message(profile_id):
    profile = _current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    if is_blocked_any(profile["id"], profile_id):
        return jsonify({"ok": False, "error": "Cannot message this user."}), 403
    return jsonify({"ok": True, "redirect": f"/messages/start/{profile_id}"})


@contacts_api_bp.route("/<profile_id>/call", methods=["GET"])
def api_contact_call(profile_id):
    profile = _current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    if is_blocked_any(profile["id"], profile_id):
        return jsonify({"ok": False, "error": "Cannot call this user."}), 403
    return jsonify({"ok": True, "redirect": f"/calls/start/{profile_id}/audio"})


@contacts_api_bp.route("/<profile_id>/video-call", methods=["GET"])
def api_contact_video_call(profile_id):
    profile = _current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Not logged in"}), 401
    if is_blocked_any(profile["id"], profile_id):
        return jsonify({"ok": False, "error": "Cannot call this user."}), 403
    return jsonify({"ok": True, "redirect": f"/calls/start/{profile_id}/video"})