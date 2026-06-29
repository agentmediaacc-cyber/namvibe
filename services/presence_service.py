import time
import random
from datetime import datetime, timezone
from services.socketio_service import emit_to_profile

_PRESENCE_STATES = frozenset({
    "online", "offline", "idle", "away",
    "typing", "recording_voice", "uploading_media",
    "in_call", "viewing_profile", "watching_reel",
})

_MEMORY_PRESENCE = {}
_MEMORY_TTL = {}

_PRESENCE_TTL = 90

_PRESENCE_LABELS = {
    "online": "Online",
    "offline": "Offline",
    "idle": "Idle",
    "away": "Away",
    "typing": "Typing...",
    "recording_voice": "Recording...",
    "uploading_media": "Uploading...",
    "in_call": "On a call",
    "viewing_profile": "Online",
    "watching_reel": "Online",
}


def _redis():
    try:
        from services.redis_service import get_redis
        r = get_redis()
        if r:
            return r
    except Exception:
        pass
    return None


def _now_ts():
    return time.monotonic()


def _key(profile_id):
    return f"presence:{profile_id}"


def set_presence(profile_id, state, context=None, ttl_seconds=None):
    if state not in _PRESENCE_STATES:
        return
    ttl = ttl_seconds or _PRESENCE_TTL

    r = _redis()
    payload = {"state": state, "context": context, "updated_at": datetime.now(timezone.utc).isoformat()}

    if r:
        try:
            import json
            r.setex(_key(profile_id), ttl, json.dumps(payload))
        except Exception:
            r = None

    if not r:
        _MEMORY_PRESENCE[profile_id] = payload
        _MEMORY_TTL[profile_id] = _now_ts() + ttl

    _emit_presence_update(profile_id, payload)


def get_presence(profile_id):
    r = _redis()
    if r:
        try:
            import json
            data = r.get(_key(profile_id))
            if data:
                return json.loads(data)
        except Exception:
            r = None

    if profile_id in _MEMORY_PRESENCE:
        if _MEMORY_TTL.get(profile_id, 0) > _now_ts():
            return _MEMORY_PRESENCE[profile_id]
        _MEMORY_PRESENCE.pop(profile_id, None)
        _MEMORY_TTL.pop(profile_id, None)

    return None


def get_many_presence(profile_ids):
    if not profile_ids:
        return {}
    r = _redis()
    result = {}
    if r:
        try:
            import json
            keys = [_key(pid) for pid in profile_ids]
            vals = r.mget(keys) if hasattr(r, "mget") else [r.get(k) for k in keys]
            for pid, val in zip(profile_ids, vals):
                if val:
                    result[pid] = json.loads(val)
        except Exception:
            r = None

    for pid in profile_ids:
        if pid not in result:
            p = _MEMORY_PRESENCE.get(pid)
            if p and _MEMORY_TTL.get(pid, 0) > _now_ts():
                result[pid] = p
    return result


def clear_presence(profile_id):
    r = _redis()
    if r:
        try:
            r.delete(_key(profile_id))
        except Exception:
            pass
    _MEMORY_PRESENCE.pop(profile_id, None)
    _MEMORY_TTL.pop(profile_id, None)


def heartbeat_presence(profile_id):
    set_presence(profile_id, "online")


def presence_label(profile_id):
    p = get_presence(profile_id)
    if not p:
        return "Offline"
    state = p.get("state", "offline")
    return _PRESENCE_LABELS.get(state, "Offline")


def _emit_presence_update(profile_id, payload):
    emit_to_profile(profile_id, "presence:update", {
        "profile_id": profile_id,
        "state": payload.get("state"),
        "context": payload.get("context"),
        "label": _PRESENCE_LABELS.get(payload.get("state", ""), "Offline"),
    })


def heartbeat(profile_id):
    set_presence(profile_id, "online")


def set_online(profile_id):
    set_presence(profile_id, "online")


def set_offline(profile_id):
    set_presence(profile_id, "offline")
    clear_presence(profile_id)


def set_typing(profile_id, thread_id=None):
    set_presence(profile_id, "typing", context=thread_id)
