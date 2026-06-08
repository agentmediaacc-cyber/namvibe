"""
Phase 50: Production launch readiness, monitoring, backups, alerts, deployment validation.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["CHAIN_TEST_FAKE_DB"] = "1"

from app import create_app

PASS = 0
FAIL = 0


def check(label, ok, detail=None):
    global PASS, FAIL
    if ok:
        print(f"  [PASS] {label}")
        PASS += 1
    else:
        print(f"  [FAIL] {label}" + (f" - {detail}" if detail else ""))
        FAIL += 1


print("\n=== 1. MIGRATION ===")
path = "sql/phase50_production_readiness.sql"
sql = open(path).read() if os.path.exists(path) else ""
check("migration exists", bool(sql))
for token in [
    "chain_deployment_audits",
    "chain_system_alerts",
    "chain_backup_events",
    "CREATE INDEX IF NOT EXISTS",
    "component",
    "severity",
    "resolved",
    "audit_type",
    "created_at",
]:
    check(f"migration has {token}", token in sql)


print("\n=== 2. SERVICES ===")
from services.production_audit_service import (
    audit_database,
    audit_notifications,
    audit_redis,
    audit_safety,
    audit_scheduler,
    audit_security,
    audit_socketio,
    audit_storage,
    audit_wallet,
    audit_workers,
    generate_launch_report,
    generate_launch_score,
    run_full_audit,
)
from services.alerting_service import create_alert, generate_alert_summary, get_active_alerts, get_alert_history, resolve_alert
from services.backup_service import generate_backup_report, get_backup_history, record_backup_event, verify_backup_configuration, verify_restore_plan
from services.deployment_validation_service import (
    generate_deployment_report,
    validate_database_configuration,
    validate_environment,
    validate_redis_configuration,
    validate_required_env_vars,
    validate_scheduler_configuration,
    validate_ssl_configuration,
    validate_worker_configuration,
)
from services.monitoring_service import (
    collect_call_metrics,
    collect_message_metrics,
    collect_queue_metrics,
    collect_safety_metrics,
    collect_system_metrics,
    collect_wallet_metrics,
    generate_monitoring_summary,
)
from services.security_hardening_service import (
    check_cookie_security,
    check_csrf_configuration,
    check_debug_mode,
    check_rate_limit_configuration,
    check_secret_strength,
    check_security_headers,
    generate_security_report,
)

audit = run_full_audit()
check("audit service run_full_audit", isinstance(audit, dict) and "score" in audit)
for name, func in [
    ("audit_database", audit_database),
    ("audit_redis", audit_redis),
    ("audit_workers", audit_workers),
    ("audit_scheduler", audit_scheduler),
    ("audit_security", audit_security),
    ("audit_storage", audit_storage),
    ("audit_notifications", audit_notifications),
    ("audit_socketio", audit_socketio),
    ("audit_wallet", audit_wallet),
    ("audit_safety", audit_safety),
]:
    check(name, isinstance(func(), dict))
check("generate_launch_score", isinstance(generate_launch_score(audit.get("findings", [])), int))
check("generate_launch_report", "launch_score" in generate_launch_report())

alert = create_alert("database", "warning", "Phase50 test", "test alert")
alert_id = alert.get("alert", {}).get("id")
check("create alert", alert.get("ok") and alert_id)
check("get active alerts", any(a["id"] == alert_id for a in get_active_alerts()))
check("alert summary", generate_alert_summary().get("ok"))
check("resolve alert", resolve_alert(alert_id).get("ok"))
check("alert history", isinstance(get_alert_history(), list))

backup = record_backup_event("database", "verified", "phase50")
check("record backup event", backup.get("ok"))
check("verify backup configuration", isinstance(verify_backup_configuration(), dict))
check("verify restore plan", verify_restore_plan().get("ok"))
check("backup history", isinstance(get_backup_history(), list))
check("backup report", isinstance(generate_backup_report(), dict))

for label, func in [
    ("validate_environment", validate_environment),
    ("validate_required_env_vars", validate_required_env_vars),
    ("validate_ssl_configuration", validate_ssl_configuration),
    ("validate_worker_configuration", validate_worker_configuration),
    ("validate_scheduler_configuration", validate_scheduler_configuration),
    ("validate_redis_configuration", validate_redis_configuration),
    ("validate_database_configuration", validate_database_configuration),
    ("deployment report", generate_deployment_report),
]:
    check(label, isinstance(func(), dict))

for label, func in [
    ("system metrics", collect_system_metrics),
    ("queue metrics", collect_queue_metrics),
    ("wallet metrics", collect_wallet_metrics),
    ("message metrics", collect_message_metrics),
    ("call metrics", collect_call_metrics),
    ("safety metrics", collect_safety_metrics),
    ("monitoring summary", generate_monitoring_summary),
]:
    check(label, isinstance(func(), dict))

for label, func in [
    ("secret strength", check_secret_strength),
    ("debug mode", check_debug_mode),
    ("cookie security", check_cookie_security),
    ("csrf configuration", check_csrf_configuration),
    ("rate limit configuration", check_rate_limit_configuration),
    ("security headers", check_security_headers),
    ("security report", generate_security_report),
]:
    check(label, isinstance(func(), dict))


print("\n=== 3. ROUTES ===")
app = create_app()
client = app.test_client()
routes = {rule.rule for rule in app.url_map.iter_rules()}
for route in [
    "/production/api/audit",
    "/production/api/deployment-report",
    "/production/api/monitoring",
    "/production/api/alerts",
    "/production/api/alerts/<alert_id>/resolve",
    "/production/api/backups",
    "/production/api/launch-readiness",
]:
    check(f"route exists {route}", route in routes)

check("launch readiness endpoint exists", client.get("/production/api/launch-readiness").status_code == 200)
check("deployment report endpoint exists", client.get("/production/api/deployment-report").status_code == 200)
check("monitoring endpoint exists", client.get("/production/api/monitoring").status_code == 200)
created = create_alert("redis", "warning", "Resolve me", "phase50 route")
resolved = client.post(f"/production/api/alerts/{created['alert']['id']}/resolve")
check("alert resolution endpoint", resolved.status_code == 200 and (resolved.get_json() or {}).get("ok"))


print("\n=== 4. FILES ===")
for file_path in [
    "templates/admin/production_audit.html",
    "templates/admin/launch_readiness.html",
    "templates/admin/monitoring_dashboard.html",
    "templates/admin/system_alerts.html",
    "templates/admin/backup_status.html",
    "scripts/benchmark_chain.py",
    "docs/CHAIN_GO_LIVE_CHECKLIST.md",
    "scripts/test_phase49_enterprise_scaling.py",
    "scripts/test_phase48_trust_safety.py",
    "scripts/test_phase47_creator_wallet.py",
]:
    check(f"{file_path} exists", os.path.exists(file_path))

src = open("app.py").read()
check("production blueprint imported", "production_bp" in src)
check("production blueprint registered", "register_blueprint(production_bp)" in src)


total = PASS + FAIL
print("\n=== PHASE 50 SUMMARY ===")
print(f"  PASS: {PASS}/{total}  FAIL: {FAIL}/{total}")
if FAIL:
    raise SystemExit(1)
print("  All Phase 50 production readiness tests passed!")
