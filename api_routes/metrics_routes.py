from flask import Blueprint, abort, jsonify, render_template, request

from services.admin_auth_service import current_admin, require_admin
from services.metrics_service import get_metrics_summary
from services.neon_service import get_neon_health
from services.redis_service import get_redis_health
from services.job_engine import run_due_jobs


metrics_bp = Blueprint("metrics", __name__)


def _metrics_payload():
    return get_metrics_summary(
        {
            "neon": get_neon_health(),
            "redis": get_redis_health(),
        }
    )


@metrics_bp.route("/admin/metrics")
@require_admin
def admin_metrics_dashboard():
    return render_template("metrics/dashboard.html", metrics=_metrics_payload(), admin=current_admin())


@metrics_bp.route("/health/metrics-summary")
def metrics_summary():
    if request.remote_addr not in {"127.0.0.1", "::1"} and not current_admin():
        abort(403)
    return jsonify(_metrics_payload()), 200


@metrics_bp.route("/health/metrics")
def health_metrics():
    if request.remote_addr not in {"127.0.0.1", "::1"} and not current_admin():
        abort(403)
    return jsonify(_metrics_payload()), 200


@metrics_bp.route("/health/queues")
def health_queues():
    if request.remote_addr not in {"127.0.0.1", "::1"} and not current_admin():
        abort(403)
    jobs = run_due_jobs(limit=50)
    return jsonify({"queued_jobs": len(jobs), "sample": jobs[:10]}), 200
