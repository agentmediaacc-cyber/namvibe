import os
import json
import logging

logger = logging.getLogger(__name__)

STUN_SERVER_URL = os.environ.get("STUN_SERVER_URL", "stun:stun.l.google.com:19302")
TURN_SERVER_URL = os.environ.get("TURN_SERVER_URL", "")
TURN_USERNAME = os.environ.get("TURN_USERNAME", "")
TURN_PASSWORD = os.environ.get("TURN_PASSWORD", "")


def get_webrtc_ice_config():
    ice_servers = []

    ice_servers.append({
        "urls": STUN_SERVER_URL,
    })

    if TURN_SERVER_URL:
        urls = [u.strip() for u in TURN_SERVER_URL.split(",") if u.strip()]
        turn_entry = {
            "urls": urls,
            "username": TURN_USERNAME,
            "credential": TURN_PASSWORD,
        }
        ice_servers.append(turn_entry)

        tcp_urls = []
        for url in urls:
            if url.startswith("turn:"):
                tcp_url = url.replace(":3478", ":3479").replace(":5349", ":5350")
                if "?transport=udp" in url:
                    tcp_url = url.replace("?transport=udp", "?transport=tcp")
                elif "?transport=tcp" not in url:
                    tcp_url = url + "?transport=tcp"
                tcp_urls.append(tcp_url)
        if tcp_urls:
            tcp_entry = {
                "urls": tcp_urls,
                "username": TURN_USERNAME,
                "credential": TURN_PASSWORD,
            }
            ice_servers.append(tcp_entry)

    return {
        "iceServers": ice_servers,
        "iceTransportPolicy": "all",
        "iceCandidatePoolSize": 10,
    }


def turn_configured():
    return bool(TURN_SERVER_URL)


def stun_configured():
    return bool(STUN_SERVER_URL)


def get_turn_status():
    if not TURN_SERVER_URL:
        return "missing"
    if not TURN_USERNAME or not TURN_PASSWORD:
        return "partial"
    return "ready"


def get_stun_status():
    if not STUN_SERVER_URL:
        return "missing"
    return "ready"
