"""NamVibe LiveKit Service — WebRTC SFU for group calls & live streaming"""

import os
import time
import logging
from typing import Optional

from services.env_service import get_env

logger = logging.getLogger(__name__)

LIVEKIT_API_KEY = get_env("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = get_env("LIVEKIT_API_SECRET", "")
LIVEKIT_HOST = get_env("LIVEKIT_HOST", "localhost:7880")
LIVEKIT_WS_URL = get_env("LIVEKIT_WS_URL", "ws://localhost:7880")

_ACCESS_TOKEN_CACHE = {}
_ROOM_CACHE = {}

def livekit_configured() -> bool:
    return bool(LIVEKIT_API_KEY and LIVEKIT_API_SECRET and LIVEKIT_HOST)

def get_livekit_server_info() -> dict:
    return {
        "configured": livekit_configured(),
        "host": LIVEKIT_HOST,
        "ws_url": LIVEKIT_WS_URL,
        "api_key_present": bool(LIVEKIT_API_KEY),
        "api_secret_present": bool(LIVEKIT_API_SECRET),
    }

def create_livekit_token(identity: str, room_name: str, *, 
                          can_publish: bool = True,
                          can_subscribe: bool = True,
                          ttl_seconds: int = 3600) -> Optional[str]:
    if not livekit_configured():
        logger.warning("[livekit] Not configured, cannot create token")
        return None
    try:
        from livekit.api import AccessToken, VideoGrants
        grant = VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=can_publish,
            can_subscribe=can_subscribe,
        )
        token = AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET, 
                           identity=identity, ttl=ttl_seconds)
        token.add_grant(grant)
        jwt = token.to_jwt()
        cache_key = f"{identity}:{room_name}"
        _ACCESS_TOKEN_CACHE[cache_key] = {"token": jwt, "expires": time.time() + ttl_seconds}
        return jwt
    except ImportError:
        logger.error("[livekit] livekit package not installed. Run: pip install livekit")
        return None
    except Exception as e:
        logger.error(f"[livekit] Token creation failed: {e}")
        return None

def create_ingress_token(identity: str, room_name: str) -> Optional[str]:
    """Token for host/ingress (can publish video)."""
    return create_livekit_token(identity, room_name, can_publish=True, can_subscribe=True)

def create_viewer_token(identity: str, room_name: str) -> Optional[str]:
    """Token for viewer (subscribe only, no publish)."""
    return create_livekit_token(identity, room_name, can_publish=False, can_subscribe=True)

def create_guest_token(identity: str, room_name: str) -> Optional[str]:
    """Token for guest speaker (can publish audio/video)."""
    return create_livekit_token(identity, room_name, can_publish=True, can_subscribe=True)

def get_cached_token(identity: str, room_name: str) -> Optional[str]:
    cache_key = f"{identity}:{room_name}"
    entry = _ACCESS_TOKEN_CACHE.get(cache_key)
    if entry and entry["expires"] > time.time() + 60:
        return entry["token"]
    return None

def get_stun_turn_servers() -> list:
    """Returns STUN/TURN server list for WebRTC ICE config."""
    servers = [
        {"urls": ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"]},
    ]
    turn_url = get_env("TURN_URL", "")
    turn_user = get_env("TURN_USERNAME", "")
    turn_cred = get_env("TURN_CREDENTIAL", "")
    if turn_url and turn_user and turn_cred:
        servers.append({
            "urls": [turn_url],
            "username": turn_user,
            "credential": turn_cred,
        })
    return servers

def create_web_rtc_config() -> dict:
    """Full WebRTC configuration object for the frontend."""
    return {
        "iceServers": get_stun_turn_servers(),
        "iceTransportPolicy": "all",
        "iceCandidatePoolSize": 10,
    }

def check_livekit_health() -> dict:
    if not livekit_configured():
        return {"status": "not_configured", "ok": False}
    try:
        from livekit.api import LiveKitAPI
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        api = LiveKitAPI(LIVEKIT_HOST, LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        rooms = loop.run_until_complete(api.room.list_rooms())
        loop.run_until_complete(api.aclose())
        loop.close()
        return {
            "status": "ok",
            "ok": True,
            "room_count": len(rooms),
            "host": LIVEKIT_HOST,
        }
    except ImportError:
        return {"status": "no_sdk", "ok": False, "message": "livekit package not installed"}
    except Exception as e:
        return {"status": "error", "ok": False, "error": str(e)[:200]}
