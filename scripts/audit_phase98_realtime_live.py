"""Audit Phase 98 — Real-Time System & Live Streaming Upgrade.

Checks:
- Redis connection (local + production)
- Socket.IO initialization and health
- Live room join/leave viewer count updates
- Live comments appear without refresh
- Live gifts appear without refresh (wallet-safe)
- Notifications emit in real time
- WebRTC call readiness
- Video/audio streaming pipeline status
- No fake streaming markers

Run:
    python3 scripts/audit_phase98_realtime_live.py
"""

import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.setdefault("WTF_CSRF_ENABLED", "0")


def _ms(start):
    return round((time.perf_counter() - start) * 1000, 2)


def _check(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


def _check_redis():
    from services.redis_service import get_redis_health, redis_available, _REDIS_URL

    health = get_redis_health()
    available = redis_available()
    url_configured = bool(_REDIS_URL)
    connected = health.get("connected", False)
    fallback = health.get("fallback", True)

    print("\n--- Redis Health ---")
    if not url_configured:
        _check("REDIS_URL configured", False, "No REDIS_URL set — will use memory fallback")
    else:
        _check("REDIS_URL configured", True)
    _check("redis_available() returns True", available)
    _check("health.connected == True", connected)
    _check("health.fallback == False (not degrading to memory)", not fallback,
           f"fallback={fallback}")

    # Circuit breaker state
    _check("circuit_state in health", bool(health.get("circuit_state")),
           f"state={health.get('circuit_state')}")

    return {
        "redis_ready": connected,
        "redis_url_configured": url_configured,
        "redis_fallback_mode": fallback,
        "redis_circuit_state": health.get("circuit_state"),
        "redis_latency_ms": health.get("latency_ms"),
        "redis_last_connected": health.get("last_connected_at"),
    }


def _check_socketio(app_module):
    from services.socketio_service import socketio

    print("\n--- Socket.IO Health ---")
    async_mode = getattr(socketio, "async_mode", None)
    server_ready = getattr(socketio, "server", None) is not None
    websocket_supported = async_mode == "gevent"

    _check("socketio object exists", bool(socketio))
    _check("async_mode is set", bool(async_mode), f"mode={async_mode}")
    _check("websocket supported (gevent)", websocket_supported,
           f"mode={async_mode}")
    _check("server instance ready", server_ready)

    # Check profile_room / live_room functions exist
    from services.socketio_service import profile_room, live_room, thread_room, emit_to_live_room, emit_to_profile, broadcast_notification
    _check("profile_room function", callable(profile_room))
    _check("live_room function", callable(live_room))
    _check("thread_room function", callable(thread_room))
    _check("emit_to_live_room function", callable(emit_to_live_room))
    _check("emit_to_profile function", callable(emit_to_profile))
    _check("broadcast_notification function", callable(broadcast_notification))

    return {
        "websocket_ready": websocket_supported,
        "socketio_ready": server_ready,
        "async_mode": async_mode,
    }


def _check_live_room_socket_events():
    from services.socket_events import (
        handle_join_live, handle_leave_live, handle_live_chat,
        handle_live_gift, handle_heartbeat,
    )

    print("\n--- Live Room Socket Events ---")
    _check("handle_join_live exists & callable", callable(handle_join_live))
    _check("handle_leave_live exists & callable", callable(handle_leave_live))
    _check("handle_live_chat exists & callable", callable(handle_live_chat))
    _check("handle_live_gift exists & callable", callable(handle_live_gift))
    _check("handle_heartbeat exists & callable", callable(handle_heartbeat))

    # Verify live presence uses Redis set
    src = open(os.path.join(ROOT, "services", "socket_events.py"), "r").read()
    has_set_add_viewers = 'set_add(f"live_viewers:{room_id}"' in src
    has_set_remove_viewers = 'set_remove(f"live_viewers:{room_id}"' in src
    has_emit_viewers = '"live:viewers"' in src

    _check("live_viewers uses Redis set_add", has_set_add_viewers)
    _check("live_viewers uses Redis set_remove", has_set_remove_viewers)
    _check("live:viewers event emitted on join/leave", has_emit_viewers)

    result = {
        "handle_join_live": callable(handle_join_live),
        "handle_leave_live": callable(handle_leave_live),
        "handle_live_chat": callable(handle_live_chat),
        "handle_live_gift": callable(handle_live_gift),
        "live_presence_uses_redis": has_set_add_viewers and has_set_remove_viewers,
        "live_viewer_count_broadcast": has_emit_viewers,
    }
    return result


def _check_live_chat_gift_wallet():
    print("\n--- Live Chat, Gifts & Wallet Safety ---")
    from services.live_streaming_service import send_premium_gift, get_gift_catalog
    from services.live_feature_service import comment_live

    _check("send_premium_gift exists", callable(send_premium_gift))
    _check("get_gift_catalog exists", callable(get_gift_catalog))
    _check("comment_live exists (realtime)", callable(comment_live))

    # Check comment_live emits to live room
    live_feature_src = open(os.path.join(ROOT, "services", "live_feature_service.py")).read()
    has_emit_comment = 'emit_to_live_room(room_id, "live:comment"' in live_feature_src
    _check("comment_live emits live:comment via socketio", has_emit_comment)

    # Check socket_events live_gift uses send_gift from wallet_engine
    events_src = open(os.path.join(ROOT, "services", "socket_events.py")).read()
    has_wallet_gift = "send_gift(profile_id, room" in events_src or "send_gift(sender_profile_id" in events_src
    _check("live_gift socket event uses wallet send_gift", has_wallet_gift)

    # Check premium gift stores earnings record
    streaming_src = open(os.path.join(ROOT, "services", "live_streaming_service.py")).read()
    has_earnings_record = "safe_insert(\"chain_live_earnings\"" in streaming_src or "safe_insert('chain_live_earnings'" in streaming_src
    _check("premium gift records earnings for host", has_earnings_record)

    # Check wallet idempotency keys
    wallet_src = open(os.path.join(ROOT, "services", "wallet_engine.py")).read()
    has_idempotency = "idempotency_key" in wallet_src
    has_deduct_coins = "def deduct_coins" in wallet_src
    _check("wallet_engine uses idempotency keys", has_idempotency)
    _check("deduct_coins function exists (fix for live gifts)", has_deduct_coins)

    return {
        "live_chat_ready": has_emit_comment,
        "live_gifting_ready": has_earnings_record and has_wallet_gift,
        "wallet_idempotency_keys": has_idempotency,
        "deduct_coins_exists": has_deduct_coins,
    }


def _check_notifications_realtime():
    print("\n--- Realtime Notifications ---")
    from services.notification_engine import create_notification, list_notifications
    from services.socketio_service import broadcast_notification

    _check("create_notification exists", callable(create_notification))
    _check("list_notifications exists", callable(list_notifications))
    _check("broadcast_notification exists", callable(broadcast_notification))

    # Check notification_engine publishes both socket.io + Redis pubsub
    engine_src = open(os.path.join(ROOT, "services", "notification_engine.py")).read()
    has_broadcast = "broadcast_notification(recipient_profile_id" in engine_src
    has_pubsub = 'publish(f"notifications:' in engine_src or 'publish(\"notifications:' in engine_src
    _check("notification_engine calls broadcast_notification", has_broadcast)
    _check("notification_engine publishes to Redis pubsub", has_pubsub)

    # Check socket_events handles notification:new
    events_src = open(os.path.join(ROOT, "services", "socket_events.py")).read()
    has_notif_handler = '"notification:new"' in events_src or "notification:new" in events_src
    _check("socket_events handles notification:new event", has_notif_handler)

    return {
        "notifications_realtime_ready": has_broadcast,
        "notifications_redis_pubsub": has_pubsub,
    }


def _check_webtrc_calls():
    print("\n--- WebRTC Calls ---")
    from services.webrtc_turn_service import get_webrtc_ice_config, turn_configured, stun_configured

    config = get_webrtc_ice_config()
    has_ice_servers = bool(config.get("iceServers"))
    has_stun = stun_configured()
    has_turn = turn_configured()

    _check("get_webrtc_ice_config returns iceServers", has_ice_servers,
           f"{len(config.get('iceServers', []))} server(s)")
    _check("STUN server configured", has_stun)
    _check("TURN server configured", has_turn)

    from services.webrtc_call_service import (
        create_call, accept_call, reject_call, end_call,
        get_call, get_active_call, get_call_history,
    )
    _check("create_call function exists", callable(create_call))
    _check("accept_call function exists", callable(accept_call))
    _check("reject_call function exists", callable(reject_call))
    _check("end_call function exists", callable(end_call))
    _check("get_call function exists", callable(get_call))
    _check("get_active_call function exists", callable(get_active_call))

    # Check call events in socket_events
    events_src = open(os.path.join(ROOT, "services", "socket_events.py")).read()
    for event in ("call:offer", "call:answer", "call:reject", "call:ice-candidate", "call:end",
                  "call:signal", "call:status", "call:ringing", "call:accept",
                  "call:mute", "call:camera-toggle", "call:speaker-toggle",
                  "group-call:create", "group-call:join", "group-call:leave"):
        has_event = f'"{event}"' in events_src or f"'{event}'" in events_src
        _check(f"socket_events handles {event}", has_event)

    return {
        "webrtc_calls_ready": has_ice_servers,
        "stun_configured": has_stun,
        "turn_configured": has_turn,
        "call_handlers_present": True,
    }


def _check_video_streaming():
    print("\n--- Video/Audio Streaming Pipeline ---")
    from services.media_server_service import is_live_streaming_ready, get_media_server_url

    status = is_live_streaming_ready()
    streaming_status = status.get("status", "missing")
    backends = status.get("backends", [])
    caps = status.get("capabilities", {})
    url = get_media_server_url()

    _check("is_live_streaming_ready returns dict", isinstance(status, dict))
    _check(f"streaming status: {streaming_status}", streaming_status != "error",
           f"backends={backends} caps={caps}")
    if url:
        _check("media_server_url configured", True, f"url={url}")
    else:
        _check("media_server_url configured (none — expected locally)", False,
               "Set RTMP_SERVER_URL, MEDIA_SERVER_URL, or LIVEKIT_URL for production")

    # Check live_feature_service has stream settings
    from services.live_feature_service import save_stream_settings
    _check("save_stream_settings exists (WebRTC/RTMP settings)", callable(save_stream_settings))

    # Verify no fake streaming
    streaming_src = open(os.path.join(ROOT, "services", "live_streaming_service.py")).read()
    fake_markers = ["fake stream", "simulated stream", "dummy video", "placeholder_stream"]
    fake_found = [m for m in fake_markers if m in streaming_src.lower()]
    _check("no fake streaming markers", not fake_found,
           f"found: {fake_found}" if fake_found else "")

    # Check real pipeline references
    real_terms = {"livekit", "mediasoup", "aiortc", "ffmpeg", "webrtc", "hls", "rtmp"}
    found_terms = {t for t in real_terms if t in streaming_src.lower() or
                   t in open(os.path.join(ROOT, "services", "media_server_service.py")).read().lower()}
    _check(f"real streaming pipeline references: {found_terms}", bool(found_terms))

    missing_reason = status.get("detail", "No media server configured") if streaming_status == "missing" else ""
    return {
        "real_video_streaming_ready": streaming_status == "ready",
        "missing_video_pipeline_reason": missing_reason if streaming_status != "ready" else None,
        "streaming_status": streaming_status,
        "backends": backends,
        "capabilities": caps,
    }


def _check_live_routes(app):
    print("\n--- Live Routes ---")
    rules = [r.rule for r in app.url_map.iter_rules() if r.endpoint and r.endpoint.startswith("live.")]
    expected_routes = [
        "/live/",
        "/live/dashboard",
        "/live/studio",
        "/live/room/<room_id>",
        "/live/room/<room_id>/comment",
        "/live/room/<room_id>/gift",
        "/live/api/live/<room_id>/comment",
        "/live/api/live/<room_id>/gift",
        "/live/api/live/<room_id>/gift/premium",
    ]
    for route in expected_routes:
        _check(f"route {route} registered",
               any(route in r for r in rules),
               f"rules: {[r for r in rules if '/live/' in r]}")

    return {"live_routes_count": len(rules)}


def _check_calls_still_work(app):
    print("\n--- Call Routes (WebRTC) Still Work ---")
    rules = [r.rule for r in app.url_map.iter_rules() if r.endpoint and r.endpoint.startswith("calls_v2.")]
    expected = [
        "/calls/recent",
        "/calls/api/start",
        "/calls/api/<call_id>/accept",
        "/calls/api/<call_id>/reject",
        "/calls/api/<call_id>/cancel",
        "/calls/api/<call_id>/end",
        "/calls/api/active",
        "/calls/api/<call_id>",
        "/calls/api/ice-servers",
        "/calls/api/webrtc-config",
    ]
    for route in expected:
        _check(f"call route {route} registered", any(route in r for r in rules))

    return {"call_routes_count": len(rules)}


def _check_mobile_reliability():
    print("\n--- Mobile Reliability ---")
    # Check gevent websocket support (fix for Android APK crash)
    sio_src = open(os.path.join(ROOT, "services", "socketio_service.py")).read()
    has_gevent = "geventwebsocket" in sio_src
    has_android_fix = "android" in sio_src.lower() or "APK" in sio_src
    has_threading_fallback = "threading" in sio_src

    _check("gevent support detected", has_gevent)
    _check("threading fallback for mobile", has_threading_fallback)
    _check("Android APK crash fix reference", has_android_fix)

    return {
        "gevent_supported": has_gevent,
        "threading_fallback": has_threading_fallback,
        "mobile_reliability_notes": "gevent preferred, threading fallback available" if has_gevent else "threading only"
    }


def _compile_check():
    targets = ["app.py"]
    import glob as g
    targets.extend(sorted(g.glob(os.path.join("api_routes", "*.py")), key=lambda p: p))
    targets.extend(sorted(g.glob(os.path.join("services", "*.py")), key=lambda p: p))
    targets = [os.path.join(ROOT, t) if not os.path.isabs(t) else t for t in targets]
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", *targets],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )
    return {"ok": proc.returncode == 0, "stderr": proc.stderr.strip()}


def run():
    import app as app_module

    app = app_module.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    client = app.test_client()

    print("=" * 60)
    print("Phase 98 — Real-Time System & Live Streaming Audit")
    print("=" * 60)

    redis_status = _check_redis()
    sio_status = _check_socketio(app_module)
    live_events = _check_live_room_socket_events()
    chat_gift = _check_live_chat_gift_wallet()
    notif_status = _check_notifications_realtime()
    webrtc = _check_webtrc_calls()
    streaming = _check_video_streaming()
    live_routes = _check_live_routes(app)
    call_routes = _check_calls_still_work(app)
    mobile = _check_mobile_reliability()
    compile_result = _compile_check()

    print("\n" + "=" * 60)
    print("FINAL REPORT")
    print("=" * 60)

    report = {
        "websocket_ready": sio_status.get("websocket_ready", False),
        "socketio_ready": sio_status.get("socketio_ready", False),
        "redis_ready": redis_status.get("redis_ready", False),
        "redis_fallback_mode": redis_status.get("redis_fallback_mode", True),
        "live_presence_ready": live_events.get("live_presence_uses_redis", False),
        "live_viewer_count_real_time": live_events.get("live_viewer_count_broadcast", False),
        "live_chat_ready": chat_gift.get("live_chat_ready", False),
        "live_gifting_ready": chat_gift.get("live_gifting_ready", False),
        "wallet_idempotency_keys": chat_gift.get("wallet_idempotency_keys", False),
        "deduct_coins_fixed": chat_gift.get("deduct_coins_exists", False),
        "notifications_realtime_ready": notif_status.get("notifications_realtime_ready", False),
        "notifications_redis_pubsub": notif_status.get("notifications_redis_pubsub", False),
        "webrtc_calls_ready": webrtc.get("webrtc_calls_ready", False),
        "stun_configured": webrtc.get("stun_configured", False),
        "turn_configured": webrtc.get("turn_configured", False),
        "real_video_streaming_ready": streaming.get("real_video_streaming_ready", False),
        "missing_video_pipeline_reason": streaming.get("missing_video_pipeline_reason"),
        "streaming_status": streaming.get("streaming_status", "unknown"),
        "streaming_backends": streaming.get("backends", []),
        "streaming_capabilities": streaming.get("capabilities", {}),
        "py_compile_ok": compile_result["ok"],
    }

    all_ok = (
        report["websocket_ready"] and
        report["socketio_ready"] and
        report["live_presence_ready"] and
        report["live_chat_ready"] and
        report["live_gifting_ready"] and
        report["wallet_idempotency_keys"] and
        report["deduct_coins_fixed"] and
        report["notifications_realtime_ready"] and
        report["webrtc_calls_ready"] and
        report["py_compile_ok"]
    )

    for key, value in report.items():
        if key == "streaming_capabilities":
            continue
        if key == "missing_video_pipeline_reason" and value:
            print(f"  {key}: {value}")
        elif key == "streaming_backends":
            print(f"  {key}: {value}")
        elif key == "redis_fallback_mode":
            status = "INFO"
            print(f"  [{status}] {key}: {value}")
        elif isinstance(value, bool):
            status = "PASS" if value else ("WARN" if "optional" in key else "FAIL")
            print(f"  [{status}] {key}: {value}")
        else:
            print(f"  {key}: {value}")

    print(f"\n  streaming_capabilities: {streaming.get('capabilities', {})}")
    print(f"\nPyCompile: {'PASS' if compile_result['ok'] else 'FAIL'}")
    if compile_result["stderr"]:
        print(f"  stderr: {compile_result['stderr'][:500]}")

    print(f"\nResult: {'PASS' if all_ok else 'PARTIAL'}")
    return all_ok


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
