import time
import os
from datetime import datetime, timezone, timedelta
from services.neon_service import fast_query, get_neon_health
from services.redis_service import get_redis_health, redis_available
from services.supabase_safe import safe_count

def get_platform_health_snapshot():
    """
    Returns a technical snapshot of the platform's current state.
    """
    start = time.perf_counter()
    # Test DB latency
    fast_query("SELECT 1")
    db_latency = (time.perf_counter() - start) * 1000
    
    # Real-time metrics
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    
    from services.socketio_service import socketio
    
    return {
        "status": "healthy" if db_latency < 500 else "degraded",
        "timestamp": now.isoformat(),
        "db_latency_ms": round(db_latency, 2),
        "database": get_neon_health(),
        "redis": get_redis_health(),
        "socketio": {
            "ready": True,
            "scalable": redis_available(),
            "async_mode": socketio.async_mode,
        },
        "metrics": {
            "active_connections": safe_count("chain_presence", filters={"status": "online"}),
            "active_streams": safe_count("chain_live_rooms", filters={"status": "live"}),
            "messages_24h": safe_count("chain_messages", filters={"created_at": ("gt", (now - timedelta(days=1)).isoformat())}),
            "calls_24h": safe_count("chain_call_sessions", filters={"started_at": ("gt", (now - timedelta(days=1)).isoformat())}),
            "payouts_pending": safe_count("chain_wallet_payouts", filters={"status": "pending"}),
        },
        "environment": {
            "flask_env": os.getenv("FLASK_ENV", "development"),
            "fast_local": os.getenv("CHAIN_FAST_LOCAL", "0") == "1",
        }
    }

def log_system_event(event_type, severity, message, metadata=None):
    """Logs a system-level event for technical auditing"""
    from services.supabase_safe import safe_insert
    from datetime import datetime, timezone
    payload = {
        "actor_type": "system",
        "action": event_type,
        "metadata": {
            "severity": severity,
            "message": message,
            "extra": metadata or {}
        },
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    # We reuse the enterprise audit log table
    return safe_insert("chain_enterprise_audit_log", payload)
