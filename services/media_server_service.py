import os
import logging

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
