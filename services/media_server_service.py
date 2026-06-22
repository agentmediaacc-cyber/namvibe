import base64
import hashlib
import hmac
import json
import logging
import os
import time
import uuid

logger = logging.getLogger(__name__)

RTMP_SERVER_URL = os.environ.get("RTMP_SERVER_URL", "")
MEDIA_SERVER_URL = os.environ.get("MEDIA_SERVER_URL", "")
LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "")


def _detect_backend():
    backends = []
    if RTMP_SERVER_URL:
        backends.append("rtmp")
    if MEDIA_SERVER_URL:
        backends.append("mediamtx")
    if LIVEKIT_URL:
        backends.append("livekit")
    return backends


def _capabilities():
    backends = _detect_backend()
    caps = {
        "broadcast": False,
        "webrtc_broadcast": False,
        "rtmp_ingest": False,
        "recording": False,
        "transcoding": False,
        "replay": False,
        "clipping": False,
    }
    for b in backends:
        if b == "livekit":
            caps.update({
                "broadcast": True,
                "webrtc_broadcast": True,
                "recording": True,
                "transcoding": True,
                "replay": True,
                "clipping": True,
            })
        elif b == "mediamtx":
            caps.update({
                "broadcast": True,
                "rtmp_ingest": True,
                "recording": True,
            })
        elif b == "rtmp":
            caps.update({
                "broadcast": True,
                "rtmp_ingest": True,
            })
    return caps


def is_live_streaming_ready():
    backends = _detect_backend()
    caps = _capabilities()
    total = len(caps)
    active = sum(1 for v in caps.values() if v)
    if not backends:
        return {
            "status": "missing",
            "detail": "No RTMP/LiveKit/media server configured. Set RTMP_SERVER_URL, MEDIA_SERVER_URL, or LIVEKIT_URL.",
            "backends": backends,
            "capabilities": caps,
            "active_capabilities": active,
            "total_capabilities": total,
        }
    ratio = active / total if total else 0
    if ratio >= 0.75:
        status = "ready"
    elif ratio >= 0.3:
        status = "partial"
    else:
        status = "missing"
    return {
        "status": status,
        "backends": backends,
        "capabilities": caps,
        "active_capabilities": active,
        "total_capabilities": total,
    }


def get_media_server_url():
    return LIVEKIT_URL or MEDIA_SERVER_URL or RTMP_SERVER_URL


def get_rtmp_ingest_url():
    if RTMP_SERVER_URL:
        return RTMP_SERVER_URL
    if MEDIA_SERVER_URL:
        return f"rtmp://{MEDIA_SERVER_URL}/live"
    return None


def get_livekit_config():
    if not LIVEKIT_URL:
        return None
    return {
        "url": LIVEKIT_URL,
        "api_key": LIVEKIT_API_KEY,
        "api_secret": bool(LIVEKIT_API_SECRET),
    }


def get_livekit_health():
    if not LIVEKIT_URL:
        return {
            "status": "missing",
            "livekit_url": bool(LIVEKIT_URL),
            "livekit_api_key": bool(LIVEKIT_API_KEY),
            "livekit_api_secret": bool(LIVEKIT_API_SECRET),
        }
    missing = []
    if not LIVEKIT_API_KEY:
        missing.append("LIVEKIT_API_KEY")
    if not LIVEKIT_API_SECRET:
        missing.append("LIVEKIT_API_SECRET")
    return {
        "status": "partial" if missing else "ready",
        "livekit_url": bool(LIVEKIT_URL),
        "livekit_api_key": bool(LIVEKIT_API_KEY),
        "livekit_api_secret": bool(LIVEKIT_API_SECRET),
        "missing_env_vars": missing,
        "detail": f"Missing: {', '.join(missing)}" if missing else None,
    }


def livekit_configured():
    return bool(LIVEKIT_URL) and bool(LIVEKIT_API_KEY) and bool(LIVEKIT_API_SECRET)


def _b64_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _livekit_jwt(payload):
    header = _b64_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64_encode(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(LIVEKIT_API_SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    return f"{header}.{body}.{_b64_encode(sig)}"


def generate_livekit_token(identity, room_name, participant_name=None, metadata=None, can_publish=True, can_subscribe=True):
    if not livekit_configured():
        return None
    now = int(time.time())
    video_grants = {
        "roomCreate": False,
        "roomJoin": True,
        "canPublish": can_publish,
        "canSubscribe": can_subscribe,
        "canPublishData": can_publish,
        "room": room_name,
    }
    payload = {
        "exp": now + 3600,
        "iat": now,
        "nbf": now,
        "iss": LIVEKIT_API_KEY,
        "sub": identity,
        "jti": str(uuid.uuid4()),
        "video": video_grants,
        "name": participant_name or identity,
        "identity": identity,
    }
    if metadata:
        payload["metadata"] = json.dumps(metadata) if isinstance(metadata, dict) else metadata
    return _livekit_jwt(payload)


def create_livekit_creator_token(profile_id, room_name, display_name=None):
    return generate_livekit_token(
        identity=str(profile_id),
        room_name=room_name,
        participant_name=display_name or str(profile_id),
        can_publish=True,
        can_subscribe=True,
    )


def create_livekit_viewer_token(profile_id, room_name, display_name=None):
    return generate_livekit_token(
        identity=str(profile_id),
        room_name=room_name,
        participant_name=display_name or str(profile_id),
        can_publish=False,
        can_subscribe=True,
    )
