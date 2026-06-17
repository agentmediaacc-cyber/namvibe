"""Follow Request API Routes."""

from flask import Blueprint, request, jsonify
from services.profile_service import get_current_profile
from api_routes.profile_routes import login_required
from services.follow_request_service import (
    send_follow_request, approve_follow_request, decline_follow_request,
    cancel_follow_request, get_follow_status,
    list_incoming_follow_requests, list_outgoing_follow_requests
)

follow_request_api_bp = Blueprint("follow_request_api", __name__, url_prefix="/api/follow")

@follow_request_api_bp.route("/request/<profile_id>", methods=["POST"])
@login_required
def api_send_follow_request(profile_id):
    profile = get_current_profile()
    message = request.json.get("message") if request.is_json else request.form.get("message")
    res = send_follow_request(profile["id"], profile_id, message=message)
    return jsonify(res)

@follow_request_api_bp.route("/approve/<request_id>", methods=["POST"])
@login_required
def api_approve_follow_request(request_id):
    profile = get_current_profile()
    res = approve_follow_request(request_id, profile["id"])
    return jsonify(res)

@follow_request_api_bp.route("/decline/<request_id>", methods=["POST"])
@login_required
def api_decline_follow_request(request_id):
    profile = get_current_profile()
    res = decline_follow_request(request_id, profile["id"])
    return jsonify(res)

@follow_request_api_bp.route("/cancel/<request_id>", methods=["POST"])
@login_required
def api_cancel_follow_request(request_id):
    profile = get_current_profile()
    res = cancel_follow_request(request_id, profile["id"])
    return jsonify(res)

@follow_request_api_bp.route("/status/<profile_id>")
@login_required
def api_get_follow_status(profile_id):
    profile = get_current_profile()
    status = get_follow_status(profile["id"], profile_id)
    return jsonify({"ok": True, "status": status})

@follow_request_api_bp.route("/requests/incoming")
@login_required
def api_list_incoming():
    profile = get_current_profile()
    requests = list_incoming_follow_requests(profile["id"])
    return jsonify({"ok": True, "requests": requests})

@follow_request_api_bp.route("/requests/outgoing")
@login_required
def api_list_outgoing():
    profile = get_current_profile()
    requests = list_outgoing_follow_requests(profile["id"])
    return jsonify({"ok": True, "requests": requests})
