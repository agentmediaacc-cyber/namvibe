#!/usr/bin/env python3
"""Test premium calling experience - checks routes, services, JS, templates, CSS."""
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def emit(status, name, detail=""):
    print(f"{status} [{name}] {detail}")
    return status == "PASS"


def check(name, condition, detail, failures):
    emit("PASS" if condition else "FAIL", name, detail)
    if not condition:
        failures.append(f"{name}: {detail}")


def main():
    failures = []

    # ── Imports ──
    try:
        cr = importlib.import_module("api_routes.call_routes")
        emit("PASS", "import_call_routes", "api_routes.call_routes imported")
    except Exception as error:
        emit("FAIL", "import_call_routes", str(error))
        return 1

    try:
        cs = importlib.import_module("services.call_service")
        emit("PASS", "import_call_service", "services.call_service imported")
    except Exception as error:
        emit("FAIL", "import_call_service", str(error))
        return 1

    try:
        ws = importlib.import_module("services.webrtc_call_service")
        emit("PASS", "import_webrtc_call_service", "services.webrtc_call_service imported")
    except Exception as error:
        emit("FAIL", "import_webrtc_call_service", str(error))
        return 1

    try:
        so = importlib.import_module("services.socketio_service")
        emit("PASS", "import_socketio_service", "services.socketio_service imported")
    except Exception as error:
        emit("FAIL", "import_socketio_service", str(error))
        return 1

    try:
        rg = importlib.import_module("services.relationship_gate_service")
        emit("PASS", "import_relationship_gate", "services.relationship_gate_service imported")
    except Exception as error:
        emit("FAIL", "import_relationship_gate", str(error))
        return 1

    # ── Route endpoints ──
    routes_text = (ROOT / "api_routes/call_routes.py").read_text(encoding="utf-8")

    check("route_start", '"/api/start", methods=["POST"]' in routes_text or '"/api/calls/start"' in routes_text,
          "WebRTC call start API route registered", failures)
    check("route_accept", '"/api/<call_id>/accept"' in routes_text or '"/api/calls/<call_id>/answer"' in routes_text,
          "call accept route registered", failures)
    check("route_reject", '"/api/<call_id>/reject"' in routes_text,
          "call reject route registered", failures)
    check("route_cancel", '"/api/<call_id>/cancel"' in routes_text,
          "call cancel route registered", failures)
    check("route_end", '"/api/<call_id>/end"' in routes_text,
          "call end route registered", failures)
    check("route_mute", '/api/<call_id>/mute" methods=["POST"]' in routes_text or '/mute"' in routes_text,
          "mute route registered", failures)
    check("route_camera", '/api/<call_id>/camera" methods=["POST"]' in routes_text or '/camera"' in routes_text,
          "camera toggle route registered", failures)
    check("route_speaker", '/api/<call_id>/speaker" methods=["POST"]' in routes_text or '/speaker"' in routes_text,
          "speaker toggle route registered", failures)
    check("route_ice_servers", '"/api/ice-servers"' in routes_text or '"/api/calls/ice-servers"' in routes_text,
          "ICE servers route registered", failures)
    check("route_history", '"/api/history"' in routes_text or '"/api/logs"' in routes_text,
          "call history route registered", failures)
    check("route_missed_count", '"/api/missed-count"' in routes_text,
          "missed call count route registered", failures)
    check("route_mark_seen", '"/api/mark-missed-seen"' in routes_text,
          "mark missed seen route registered", failures)
    check("route_notifications", '"/api/notifications"' in routes_text,
          "call notifications route registered", failures)
    check("route_diagnostics", '"/api/diagnostics"' in routes_text,
          "call diagnostics route registered", failures)
    check("route_invite", '"/api/<call_id>/invite"' in routes_text or '/invite"' in routes_text,
          "invite participant route registered", failures)
    check("route_start_direct", '/start/<profile_id>/<call_type>' in routes_text,
          "direct call start route registered", failures)
    check("route_group_start", '/group/start' in routes_text,
          "group call start route registered", failures)
    check("route_call_view", '/<call_id>/view' in routes_text,
          "call view route registered", failures)
    check("route_call_view_end", '/<call_id>/end"' in routes_text,
          "call end form route registered", failures)

    # ── Service functions ──
    check("svc_call_start", callable(getattr(cs, "start_call", None)),
          "call_service.start_call is callable", failures)
    check("svc_call_answer", callable(getattr(cs, "answer_call", None)),
          "call_service.answer_call is callable", failures)
    check("svc_call_end", callable(getattr(cs, "end_call", None)),
          "call_service.end_call is callable", failures)
    check("svc_call_reject", callable(getattr(cs, "reject_call", None)),
          "call_service.reject_call is callable", failures)
    check("svc_list_recent", callable(getattr(cs, "list_recent_calls", None)),
          "call_service.list_recent_calls is callable", failures)

    check("ws_create_call", callable(getattr(ws, "create_call", None)),
          "webrtc_call_service.create_call is callable", failures)
    check("ws_accept_call", callable(getattr(ws, "accept_call", None)),
          "webrtc_call_service.accept_call is callable", failures)
    check("ws_reject_call", callable(getattr(ws, "reject_call", None)),
          "webrtc_call_service.reject_call is callable", failures)
    check("ws_end_call", callable(getattr(ws, "end_call", None)),
          "webrtc_call_service.end_call is callable", failures)
    check("ws_get_call", callable(getattr(ws, "get_call", None)),
          "webrtc_call_service.get_call is callable", failures)
    check("ws_get_active_call", callable(getattr(ws, "get_active_call", None)),
          "webrtc_call_service.get_active_call is callable", failures)
    check("ws_get_call_history", callable(getattr(ws, "get_call_history", None)),
          "webrtc_call_service.get_call_history is callable", failures)
    check("ws_get_call_logs", callable(getattr(ws, "get_call_logs", None)),
          "webrtc_call_service.get_call_logs is callable", failures)
    check("ws_get_missed_count", callable(getattr(ws, "get_missed_call_count", None)),
          "webrtc_call_service.get_missed_call_count is callable", failures)
    check("ws_get_call_participants", callable(getattr(ws, "get_call_participants", None)),
          "webrtc_call_service.get_call_participants is callable", failures)
    check("ws_mark_reconnecting", callable(getattr(ws, "mark_call_reconnecting", None)),
          "webrtc_call_service.mark_call_reconnecting is callable", failures)
    check("ws_mark_failed", callable(getattr(ws, "mark_call_failed", None)),
          "webrtc_call_service.mark_call_failed is callable", failures)
    check("ws_invite_participant", callable(getattr(ws, "invite_participant", None)),
          "webrtc_call_service.invite_participant is callable", failures)
    check("ws_update_participant_state", callable(getattr(ws, "update_participant_state", None)),
          "webrtc_call_service.update_participant_state is callable", failures)
    check("ws_get_call_notifications", callable(getattr(ws, "get_call_notifications", None)),
          "webrtc_call_service.get_call_notifications is callable", failures)
    check("ws_mark_notifications_seen", callable(getattr(ws, "mark_notifications_seen", None)),
          "webrtc_call_service.mark_notifications_seen is callable", failures)

    check("so_emit_to_profile", callable(getattr(so, "emit_to_profile", None)),
          "socketio_service.emit_to_profile is callable", failures)
    check("so_profile_room", callable(getattr(so, "profile_room", None)),
          "socketio_service.profile_room is callable", failures)
    check("so_thread_room", callable(getattr(so, "thread_room", None)),
          "socketio_service.thread_room is callable", failures)

    check("rg_can_call", callable(getattr(rg, "can_call", None)),
          "relationship_gate_service.can_call is callable", failures)
    check("rg_can_message", callable(getattr(rg, "can_message", None)),
          "relationship_gate_service.can_message is callable", failures)

    # ── Template checks ──
    call_overlay = (ROOT / "templates/calls/call_overlay.html").read_text(encoding="utf-8")
    thread_template = (ROOT / "templates/messages/thread.html").read_text(encoding="utf-8")

    check("tpl_incoming", 'call-overlay-incoming' in call_overlay, "call_overlay has incoming overlay", failures)
    check("tpl_outgoing", 'call-overlay-outgoing' in call_overlay, "call_overlay has outgoing overlay", failures)
    check("tpl_connected", 'call-overlay-connected' in call_overlay, "call_overlay has connected overlay", failures)
    check("tpl_reconnecting", 'call-overlay-reconnecting' in call_overlay, "call_overlay has reconnecting overlay", failures)
    check("tpl_swipe", 'call-swipe-container' in call_overlay, "call_overlay has swipe container", failures)
    check("tpl_quality_badge", 'call-quality-badge' in call_overlay, "call_overlay has quality badge", failures)
    check("tpl_screen_share_btn", 'call-screen-share-btn' in call_overlay, "call_overlay has screen share button", failures)
    check("tpl_caller_avatar", 'caller-avatar-lg' in call_overlay, "call_overlay has caller avatar", failures)
    check("tpl_caller_name", 'data-caller-name' in call_overlay, "call_overlay has caller name data attr", failures)

    check("tpl_thread_overlay", 'id="call-overlay"' in thread_template, "thread template has call overlay", failures)
    check("tpl_thread_controls", 'toggleMute' in thread_template and 'toggleCamera' in thread_template and 'toggleSpeaker' in thread_template,
          "thread template has call control handlers", failures)
    check("tpl_thread_pip", 'toggleCallPiP' in thread_template, "thread template has PiP handler", failures)
    check("tpl_thread_participant_chips", 'participant-chips' in thread_template, "thread template has participant chips", failures)

    # ── JS checks ──
    webrtc_js = (ROOT / "static/js/webrtc_calls.js").read_text(encoding="utf-8")

    check("js_wstartcall", "wStartCall" in webrtc_js, "webrtc_calls.js has wStartCall", failures)
    check("js_waccept", "wAcceptCall" in webrtc_js, "webrtc_calls.js has wAcceptCall", failures)
    check("js_wreject", "wRejectCall" in webrtc_js, "webrtc_calls.js has wRejectCall", failures)
    check("js_wend", "wEndCall" in webrtc_js, "webrtc_calls.js has wEndCall", failures)
    check("js_wmute", "wToggleMute" in webrtc_js, "webrtc_calls.js has wToggleMute", failures)
    check("js_wcamera", "wToggleCamera" in webrtc_js, "webrtc_calls.js has wToggleCamera", failures)
    check("js_wspeaker", "wToggleSpeaker" in webrtc_js, "webrtc_calls.js has wToggleSpeaker", failures)
    check("js_wscreenshare", "wToggleScreenShare" in webrtc_js, "webrtc_calls.js has wToggleScreenShare", failures)
    check("js_wswipecamera", "wSwitchCamera" in webrtc_js, "webrtc_calls.js has wSwitchCamera", failures)
    check("js_pip", "toggleCallPiP" in webrtc_js, "webrtc_calls.js has toggleCallPiP", failures)
    check("js_restart_ice", "wRestartICE" in webrtc_js, "webrtc_calls.js has wRestartICE", failures)
    check("js_call_timer", "startCallTimer" in webrtc_js, "webrtc_calls.js has startCallTimer", failures)
    check("js_ringtone", "startRingtone" in webrtc_js, "webrtc_calls.js has ringtone", failures)
    check("js_ringback", "startRingbackTone" in webrtc_js, "webrtc_calls.js has ringback tone", failures)
    check("js_swipe_answer", "initSwipeToAnswer" in webrtc_js, "webrtc_calls.js has swipe-to-answer", failures)
    check("js_quality_display", "updateQualityDisplay" in webrtc_js, "webrtc_calls.js has quality display", failures)
    check("js_missed_badge", "wUpdateMissedCallBadge" in webrtc_js, "webrtc_calls.js has missed badge", failures)
    check("js_call_history", "wLoadCallHistory" in webrtc_js, "webrtc_calls.js has call history", failures)
    check("js_participant_chips", "wRenderParticipantChips" in webrtc_js, "webrtc_calls.js has participant chips", failures)
    check("js_failed_reason", "showCallFailedReason" in webrtc_js, "webrtc_calls.js has failed reason", failures)
    check("js_quality_monitor", "wMonitorQuality" in webrtc_js, "webrtc_calls.js has quality monitor", failures)
    check("js_reconnecting_phase50", "showReconnectingOverlayPhase50" in webrtc_js, "webrtc_calls.js has Phase50 reconnecting", failures)
    check("js_wredial", "wRedial" in webrtc_js, "webrtc_calls.js has redial", failures)
    check("js_wmarkmissedseen", "wMarkMissedSeen" in webrtc_js, "webrtc_calls.js has mark missed seen", failures)

    # ── CSS checks ──
    pro_css = (ROOT / "static/css/namvibe_calls_pro.css").read_text(encoding="utf-8")
    calls_css = (ROOT / "static/css/calls.css").read_text(encoding="utf-8")

    check("css_overlay", ".call-overlay" in pro_css, "pro CSS has .call-overlay", failures)
    check("css_controls", ".call-control-btn" in pro_css, "pro CSS has .call-control-btn", failures)
    check("css_video_container", ".call-video-container" in pro_css, "pro CSS has .call-video-container", failures)
    check("css_local_video", ".call-local-video" in pro_css, "pro CSS has .call-local-video", failures)
    check("css_timer", ".call-timer" in pro_css, "pro CSS has .call-timer", failures)
    check("css_incoming_actions", ".call-incoming-actions" in pro_css, "pro CSS has .call-incoming-actions", failures)
    check("css_reconnecting", ".call-reconnecting-text" in pro_css, "pro CSS has .call-reconnecting-text", failures)
    check("css_ringtone_unlock", ".call-ringtone-unlock" in pro_css, "pro CSS has .call-ringtone-unlock", failures)
    check("css_swipe_anim", "@keyframes call-fade-in" in pro_css, "pro CSS has call-fade-in keyframes", failures)
    check("css_screen_share", "data-screen-sharing" in pro_css, "pro CSS has screen share styles", failures)
    check("css_quality_badge", ".call-quality-badge" in pro_css, "pro CSS has quality badge styles", failures)
    check("css_avatar_ring", "avatar-ring-pulse" in pro_css, "pro CSS has avatar ring pulse animation", failures)
    check("css_mini_draggable", "phase54-mini-call" in pro_css, "pro CSS has mini call styles", failures)

    check("css_calls_stage", ".call-stage" in calls_css, "calls.css has .call-stage", failures)
    check("css_calls_controls", ".call-controls" in calls_css, "calls.css has .call-controls", failures)
    check("css_calls_target", ".call-target-card" in calls_css, "calls.css has .call-target-card", failures)

    # ── Outcome ──
    if failures:
        print(f"\nFAIL ({len(failures)} checks failed)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nPASS (all checks passed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
