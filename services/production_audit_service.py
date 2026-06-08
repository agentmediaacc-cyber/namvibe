from datetime import datetime, timezone


def _finding(component, ok, message, severity="info", score=10):
    return {
        "component": component,
        "ok": bool(ok),
        "message": message,
        "severity": severity,
        "score": score if ok else 0,
        "weight": score,
    }


def audit_database():
    try:
        from services.deployment_validation_service import validate_database_configuration
        result = validate_database_configuration()
        return _finding("database", result.get("ok"), "Database URL configured" if result.get("ok") else "DATABASE_URL is missing", "critical")
    except Exception as error:
        return _finding("database", False, str(error), "critical")


def audit_redis():
    try:
        from services.redis_hardening_service import get_redis_health
        health = get_redis_health()
        return _finding("redis", health.get("available"), "Redis connected" if health.get("available") else "Redis fallback mode active", "warning", 8)
    except Exception as error:
        return _finding("redis", False, str(error), "warning", 8)


def audit_workers():
    try:
        from services.worker_service import get_all_worker_statuses
        workers = get_all_worker_statuses()
        online = len([w for w in workers if w.get("status") == "online"])
        return _finding("workers", online > 0, f"{online} workers online", "warning", 8)
    except Exception as error:
        return _finding("workers", False, str(error), "warning", 8)


def audit_scheduler():
    try:
        from services.scheduler_service import get_scheduler_status
        status = get_scheduler_status()
        enabled = len(status.get("enabled", []))
        return _finding("scheduler", enabled >= 6, f"{enabled} scheduled tasks enabled", "warning", 8)
    except Exception as error:
        return _finding("scheduler", False, str(error), "warning", 8)


def audit_security():
    from services.security_hardening_service import generate_security_report
    report = generate_security_report()
    return _finding("security", report.get("score", 0) >= 70, f"Security score {report.get('score')}", "critical", 14)


def audit_storage():
    import os
    ok = bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    return _finding("storage", ok, "Storage configured" if ok else "Storage env not fully configured", "warning", 8)


def audit_notifications():
    import os
    ok = bool(os.getenv("VAPID_PUBLIC_KEY") or os.getenv("FCM_SERVER_KEY"))
    return _finding("notifications", ok, "Push provider configured" if ok else "Push provider not configured", "warning", 7)


def audit_socketio():
    try:
        import services.socket_events  # noqa: F401
        return _finding("socketio", True, "Socket handlers import successfully", "info", 8)
    except Exception as error:
        return _finding("socketio", False, str(error), "critical", 8)


def audit_wallet():
    try:
        from services.creator_monetization_service import calculate_platform_fee
        return _finding("wallet", calculate_platform_fee(1000) == 100, "Wallet fee calculation healthy", "critical", 12)
    except Exception as error:
        return _finding("wallet", False, str(error), "critical", 12)


def audit_safety():
    try:
        from services.spam_detection_service import analyze_text_for_spam
        spam = analyze_text_for_spam("free money crypto gift card password bitcoin guaranteed profit click now")
        return _finding("safety", spam.get("spam") is True or spam.get("score", 0) >= 30, "Safety rule engine healthy", "critical", 12)
    except Exception as error:
        return _finding("safety", False, str(error), "critical", 12)


def generate_launch_score(findings):
    possible = sum(int(f.get("weight", f.get("score", 0)) or 0) for f in findings)
    earned = sum(int(f.get("score", 0) or 0) for f in findings if f.get("ok"))
    return min(100, int(round((earned / possible) * 100))) if possible else 0


def run_full_audit():
    findings = [
        audit_database(),
        audit_redis(),
        audit_workers(),
        audit_scheduler(),
        audit_security(),
        audit_storage(),
        audit_notifications(),
        audit_socketio(),
        audit_wallet(),
        audit_safety(),
    ]
    score = generate_launch_score(findings)
    warnings = [f for f in findings if not f.get("ok") and f.get("severity") == "warning"]
    critical = [f for f in findings if not f.get("ok") and f.get("severity") == "critical"]
    return {"ok": not critical, "score": score, "findings": findings, "warnings": warnings, "critical": critical}


def generate_launch_report():
    audit = run_full_audit()
    from services.deployment_validation_service import generate_deployment_report
    from services.backup_service import generate_backup_report
    return {
        "ok": audit.get("ok"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "launch_score": audit.get("score"),
        "audit": audit,
        "deployment": generate_deployment_report(),
        "backups": generate_backup_report(),
    }
