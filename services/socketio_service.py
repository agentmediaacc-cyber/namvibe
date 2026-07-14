
def _json_safe_payload(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe_payload(v) for v in value]
    return value

from datetime import datetime, date
import os
import logging
import time
import random
from flask_socketio import SocketIO, emit, join_room, leave_room
from services.circuit_breaker import CircuitBreaker
from services.redis_service import _REDIS_URL, _REDIS_URL_MASKED, redis_available, get_redis, log_redis_warning
from services.logging_service import safe_print

logger = logging.getLogger(__name__)

socketio = SocketIO()
_SOCKET_BREAKER = CircuitBreaker("socketio_emit", failure_threshold=3, recovery_seconds=30)
_SOCKET_EMIT_RATE_LIMIT = {}


def profile_room(profile_id):
    return f"profile:{profile_id}"


def thread_room(thread_id):
    return f"thread:{thread_id}"


def live_room(room_id):
    return f"live:{room_id}"

def _check_emit_rate(event, room, max_per_second=100):
    now = time.time()
    key = f"{event}:{room}"
    entry = _SOCKET_EMIT_RATE_LIMIT.get(key)
    if entry and now - entry.get("ts", 0) < 1:
        entry["count"] = entry.get("count", 0) + 1
        if entry["count"] > max_per_second:
            return True
    else:
        _SOCKET_EMIT_RATE_LIMIT[key] = {"count": 1, "ts": now}
    return False


def init_socketio(app):
    """Initializes Socket.IO with Redis and optimized settings."""
    mgr = None
    redis_url = os.environ.get("REDIS_URL") or os.environ.get("REDIS_TLS_URL") or _REDIS_URL
    use_redis_mgr = os.environ.get("CHAIN_SOCKETIO_REDIS_MANAGER", "1") == "1"
    
    if not use_redis_mgr:
        safe_print("[socketio] CHAIN_SOCKETIO_REDIS_MANAGER=0 — using in-process Socket.IO (no Redis message queue)")
    elif app.config.get("TESTING"):
        safe_print("[socketio] Test mode: Skipping Redis manager")
    elif redis_url:
        mgr = redis_url
        safe_print(f"[socketio] SCALABLE PRODUCTION MODE: Using Redis manager at {_REDIS_URL_MASKED}")
    else:
        log_redis_warning("redis_socketio_fallback", "[socketio] WARNING: Running in SINGLE-NODE mode. For production with multiple users, configure REDIS_URL and restart.")

    # Determine async_mode: prefer gevent when gevent-websocket is available
    # (fixes Android APK websocket crash vs threading fallback)
    async_mode = None
    try:
        import geventwebsocket
        async_mode = 'gevent'
        safe_print(f"[socketio] Using gevent async_mode (websocket supported)")
    except ImportError:
        safe_print("[socketio] gevent-websocket not installed. Falling back to 'threading' mode (polling only).")
        async_mode = 'threading'

    init_kwargs = dict(
        cors_allowed_origins="*",
        async_mode=async_mode,
        ping_timeout=20,
        ping_interval=10,
        max_http_buffer_size=5 * 1024 * 1024,
        http_compression=True,
        engineio_logger=False,
    )
    try:
        if mgr and not redis_available():
            raise RuntimeError("Redis manager unavailable during startup")
        socketio.init_app(app, message_queue=mgr, **init_kwargs)
        register_live_room_handlers(socketio)
    except Exception as error:
        log_redis_warning("socketio_init_fallback", f"[socketio] Redis manager failed, falling back to local mode: {error}")
        socketio.init_app(app, message_queue=None, **init_kwargs)
        register_live_room_handlers(socketio)
    return socketio


def _emit_async(event, payload, room=None, include_self=True):
    def _run_emit():
        if not _SOCKET_BREAKER.allow():
            return
        if getattr(socketio, "server", None) is None:
            return
        if _check_emit_rate(event, room):
            if random.random() < 0.01:
                logger.warning(f"[socketio] Dropping {event} to {room} (rate limit)")
            return
        try:
            socketio.emit(event, _json_safe_payload(payload), room=room, include_self=include_self)
            _SOCKET_BREAKER.success()
        except Exception as error:
            _SOCKET_BREAKER.failure(error)
            log_redis_warning(f"socket_emit_{event}", f"[socketio] emit failed for {event}: {error}", interval_seconds=30)
    try:
        socketio.start_background_task(_run_emit)
    except Exception:
        _run_emit()

def emit_to_profile(profile_id, event, payload):
    """Optimized: Emits to profile room."""
    _emit_async(event, payload, room=profile_room(profile_id))

def emit_to_thread(thread_id, event, payload):
    """Optimized: Emits to thread room."""
    _emit_async(event, payload, room=thread_room(thread_id))

def emit_to_live_room(room_id, event, payload):
    """Optimized: Emits to live room."""
    _emit_async(event, payload, room=live_room(room_id))

def broadcast_notification(profile_id, payload):
    """Scalable notification broadcast."""
    emit_to_profile(profile_id, "notification:new", payload)

# ─── LIVE ROOM EVENT HANDLERS ─────────────────────────────
def register_live_room_handlers(socketio_app):
    """Registers only auxiliary live events not already secured in socket_events."""

    @socketio_app.on("live:raise_hand")
    def on_raise_hand(data):
        room_id = data.get("room_id") if isinstance(data, dict) else None
        if not room_id:
            return
        emit("live:hand_raised", data, room=live_room(room_id), include_self=False)

    @socketio_app.on("live:ring")
    def on_live_ring(data):
        target_profile_id = data.get("target_profile_id") if isinstance(data, dict) else None
        if not target_profile_id:
            return
        emit("live:incoming_call", data, room=profile_room(target_profile_id))

    @socketio_app.on("live:accept_call")
    def on_accept_call(data):
        target_profile_id = data.get("target_profile_id") if isinstance(data, dict) else None
        if not target_profile_id:
            return
        emit("live:call_accepted", data, room=profile_room(target_profile_id))

    @socketio_app.on("live:reject_call")
    def on_reject_call(data):
        target_profile_id = data.get("target_profile_id") if isinstance(data, dict) else None
        if not target_profile_id:
            return
        emit("live:call_rejected", data, room=profile_room(target_profile_id))

    @socketio_app.on("live:invite_guest")
    def on_invite_guest(data):
        target_profile_id = data.get("target_profile_id") if isinstance(data, dict) else None
        if not target_profile_id:
            return
        emit("live:guest_invited", data, room=profile_room(target_profile_id))

    @socketio_app.on("live:typing")
    def on_typing(data):
        room_id = data.get("room_id") if isinstance(data, dict) else None
        if not room_id:
            return
        emit("live:typing", data, room=live_room(room_id), include_self=False)

    @socketio_app.on("live:mute")
    def on_mute(data):
        room_id = data.get("room_id") if isinstance(data, dict) else None
        if not room_id:
            return
        emit("live:user_muted", data, room=live_room(room_id), include_self=False)

    safe_print("[socketio] Auxiliary live room event handlers registered")


def _get_sid():
    from flask import request as _req
    try:
        return _req.sid
    except Exception:
        return None


def cleanup_stale_sockets():
    pass
