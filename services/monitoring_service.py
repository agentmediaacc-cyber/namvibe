def collect_queue_metrics():
    try:
        from services.job_queue_service import get_queue_stats
        return get_queue_stats().get("stats", {})
    except Exception:
        return {"queued": 0, "failed": 0, "running": 0}


def collect_wallet_metrics():
    return {"wallet_transactions": 0, "pending_payouts": 0}


def collect_message_metrics():
    return {"messages_sent": 0, "active_users": 0}


def collect_call_metrics():
    return {"calls_active": 0}


def collect_safety_metrics():
    try:
        from services.moderation_service import get_moderation_queue
        pending = len(get_moderation_queue(status="pending", limit=100) or [])
    except Exception:
        pending = 0
    return {"reports_pending": pending, "moderation_pending": pending}


def collect_system_metrics():
    try:
        from services.alerting_service import generate_alert_summary
        alerts = generate_alert_summary()
    except Exception:
        alerts = {"active_count": 0}
    return {
        "active_users": collect_message_metrics().get("active_users", 0),
        "messages_sent": collect_message_metrics().get("messages_sent", 0),
        "calls_active": collect_call_metrics().get("calls_active", 0),
        "queue_depth": collect_queue_metrics().get("queued", 0),
        "failed_jobs": collect_queue_metrics().get("failed", 0),
        "wallet_transactions": collect_wallet_metrics().get("wallet_transactions", 0),
        "reports_pending": collect_safety_metrics().get("reports_pending", 0),
        "system_alerts": alerts.get("active_count", 0),
    }


def generate_monitoring_summary():
    return {
        "ok": True,
        "system": collect_system_metrics(),
        "queue": collect_queue_metrics(),
        "wallet": collect_wallet_metrics(),
        "messages": collect_message_metrics(),
        "calls": collect_call_metrics(),
        "safety": collect_safety_metrics(),
    }
