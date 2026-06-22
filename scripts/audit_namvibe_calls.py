#!/usr/bin/env python3
from pathlib import Path
import importlib
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"{status}: {label}" + (f" - {detail}" if detail and not condition else ""))
    return bool(condition)


def main():
    results = []
    app_mod = importlib.import_module("app")
    routes = {rule.rule: sorted(rule.methods) for rule in app_mod.app.url_map.iter_rules()}

    call_route_src = read("api_routes/call_routes.py")
    js = read("static/js/namvibe_calls_pro.js")
    css = read("static/css/namvibe_calls_pro.css")
    call_overlay = read("templates/calls/call_overlay.html")
    history_html = read("templates/calls/history.html")
    index_html = read("templates/calls/index.html")
    socket_src = read("services/socket_events.py")
    webrtc_service = read("services/webrtc_call_service.py")
    lifecycle_src = read("services/call_lifecycle_service.py")
    history_svc = read("services/call_history_service.py")
    permission_svc = read("services/call_permission_service.py")
    migration = read("scripts/phase92_call_schema_upgrade.py")
    turn_svc = read("services/webrtc_turn_service.py")

    all_templates = call_overlay + history_html + index_html
    all_js_route = js + call_route_src + socket_src

    required_routes = [
        "/calls/",
        "/calls/history",
        "/calls/api/start",
        "/calls/api/<call_id>/accept",
        "/calls/api/<call_id>/reject",
        "/calls/api/<call_id>/cancel",
        "/calls/api/<call_id>/end",
    ]
    for route in required_routes:
        found = route in routes
        results.append(check(f"route exists {route}", found))

    # Check for route variants with different prefixes
    alt_routes = [
        "/calls/recent",
        "/calls/api/history",
        "/calls/api/calls/history",
        "/calls/api/logs",
        "/calls/api/ice-servers",
        "/calls/api/missed-count",
        "/messages/api/calls/history",
        "/messages/api/calls/start",
    ]
    for route in alt_routes:
        if route in routes:
            results.append(check(f"route exists {route}", True))

    results.append(check("call JS file exists", (ROOT / "static/js/namvibe_calls_pro.js").exists()))
    results.append(check("call CSS file exists", (ROOT / "static/css/namvibe_calls_pro.css").exists()))
    results.append(check("call overlay template exists", (ROOT / "templates/calls/call_overlay.html").exists()))
    results.append(check("call history template exists", (ROOT / "templates/calls/history.html").exists()))

    results.append(check("WebRTC offer/answer", "call:offer" in all_js_route and "call:answer" in all_js_route))
    results.append(check("ICE candidate handling", "call:ice-candidate" in all_js_route))
    results.append(check("ringtone handling", "startRinging" in js and "stopRinging" in js))
    results.append(check("busy state", "call:busy" in socket_src or "call:busy" in js))
    results.append(check("timeout handling", "CALL_TIMEOUT_SECONDS" in js or "call_timeout" in webrtc_service))
    results.append(check("accept/reject", "call:accepted" in all_js_route and "call:rejected" in all_js_route))
    results.append(check("missed call logic", "call:missed" in all_js_route))
    results.append(check("mic mute", "toggleMute" in js and "call:mute-state" in all_js_route))
    results.append(check("speaker fallback", "setSinkId" in js))
    results.append(check("camera toggle/switch", "toggleCamera" in js and "switchCamera" in js))
    results.append(check("reconnection handling", "call:reconnecting" in all_js_route and "call:reconnected" in all_js_route))
    results.append(check("call history exists", "call-history-list" in history_html or "get_call_history" in history_svc))
    results.append(check("safe media cleanup", "cleanupMedia" in js and "cleanupCall" in js))
    results.append(check("mobile safe-area", "env(safe-area-inset-bottom" in css))
    results.append(check("minimum 44px tap targets", "min-width: 44px" in css or "min-height: 44px" in css))
    results.append(check("no fake call data", "fake call" not in all_templates.lower()))
    results.append(check("no hardcoded demo users", "demo user" not in all_templates.lower() and "test user" not in all_templates.lower()))
    results.append(check("privacy/block checks", "_check_blocked" in webrtc_service or "can_start_call" in permission_svc))
    results.append(check("self-call prevented", "self_call" in lifecycle_src or "self_call_not_allowed" in webrtc_service))
    results.append(check("call history with profile data", "other_display_name" in history_svc))
    results.append(check("delete call log", "delete_call_log" in history_svc))
    results.append(check("incoming call modal", "call-overlay-incoming" in call_overlay))
    results.append(check("accept/reject buttons", "data-call-accept" in call_overlay and "data-call-reject" in call_overlay))
    results.append(check("call timer", "call-timer" in call_overlay))
    results.append(check("mute button", "call-mute-btn" in call_overlay))
    results.append(check("speaker button", "call-speaker-btn" in call_overlay))
    results.append(check("camera switch button", "call-switch-camera-btn" in call_overlay))
    results.append(check("reconnecting state", "call-overlay-reconnecting" in call_overlay))
    results.append(check("ringtone unlock prompt", "call-ringtone-unlock" in call_overlay))
    results.append(check("chain_call_logs migration", "chain_call_logs" in migration))
    results.append(check("STUN config from env", "stun:" in turn_svc or "STUN_SERVER_URL" in turn_svc))
    results.append(check("TURN config from env", "TURN_SERVER_URL" in turn_svc or "WEBRTC_TURN_URLS" in turn_svc))

    if not all(results):
        raise SystemExit(1)
    print("audit_namvibe_calls_ok")


if __name__ == "__main__":
    main()
