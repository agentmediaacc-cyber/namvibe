"""
Friend Routes — Friendship system API endpoints.
"""
from flask import Blueprint, jsonify, request, render_template
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.friendship_service import (
    send_friend_request, accept_friend_request, decline_friend_request,
    cancel_friend_request, get_friendship_status, are_friends,
    get_current_profile_id
)
from services.friend_service import list_friend_requests, list_friends

friend_bp = Blueprint("friends", __name__)


@friend_bp.route("/api/friends/status/<profile_id>")
@login_required
def api_friend_status(profile_id):
    current = get_current_profile()
    if not current:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    status = get_friendship_status(current["id"], profile_id)
    return jsonify({"ok": True, **status})


@friend_bp.route("/api/friends/request/<profile_id>", methods=["POST"])
@login_required
def api_send_friend_request(profile_id):
    current = get_current_profile()
    if not current:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if current["id"] == profile_id:
        return jsonify({"ok": False, "error": "Cannot send friend request to yourself"}), 400
    data = request.get_json(silent=True) or {}
    message = data.get("message")
    result = send_friend_request(current["id"], profile_id, message=message)
    if result.get("success"):
        return jsonify({"ok": True, "request_id": result.get("request_id")})
    return jsonify({"ok": False, "error": result.get("error", "Request failed")}), 400


@friend_bp.route("/api/friends/accept/<request_id>", methods=["POST"])
@login_required
def api_accept_friend_request(request_id):
    current = get_current_profile()
    if not current:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = accept_friend_request(request_id, current["id"])
    if result.get("success"):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": result.get("error", "Accept failed")}), 400


@friend_bp.route("/api/friends/decline/<request_id>", methods=["POST"])
@login_required
def api_decline_friend_request(request_id):
    current = get_current_profile()
    if not current:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = decline_friend_request(request_id, current["id"])
    if result.get("success"):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": result.get("error", "Decline failed")}), 400


@friend_bp.route("/api/friends/cancel/<request_id>", methods=["POST"])
@login_required
def api_cancel_friend_request(request_id):
    current = get_current_profile()
    if not current:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = cancel_friend_request(request_id, current["id"])
    if result.get("success"):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": result.get("error", "Cancel failed")}), 400


@friend_bp.route("/api/friends/requests")
@login_required
def api_friend_requests():
    current = get_current_profile()
    if not current:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    received = list_friend_requests(current["id"], direction="received", limit=50)
    sent = list_friend_requests(current["id"], direction="sent", limit=50)
    return jsonify({
        "ok": True,
        "received": received.get("requests", []),
        "sent": sent.get("requests", []),
    })


@friend_bp.route("/friends/requests")
@login_required
def view_friend_requests():
    current = get_current_profile()
    if not current:
        return render_template("auth/login.html")
    received = list_friend_requests(current["id"], direction="received", limit=50)
    sent = list_friend_requests(current["id"], direction="sent", limit=50)
    return render_template("profile/friend_requests.html",
                           profile=current,
                           received=received.get("requests", []),
                           sent=sent.get("requests", []))
