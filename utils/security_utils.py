import os
from flask import request, abort, jsonify
from services.neon_service import fast_query, write_query
from engines.cache_engine import cache_key, get_cache, set_cache


_IP_REPUTATION_TTL_SECONDS = 60

def check_ip_reputation():
    if os.getenv("CHAIN_DISABLE_IP_REPUTATION", "0") == "1":
        return False

    ip = request.remote_addr
    if not ip:
        return False
    if ip in {"127.0.0.1", "::1"}:
        return False

    cached = get_cache(cache_key("ip_reputation", ip))
    if cached is not None:
        if cached:
            abort(403, description="Access denied from this IP address.")
        return False

    sql = "SELECT is_blocked FROM chain_ip_reputation WHERE ip_address = %s"
    try:
        rows = fast_query(sql, (ip,), timeout_ms=150, default=[])
    except Exception:
        return False
    is_blocked = bool(rows and rows[0]["is_blocked"])
    set_cache(cache_key("ip_reputation", ip), is_blocked, ttl=_IP_REPUTATION_TTL_SECONDS)
    if is_blocked:
        abort(403, description="Access denied from this IP address.")
    return False

def record_login_attempt(profile_id, is_anomaly=False):
    ip = request.remote_addr
    ua = request.user_agent.string
    fingerprint = request.headers.get("X-Device-Fingerprint")
    
    sql = """
        INSERT INTO chain_login_history (profile_id, ip_address, user_agent, device_fingerprint, is_anomaly)
        VALUES (%s, %s, %s, %s, %s)
    """
    write_query(sql, (profile_id, ip, ua, fingerprint, is_anomaly))
