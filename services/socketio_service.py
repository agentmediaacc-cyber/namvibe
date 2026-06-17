
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
from services.redis_service import _REDIS_URL, redis_available, get_redis, log_redis_warning

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
    
    # Disable queue during testing as SocketIOTestClient doesn't support it
    if not app.config.get("TESTING") and redis_url:
        mgr = redis_url
        print(f"[socketio] SCALABLE PRODUCTION MODE: Using Redis manager at {redis_url[:20]}...")
    else:
        if app.config.get("TESTING"):
            print("[socketio] Test mode: Skipping Redis manager")
        else:
            log_redis_warning("redis_socketio_fallback", "[socketio] WARNING: Running in SINGLE-NODE mode. For production with multiple users, configure REDIS_URL and restart.")

    # Determine async_mode: prefer gevent when gevent-websocket is available
    # (fixes Android APK websocket crash vs threading fallback)
    async_mode = None
    try:
        import geventwebsocket
        async_mode = 'gevent'
        print(f"[socketio] Using gevent async_mode (websocket supported)")
    except ImportError:
        print("[socketio] gevent-websocket not installed. Falling back to 'threading' mode (polling only).")
        async_mode = 'threading'

    socketio.init_app(
        app,
        message_queue=mgr,
        cors_allowed_origins="*",
        async_mode=async_mode,
        ping_timeout=20,
        ping_interval=10,
        engineio_logger=False
    )
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

def cleanup_stale_sockets():
    """Placeholder for background socket cleanup if using custom state."""
    pass
