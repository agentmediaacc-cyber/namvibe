from flask import Blueprint, jsonify, render_template

from services.alerting_service import get_active_alerts, get_alert_history, resolve_alert
from services.backup_service import generate_backup_report, get_backup_history
from services.deployment_validation_service import generate_deployment_report
from services.monitoring_service import generate_monitoring_summary
from services.production_audit_service import generate_launch_report, run_full_audit

production_bp = Blueprint("production", __name__)


@production_bp.route("/admin/production/audit")
def production_audit_page():
    return render_template("admin/production_audit.html")


@production_bp.route("/admin/production/launch-readiness")
def launch_readiness_page():
    return render_template("admin/launch_readiness.html")


@production_bp.route("/admin/production/monitoring")
def monitoring_page():
    return render_template("admin/monitoring_dashboard.html")


@production_bp.route("/admin/production/alerts")
def alerts_page():
    return render_template("admin/system_alerts.html")


@production_bp.route("/admin/production/backups")
def backup_status_page():
    return render_template("admin/backup_status.html")


@production_bp.route("/production/api/audit")
def api_audit():
    return jsonify(run_full_audit()), 200


@production_bp.route("/production/api/deployment-report")
def api_deployment_report():
    return jsonify(generate_deployment_report()), 200


@production_bp.route("/production/api/monitoring")
def api_monitoring():
    return jsonify(generate_monitoring_summary()), 200


@production_bp.route("/production/api/alerts")
def api_alerts():
    return jsonify({"ok": True, "alerts": get_active_alerts(), "history": get_alert_history(limit=50)}), 200


@production_bp.route("/production/api/alerts/<alert_id>/resolve", methods=["POST"])
def api_resolve_alert(alert_id):
    result = resolve_alert(alert_id)
    return jsonify(result), 200 if result.get("ok") else 404


@production_bp.route("/production/api/backups")
def api_backups():
    return jsonify({"ok": True, "report": generate_backup_report(), "history": get_backup_history()}), 200


@production_bp.route("/production/api/launch-readiness")
def api_launch_readiness():
    return jsonify(generate_launch_report()), 200
