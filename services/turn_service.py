"""NamVibe TURN/STUN Service — WebRTC NAT Traversal via coturn"""

import os
import logging
from services.env_service import get_env

logger = logging.getLogger(__name__)

TURN_URL = get_env("TURN_URL", "")
TURN_USERNAME = get_env("TURN_USERNAME", "")
TURN_CREDENTIAL = get_env("TURN_CREDENTIAL", "")
TURN_REALM = get_env("TURN_REALM", "namvibe.com")

STUN_SERVERS = [
    {"urls": ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"]},
    {"urls": ["stun:stun2.l.google.com:19302"]},
]

def turn_configured() -> bool:
    return bool(TURN_URL and TURN_USERNAME and TURN_CREDENTIAL)

def get_turn_config() -> dict:
    config = {
        "iceServers": list(STUN_SERVERS),
        "iceTransportPolicy": "all",
        "iceCandidatePoolSize": 10,
    }
    if turn_configured():
        config["iceServers"].append({
            "urls": [TURN_URL],
            "username": TURN_USERNAME,
            "credential": TURN_CREDENTIAL,
        })
    return config

def get_turn_status() -> dict:
    return {
        "configured": turn_configured(),
        "turn_url": TURN_URL or "not_set",
        "stun_servers": len(STUN_SERVERS),
        "realm": TURN_REALM,
    }

def get_coturn_install_guide() -> str:
    return """
# ── coturn STUN/TURN Server Setup ──

## Install
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
