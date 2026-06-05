import os
from flask_socketio import SocketIO, emit, join_room, leave_room
from services.circuit_breaker import CircuitBreaker
from services.redis_service import _REDIS_URL, redis_available, get_redis, log_redis_warning

socketio = SocketIO()
_SOCKET_BREAKER = CircuitBreaker("socketio_emit", failure_threshold=3, recovery_seconds=30)


def profile_room(profile_id):
    return f"profile:{profile_id}"


def thread_room(thread_id):
    return f"thread:{thread_id}"


def live_room(room_id):
    return f"live:{room_id}"

def init_socketio(app):
    """Initializes Socket.IO with Redis and optimized settings."""
    mgr = None
    # Disable queue during testing as SocketIOTestClient doesn't support it
    if not app.config.get("TESTING") and redis_available():
        mgr = _REDIS_URL
        print(f"[socketio] Scalable mode: Using Redis manager at {mgr}")
    else:
        if app.config.get("TESTING"):
            print("[socketio] Test mode: Skipping Redis manager")
        else:
            log_redis_warning("redis_socketio_fallback", "[socketio] Single-node mode: Redis unavailable")

    socketio.init_app(
        app,
        message_queue=mgr,
        cors_allowed_origins="*",
        async_mode='gevent' if os.getenv('FLASK_ENV') == 'production' else None,
        ping_timeout=20,
        ping_interval=10,
        engineio_logger=False
    )
    return socketio


def _emit_async(event, payload, room=None, include_self=True):
    def _run_emit():
        if not _SOCKET_BREAKER.allow():
            return
        try:
            socketio.emit(event, payload, room=room, include_self=include_self)
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
