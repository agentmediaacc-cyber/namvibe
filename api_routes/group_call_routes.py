import os
from flask import Blueprint, request, jsonify
from services.profile_service import get_current_profile
from services.group_call_service import (
    create_group_call, get_group_call, join_group_call, leave_group_call,
    invite_participant, remove_participant, mute_participant, unmute_participant,
    raise_hand, lower_hand, lock_room, unlock_room, transfer_host,
    end_group_call, get_group_call_history, get_participants_with_profiles,
    update_speaking_status, update_camera_status, update_screen_share_status,
    get_active_group_call, get_participants,
)
from api_routes.profile_routes import login_required

group_call_bp = Blueprint("group_calls", __name__, url_prefix="/group-calls")


@group_call_bp.route("/api/create", methods=["POST"])
@login_required
def api_create():
    profile = get_current_profile()
    data = request.json or {}
    room_name = data.get("room_name", f"{profile.get('display_name', 'User')}'s Room")
    call_type = data.get("call_type", "audio")
    thread_id = data.get("thread_id")
    max_participants = data.get("max_participants", 32)
    call = create_group_call(profile["id"], room_name=room_name, call_type=call_type, thread_id=thread_id, max_participants=max_participants)
    if not call:
        return jsonify({"ok": False, "error": "Failed to create group call"}), 500
    return jsonify({"ok": True, "call": call})


@group_call_bp.route("/api/<call_id>/join", methods=["POST"])
@login_required
def api_join(call_id):
    profile = get_current_profile()
    ok = join_group_call(call_id, profile["id"])
    if not ok:
        return jsonify({"ok": False, "error": "Could not join call"}), 400
    call = get_group_call(call_id)
    participants = get_participants_with_profiles(call_id)
    return jsonify({"ok": True, "call": call, "participants": participants})


@group_call_bp.route("/api/<call_id>/leave", methods=["POST"])
@login_required
def api_leave(call_id):
    profile = get_current_profile()
    leave_group_call(call_id, profile["id"])
    return jsonify({"ok": True})


@group_call_bp.route("/api/<call_id>/invite", methods=["POST"])
@login_required
def api_invite(call_id):
    profile = get_current_profile()
    data = request.json or {}
    invited_profile_id = data.get("profile_id")
    if not invited_profile_id:
        return jsonify({"ok": False, "error": "profile_id required"}), 400
    invite_participant(call_id, invited_profile_id, profile["id"])
    return jsonify({"ok": True})


@group_call_bp.route("/api/<call_id>/remove", methods=["POST"])
@login_required
def api_remove(call_id):
    profile = get_current_profile()
    data = request.json or {}
    target = data.get("profile_id")
    if not target:
        return jsonify({"ok": False, "error": "profile_id required"}), 400
    ok = remove_participant(call_id, target, profile["id"])
    if not ok:
        return jsonify({"ok": False, "error": "Only host can remove participants"}), 403
    return jsonify({"ok": True})


@group_call_bp.route("/api/<call_id>/mute", methods=["POST"])
@login_required
def api_mute(call_id):
    profile = get_current_profile()
    data = request.json or {}
    target = data.get("profile_id", profile["id"])
    mute_participant(call_id, target)
    return jsonify({"ok": True})


@group_call_bp.route("/api/<call_id>/unmute", methods=["POST"])
@login_required
def api_unmute(call_id):
    profile = get_current_profile()
    data = request.json or {}
    target = data.get("profile_id", profile["id"])
    unmute_participant(call_id, target)
    return jsonify({"ok": True})


@group_call_bp.route("/api/<call_id>/raise-hand", methods=["POST"])
@login_required
def api_raise_hand(call_id):
    profile = get_current_profile()
    raise_hand(call_id, profile["id"])
    return jsonify({"ok": True})


@group_call_bp.route("/api/<call_id>/lower-hand", methods=["POST"])
@login_required
def api_lower_hand(call_id):
    profile = get_current_profile()
    lower_hand(call_id, profile["id"])
    return jsonify({"ok": True})


@group_call_bp.route("/api/<call_id>/lock", methods=["POST"])
@login_required
def api_lock(call_id):
    profile = get_current_profile()
    call = get_group_call(call_id)
    if not call or call["host_profile_id"] != profile["id"]:
        return jsonify({"ok": False, "error": "Only host can lock room"}), 403
    lock_room(call_id)
    return jsonify({"ok": True})


@group_call_bp.route("/api/<call_id>/unlock", methods=["POST"])
@login_required
def api_unlock(call_id):
    profile = get_current_profile()
    call = get_group_call(call_id)
    if not call or call["host_profile_id"] != profile["id"]:
        return jsonify({"ok": False, "error": "Only host can unlock room"}), 403
    unlock_room(call_id)
    return jsonify({"ok": True})


@group_call_bp.route("/api/<call_id>/transfer-host", methods=["POST"])
@login_required
def api_transfer_host(call_id):
    profile = get_current_profile()
    data = request.json or {}
    target = data.get("profile_id")
    if not target:
        return jsonify({"ok": False, "error": "profile_id required"}), 400
    call = get_group_call(call_id)
    if not call or call["host_profile_id"] != profile["id"]:
        return jsonify({"ok": False, "error": "Only host can transfer host"}), 403
    transfer_host(call_id, target)
    return jsonify({"ok": True})


@group_call_bp.route("/api/<call_id>/end", methods=["POST"])
@login_required
def api_end(call_id):
    profile = get_current_profile()
    call = get_group_call(call_id)
    if not call or call["host_profile_id"] != profile["id"]:
        return jsonify({"ok": False, "error": "Only host can end call"}), 403
    end_group_call(call_id)
    return jsonify({"ok": True})


@group_call_bp.route("/api/<call_id>")
@login_required
def api_get(call_id):
    call = get_group_call(call_id)
    if not call:
        return jsonify({"ok": False, "error": "Call not found"}), 404
    participants = get_participants_with_profiles(call_id)
    return jsonify({"ok": True, "call": call, "participants": participants})


@group_call_bp.route("/api/<call_id>/participants")
@login_required
def api_participants(call_id):
    participants = get_participants_with_profiles(call_id)
    return jsonify({"ok": True, "participants": participants})


@group_call_bp.route("/api/history")
@login_required
def api_history():
    profile = get_current_profile()
    limit = request.args.get("limit", 50, type=int)
    history = get_group_call_history(profile["id"], limit=limit)
    return jsonify({"ok": True, "history": history})
