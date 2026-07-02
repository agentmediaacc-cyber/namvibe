import os
import time
from concurrent.futures import ThreadPoolExecutor
from flask import request, g
from services.neon_service import get_pool_status, write_query

_PERF_LOG_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="perf-log")


def start_request_timer():
    g.start_time = time.time()


def _write_performance_log(path, method, status, latency, profile_id):
    sql = "INSERT INTO chain_performance_logs (request_path, method, status_code, latency_ms, profile_id) VALUES (%s, %s, %s, %s, %s)"
    try:
        write_query(sql, (path, method, status, latency, profile_id), timeout_ms=150)
    except Exception:
        pass


def log_request_performance(response):

    if os.getenv("CHAIN_DISABLE_PERFORMANCE_LOGS", "0") == "1":
        return response

    if request.path.startswith("/static/"):
        return response

    if request.path == "/healthz" or request.path.startswith("/health/"):
        return response

    if not hasattr(g, 'start_time'):
        return response

    pool_status = get_pool_status()
    if not pool_status.get("available"):
        return response
    
    latency = (time.time() - g.start_time) * 1000
    path = request.path
    method = request.method
    status = response.status_code
    profile_id = g.get('profile_id') or getattr(g, 'current_profile', {}).get('id')

    try:
        _PERF_LOG_EXECUTOR.submit(_write_performance_log, path, method, status, latency, profile_id)
    except Exception:
        pass
        
    return response
