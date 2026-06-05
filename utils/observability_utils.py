import os
import time
from flask import request, g
from services.neon_service import write_query

def start_request_timer():
    g.start_time = time.time()

def log_request_performance(response):

    if os.getenv("CHAIN_DISABLE_PERFORMANCE_LOGS", "0") == "1":
        return response

    if not hasattr(g, 'start_time'):
        return response
    
    latency = (time.time() - g.start_time) * 1000
    path = request.path
    method = request.method
    status = response.status_code
    profile_id = g.get('profile_id') or getattr(g, 'current_profile', {}).get('id')
    
    # Async log to DB (Simulated by direct write for now, but should be a background job)
    sql = "INSERT INTO chain_performance_logs (request_path, method, status_code, latency_ms, profile_id) VALUES (%s, %s, %s, %s, %s)"
    try:
        write_query(sql, (path, method, status, latency, profile_id))
    except:
        pass
        
    return response
