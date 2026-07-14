"""NamVibe TURN/STUN Service — WebRTC NAT Traversal via LiveKit Cloud or coturn"""

import os
import logging
from services.env_service import get_env

logger = logging.getLogger(__name__)

TURN_URL = get_env("TURN_URL", "")
TURN_USERNAME = get_env("TURN_USERNAME", "")
TURN_CREDENTIAL = get_env("TURN_CREDENTIAL", "")
TURN_REALM = get_env("TURN_REALM", "namvibe.com")
LIVEKIT_API_KEY = get_env("LIVEKIT_API_KEY", "")

STUN_SERVERS = [
    {"urls": ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"]},
    {"urls": ["stun:stun2.l.google.com:19302"]},
]

def turn_configured() -> bool:
    return bool(TURN_URL and TURN_USERNAME and TURN_CREDENTIAL)

def turn_handled_by_livekit() -> bool:
    return bool(LIVEKIT_API_KEY)

def get_turn_config() -> dict:
    config = {
        "iceServers": list(STUN_SERVERS),
        "iceTransportPolicy": "all",
        "iceCandidatePoolSize": 10,
    }
    if turn_configured():
        urls = [part.strip() for part in str(TURN_URL).split(",") if part.strip()]
        if not urls:
            urls = [TURN_URL]
        config["iceServers"].append({
            "urls": urls,
            "username": TURN_USERNAME,
            "credential": TURN_CREDENTIAL,
        })
    return config

def get_turn_status() -> dict:
    lk_handles = turn_handled_by_livekit()
    return {
        "configured": turn_configured() or lk_handles,
        "turn_url": (TURN_URL.split(",")[0].strip() if TURN_URL else ("livekit_cloud" if lk_handles else "not_set")),
        "stun_servers": len(STUN_SERVERS),
        "realm": TURN_REALM,
        "handled_by_livekit": lk_handles,
    }

def get_coturn_install_guide() -> str:
    return """
# ── coturn STUN/TURN Server Setup ──
# NOTE: Not needed when using LiveKit Cloud — it provides built-in TURN relay.

## Install (only if NOT using LiveKit Cloud)
  brew install coturn          # macOS
  apt install coturn           # Ubuntu/Debian

## Minimal turnserver.conf
  listening-port=3478
  tls-listening-port=5349
  realm=namvibe.com
  server-name=namvibe.com
  fingerprint
  lt-cred-mech
  user=namvibe:YOUR_STRONG_PASSWORD
  realm=namvibe.com
  total-quota=300
  bps-capacity=0
  stale-nonce=600

## Environment variables to set
  TURN_URL=turn:YOUR_SERVER_IP:3478
  TURN_USERNAME=namvibe
  TURN_CREDENTIAL=YOUR_STRONG_PASSWORD
  TURN_REALM=namvibe.com
"""
