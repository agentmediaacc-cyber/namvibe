import os
import hashlib
from flask import Blueprint, render_template, request, jsonify, session
from services.profile_service import get_current_profile
from services.security_service import (
    create_device_session, get_device_sessions, get_device_session,
    revoke_device_session, logout_all_other_devices,
    create_security_event, get_security_events,
    trust_device, untrust_device, get_trusted_devices,
)
from api_routes.profile_routes import login_required

security_bp = Blueprint("security", __name__, url_prefix="/security")


@security_bp.route("/api/devices")
@login_required
def api_devices():
    profile = get_current_profile()
    devices = get_device_sessions(profile["id"])
    return jsonify({"ok": True, "devices": devices})


@security_bp.route("/api/device/<device_id>/revoke", methods=["POST"])
@login_required
def api_revoke_device(device_id):
    profile = get_current_profile()
    device = get_device_session(device_id)
    if not device or device["profile_id"] != profile["id"]:
        return jsonify({"ok": False, "error": "Device not found"}), 404
    revoke_device_session(device_id, profile["id"])
    create_security_event(profile["id"], "device_revoked", device_id=device_id,
                          metadata={"device_name": device.get("device_name")})
    return jsonify({"ok": True})


@security_bp.route("/api/logout-all-other-devices", methods=["POST"])
@login_required
def api_logout_all_other():
    profile = get_current_profile()
    current_id = request.json.get("current_device_id") if request.is_json else None
    logout_all_other_devices(current_id, profile["id"])
    create_security_event(profile["id"], "logout",
                          metadata={"action": "logout_all_other_devices"})
    return jsonify({"ok": True})


@security_bp.route("/api/device/<device_id>/trust", methods=["POST"])
@login_required
def api_trust_device(device_id):
    profile = get_current_profile()
    device = get_device_session(device_id)
    if not device or device["profile_id"] != profile["id"]:
        return jsonify({"ok": False, "error": "Device not found"}), 404
    trust_device(profile["id"], device_id)
    return jsonify({"ok": True})


@security_bp.route("/api/device/<device_id>/untrust", methods=["POST"])
@login_required
def api_untrust_device(device_id):
    profile = get_current_profile()
    device = get_device_session(device_id)
    if not device or device["profile_id"] != profile["id"]:
        return jsonify({"ok": False, "error": "Device not found"}), 404
    untrust_device(profile["id"], device_id)
    return jsonify({"ok": True})


@security_bp.route("/api/events")
@login_required
def api_events():
    profile = get_current_profile()
    limit = request.args.get("limit", 50, type=int)
    events = get_security_events(profile["id"], limit=limit)
    return jsonify({"ok": True, "events": events})


# ---------- Frontend Pages ----------

@security_bp.route("/devices")
@login_required
def devices_page():
    profile = get_current_profile()
    devices = get_device_sessions(profile["id"])
    trusted = get_trusted_devices(profile["id"])
    return render_template("security/devices.html", profile=profile, devices=devices, trusted_devices=trusted)


@security_bp.route("/privacy")
@login_required
def privacy_page():
    profile = get_current_profile()
    from services.security_service import get_privacy_settings
    privacy = get_privacy_settings(profile["id"])
    return render_template("security/privacy.html", profile=profile, privacy=privacy)


@security_bp.route("/events")
@login_required
def events_page():
    profile = get_current_profile()
    events = get_security_events(profile["id"], limit=100)
    return render_template("security/security_events.html", profile=profile, events=events)
