#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(rel_path):
    return (ROOT / rel_path).read_text(encoding="utf-8")

def check(name, ok, detail, failures):
    line = f"{'PASS' if ok else 'FAIL'} [{name}] {detail}"
    print(line)
    if not ok:
        failures.append(f"{name}: {detail}")

def main():
    failures = []

    call_routes = read("api_routes/call_routes.py")
    call_service = read("services/call_service.py")
    webrtc_service = read("services/webrtc_call_service.py")
    socketio_service = read("services/socketio_service.py")
    gate_service = read("services/relationship_gate_service.py")
    webrtc_js = read("static/js/webrtc_calls.js")
    call_overlay = read("templates/calls/call_overlay.html")
    call_pro_css = read("static/css/namvibe_calls_pro.css")
    calls_css = read("static/css/calls.css")

    check(
        "friend_gate_preserved",
        "require_friendship_or_403" in call_routes and "can_call" in call_routes,
        "call routes enforce friendship and can_call gate",
        failures,
    )
    check(
        "can_call_in_gate_service",
        "def can_call(" in gate_service,
        "relationship_gate_service has can_call function",
        failures,
    )
    check(
        "start_call_endpoint",
        '"/api/start"' in call_routes or '"/api/calls/start"' in call_routes,
        "webrtc call start API endpoint exists",
        failures,
    )
    check(
        "accept_reject_endpoints",
        "/accept" in call_routes and "/reject" in call_routes and "/end" in call_routes,
        "accept/reject/end call endpoints exist",
        failures,
    )
    check(
        "ice_servers_endpoint",
        '"/api/ice-servers"' in call_routes,
        "ICE servers config endpoint exists",
        failures,
    )
    check(
        "call_history_endpoint",
        '"/api/history"' in call_routes or '"/api/logs"' in call_routes,
        "call history/logs API endpoint exists",
        failures,
    )
    check(
        "missed_count_endpoint",
        '"/api/missed-count"' in call_routes,
        "missed call count endpoint exists",
        failures,
    )
    check(
        "mute_camera_speaker_endpoints",
        "/mute" in call_routes and "/camera" in call_routes and "/speaker" in call_routes,
        "mute/camera/speaker toggle endpoints exist",
        failures,
    )
    check(
        "screen_share_endpoint",
        "wToggleScreenShare" in webrtc_js,
        "screen share signaling exists in webrtc_calls.js",
        failures,
    )
    check(
        "reconnect_failed_endpoints",
        "/reconnect" in call_routes and "/failed" in call_routes,
        "reconnect/failed call endpoints exist",
        failures,
    )
    check(
        "call_diagnostics_endpoint",
        "/diagnostics" in call_routes,
        "call diagnostics endpoint exists",
        failures,
    )
    check(
        "missed_notification_endpoint",
        "/mark-missed-seen" in call_routes and "/notifications" in call_routes,
        "missed call seen/notification endpoints exist",
        failures,
    )
    check(
        "invite_participant_endpoint",
        "/invite" in call_routes,
        "invite participant endpoint exists",
        failures,
    )

    check(
        "webrtc_js_socket_events",
        "call:incoming" in webrtc_js and "call:offer" in webrtc_js and "call:answer" in webrtc_js,
        "webrtc_calls.js handles incoming/offer/answer socket events",
        failures,
    )
    check(
        "webrtc_js_ice_candidates",
        "call:ice-candidate" in webrtc_js,
        "webrtc_calls.js handles ICE candidate exchange",
        failures,
    )
    check(
        "webrtc_js_mute_camera",
        "wToggleMute" in webrtc_js and "wToggleCamera" in webrtc_js and "wToggleSpeaker" in webrtc_js,
        "webrtc_calls.js has mute/camera/speaker toggles",
        failures,
    )
    check(
        "webrtc_js_call_timer",
        "startCallTimer" in webrtc_js and "stopCallTimer" in webrtc_js,
        "webrtc_calls.js has call timer",
        failures,
    )
    check(
        "webrtc_js_ringtone",
        "startRingtone" in webrtc_js and "startRingbackTone" in webrtc_js and "stopRingtone" in webrtc_js,
        "webrtc_calls.js has ringtone/ringback engine",
        failures,
    )
    check(
        "webrtc_js_reconnect",
        "wRestartICE" in webrtc_js and "reconnecting" in webrtc_js and "reconnected" in webrtc_js,
        "webrtc_calls.js has ICE restart and reconnect handling",
        failures,
    )
    check(
        "webrtc_js_failed_reason",
        "showCallFailedReason" in webrtc_js,
        "webrtc_calls.js has call failed reason display",
        failures,
    )
    check(
        "webrtc_js_missed_badge",
        "wUpdateMissedCallBadge" in webrtc_js,
        "webrtc_calls.js has missed call badge update",
        failures,
    )
    check(
        "webrtc_js_call_history",
        "wLoadCallHistory" in webrtc_js and "renderCallCard" in webrtc_js,
        "webrtc_calls.js has call history rendering",
        failures,
    )
    check(
        "webrtc_js_participants",
        "wRenderParticipantChips" in webrtc_js,
        "webrtc_calls.js has participant chips rendering",
        failures,
    )
    check(
        "webrtc_js_pip",
        "toggleCallPiP" in webrtc_js,
        "webrtc_calls.js has PiP/minimize support",
        failures,
    )
    check(
        "webrtc_js_switch_camera",
        "wSwitchCamera" in webrtc_js,
        "webrtc_calls.js has camera flip",
        failures,
    )
    check(
        "webrtc_js_screen_share",
        "wToggleScreenShare" in webrtc_js and "stopScreenShare" in webrtc_js,
        "webrtc_calls.js has screen share toggle",
        failures,
    )
    check(
        "webrtc_js_swipe_answer",
        "initSwipeToAnswer" in webrtc_js and "call-swipe-track" in webrtc_js,
        "webrtc_calls.js has swipe-to-answer gesture",
        failures,
    )
    check(
        "webrtc_js_quality_display",
        "updateQualityDisplay" in webrtc_js,
        "webrtc_calls.js has quality display update",
        failures,
    )
    check(
        "webrtc_js_modals",
        "showIncomingCallModal" in webrtc_js,
        "webrtc_calls.js has incoming call modal",
        failures,
    )

    check(
        "call_overlay_incoming",
        'id="call-overlay-incoming"' in call_overlay,
        "call_overlay.html has incoming overlay",
        failures,
    )
    check(
        "call_overlay_outgoing",
        'id="call-overlay-outgoing"' in call_overlay,
        "call_overlay.html has outgoing overlay",
        failures,
    )
    check(
        "call_overlay_connected",
        'id="call-overlay-connected"' in call_overlay,
        "call_overlay.html has connected overlay",
        failures,
    )
    check(
        "call_overlay_reconnecting",
        'id="call-overlay-reconnecting"' in call_overlay,
        "call_overlay.html has reconnecting overlay",
        failures,
    )
    check(
        "call_overlay_avatar",
        'caller-avatar-lg' in call_overlay,
        "call_overlay.html has caller avatar display",
        failures,
    )
    check(
        "call_overlay_name",
        'data-caller-name' in call_overlay and 'id="caller-name-display"' in call_overlay,
        "call_overlay.html has caller name display",
        failures,
    )
    check(
        "call_overlay_swipe",
        'call-swipe-container' in call_overlay and 'call-swipe-track' in call_overlay,
        "call_overlay.html has swipe-to-answer UI",
        failures,
    )
    check(
        "call_overlay_quality",
        'call-quality-badge' in call_overlay,
        "call_overlay.html has quality badge",
        failures,
    )
    check(
        "call_overlay_screen_share_btn",
        'call-screen-share-btn' in call_overlay,
        "call_overlay.html has screen share button",
        failures,
    )
    check(
        "call_overlay_ringtone_unlock",
        'call-ringtone-unlock' in call_overlay,
        "call_overlay.html has ringtone unlock UI",
        failures,
    )
    check(
        "call_overlay_reject_btn",
        'data-call-reject' in call_overlay,
        "call_overlay.html has reject button with data attribute",
        failures,
    )
    check(
        "call_overlay_end_btn",
        'data-call-end' in call_overlay,
        "call_overlay.html has end call button",
        failures,
    )

    check(
        "call_pro_css_overlay",
        ".call-overlay" in call_pro_css,
        "namvibe_calls_pro.css has overlay styles",
        failures,
    )
    check(
        "call_pro_css_controls",
        ".call-control-btn" in call_pro_css,
        "namvibe_calls_pro.css has control button styles",
        failures,
    )
    check(
        "call_pro_css_local_video",
        ".call-local-video" in call_pro_css,
        "namvibe_calls_pro.css has local video styles",
        failures,
    )
    check(
        "call_pro_css_timer",
        ".call-timer" in call_pro_css,
        "namvibe_calls_pro.css has call timer styles",
        failures,
    )
    check(
        "call_pro_css_swipe",
        "call-swipe" in call_pro_css,
        "namvibe_calls_pro.css has swipe animation styles",
        failures,
    )
    check(
        "call_pro_css_screen_share",
        "data-screen-sharing" in call_pro_css,
        "namvibe_calls_pro.css has screen share active styles",
        failures,
    )
    check(
        "call_pro_css_mini_call",
        "phase54-mini-call" in call_pro_css,
        "namvibe_calls_pro.css has mini call draggable styles",
        failures,
    )
    check(
        "call_pro_css_quality",
        "call-quality-badge" in call_pro_css,
        "namvibe_calls_pro.css has quality badge styles",
        failures,
    )

    check(
        "socketio_service_emit_profile",
        "emit_to_profile" in socketio_service,
        "socketio_service.py has emit_to_profile",
        failures,
    )
    check(
        "socketio_service_rooms",
        "profile_room" in socketio_service and "thread_room" in socketio_service,
        "socketio_service.py has profile/thread room helpers",
        failures,
    )

    check(
        "call_service_start",
        "def start_call(" in call_service,
        "call_service.py has start_call",
        failures,
    )
    check(
        "call_service_end",
        "def end_call(" in call_service,
        "call_service.py has end_call",
        failures,
    )
    check(
        "call_service_answer_reject",
        "def answer_call(" in call_service and "def reject_call(" in call_service,
        "call_service.py has answer_call and reject_call",
        failures,
    )

    check(
        "webrtc_service_create",
        "def create_call(" in webrtc_service,
        "webrtc_call_service.py has create_call",
        failures,
    )
    check(
        "webrtc_service_accept",
        "def accept_call(" in webrtc_service,
        "webrtc_call_service.py has accept_call",
        failures,
    )
    check(
        "webrtc_service_reject",
        "def reject_call(" in webrtc_service,
        "webrtc_call_service.py has reject_call",
        failures,
    )
    check(
        "webrtc_service_end",
        "def end_call(" in webrtc_service,
        "webrtc_call_service.py has end_call",
        failures,
    )
    check(
        "webrtc_service_history",
        "def get_call_history(" in webrtc_service,
        "webrtc_call_service.py has get_call_history",
        failures,
    )
    check(
        "webrtc_service_logs",
        "def get_call_logs(" in webrtc_service,
        "webrtc_call_service.py has get_call_logs",
        failures,
    )
    check(
        "webrtc_service_missed",
        "def get_missed_call_count(" in webrtc_service,
        "webrtc_call_service.py has get_missed_call_count",
        failures,
    )
    check(
        "webrtc_service_participants",
        "def get_call_participants(" in webrtc_service,
        "webrtc_call_service.py has get_call_participants",
        failures,
    )
    check(
        "webrtc_service_reconnect",
        "def mark_call_reconnecting(" in webrtc_service,
        "webrtc_call_service.py has mark_call_reconnecting",
        failures,
    )
    check(
        "webrtc_service_failed",
        "def mark_call_failed(" in webrtc_service,
        "webrtc_call_service.py has mark_call_failed",
        failures,
    )
    check(
        "webrtc_service_relationship_gate",
        "_check_relationship_gate" in webrtc_service and "_check_blocked" in webrtc_service,
        "webrtc_call_service.py checks relationship gate and blocks",
        failures,
    )
    check(
        "webrtc_service_rate_limit",
        "_check_rate_limit" in webrtc_service,
        "webrtc_call_service.py has rate limiting",
        failures,
    )

    check(
        "thread_template_overlay",
        'id="call-overlay"' in read("templates/messages/thread.html"),
        "messages thread.html has call overlay",
        failures,
    )
    check(
        "recent_calls_template",
        "/calls/recent" in call_routes,
        "recent calls template route exists",
        failures,
    )
    check(
        "call_history_template",
        '"/history"' in call_routes,
        "call history page template route exists",
        failures,
    )
    check(
        "calls_css_stage",
        ".call-stage" in calls_css,
        "calls.css has call stage styles",
        failures,
    )
    check(
        "calls_css_controls",
        ".call-controls" in calls_css,
        "calls.css has controls styles",
        failures,
    )

    check(
        "end_call_confirm_removed",
        "window.confirm('End this call?')" not in webrtc_js,
        "webrtc_calls.js does NOT have the end-call confirm dialog",
        failures,
    )
    check(
        "no_fake_call_records",
        "fake" not in read("services/call_history_service.py").lower()[:500],
        "call history service has no fake data",
        failures,
    )

    if failures:
        print(f"\nFAIL ({len(failures)} checks failed)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nPASS (all checks passed)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
