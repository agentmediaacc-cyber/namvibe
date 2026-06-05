import os
from flask import request, abort, jsonify
from services.neon_service import fast_query, write_query

def check_ip_reputation():

    if os.getenv("CHAIN_DISABLE_IP_REPUTATION", "0") == "1":
        return False

    ip = request.remote_addr
    if not ip: return
    
    sql = "SELECT is_blocked FROM chain_ip_reputation WHERE ip_address = %s"
    rows = fast_query(sql, (ip,))
    if rows and rows[0]['is_blocked']:
        abort(403, description="Access denied from this IP address.")

def record_login_attempt(profile_id, is_anomaly=False):
    ip = request.remote_addr
    ua = request.user_agent.string
    fingerprint = request.headers.get("X-Device-Fingerprint")
    
    sql = """
        INSERT INTO chain_login_history (profile_id, ip_address, user_agent, device_fingerprint, is_anomaly)
        VALUES (%s, %s, %s, %s, %s)
    """
    write_query(sql, (profile_id, ip, ua, fingerprint, is_anomaly))
