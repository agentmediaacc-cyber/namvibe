import os

from flask import Blueprint, jsonify, render_template, request

from services.admin_auth_service import require_admin
from services.job_queue_service import (
    cancel_job,
    enqueue_job,
    get_job,
    get_queue_stats,
    retry_job,
)
from services.profile_service import get_current_profile
from services.redis_hardening_service import get_redis_health
from services.scheduler_service import disable_task, enable_task, get_scheduler_status
from services.worker_service import get_all_worker_statuses

system_bp = Blueprint("system", __name__)


def _health_payload():
    queue = get_queue_stats()
    scheduler = get_scheduler_status()
    workers = get_all_worker_statuses()
    redis = get_redis_health()
    components = {
        "app": {"ok": True, "status": "ok"},
        "database": {"ok": True, "status": "fallback" if queue.get("db_fallback") else "configured"},
        "redis": redis,
        "job_queue": {"ok": True, **queue.get("stats", {})},
        "scheduler": {"ok": True, "tasks": len(scheduler.get("tasks", []))},
        "workers": {"ok": True, "online": len([w for w in workers if w.get("status") == "online"])},
        "socketio": {"ok": True, "status": "registered"},
        "storage": {"ok": True, "status": "not_checked"},
        "notification_queue": {"ok": True, "status": "queue_ready"},
    }
    return {"ok": all(bool(c.get("ok", True)) for c in components.values()), "components": components}


@system_bp.route("/system/health")
@require_admin
def system_health_page():
    return render_template("admin/system_health.html")


@system_bp.route("/system/queue")
@require_admin
def queue_dashboard_page():
    return render_template("admin/queue_dashboard.html")


@system_bp.route("/system/workers")
@require_admin
def workers_page():
    return render_template("admin/workers.html")


@system_bp.route("/system/scheduled-tasks")
@require_admin
def scheduled_tasks_page():
    return render_template("admin/scheduled_tasks.html")


@system_bp.route("/system/api/health")
@require_admin
def api_health():
    return jsonify(_health_payload()), 200


@system_bp.route("/system/api/cache-status")
@require_admin
def api_cache_status():
    from services.homepage_cache_service import homepage_cache_info
    return jsonify(homepage_cache_info()), 200


@system_bp.route("/system/api/queue/stats")
@require_admin
def api_queue_stats():
    return jsonify(get_queue_stats()), 200


@system_bp.route("/system/api/workers")
@require_admin
def api_workers():
    return jsonify({"ok": True, "workers": get_all_worker_statuses()}), 200


@system_bp.route("/system/api/scheduled-tasks")
@require_admin
def api_scheduled_tasks():
    return jsonify(get_scheduler_status()), 200


@system_bp.route("/system/api/scheduled-tasks/<task_name>/enable", methods=["POST"])
@require_admin
def api_enable_task(task_name):
    return jsonify(enable_task(task_name)), 200


@system_bp.route("/system/api/scheduled-tasks/<task_name>/disable", methods=["POST"])
@require_admin
def api_disable_task(task_name):
    return jsonify(disable_task(task_name)), 200


@system_bp.route("/system/api/jobs/enqueue-test", methods=["POST"])
@require_admin
def api_enqueue_test():
    data = request.get_json(silent=True) or {}
    result = enqueue_job(data.get("job_type") or "security_event_digest", data.get("payload") or {"source": "api-test"})
    return jsonify(result), 200


@system_bp.route("/system/api/jobs/<job_id>")
@require_admin
def api_get_job(job_id):
    job = get_job(job_id)
    return jsonify({"ok": bool(job), "job": job}), 200 if job else 404


@system_bp.route("/system/api/jobs/<job_id>/retry", methods=["POST"])
@require_admin
def api_retry_job(job_id):
    return jsonify(retry_job(job_id)), 200


@system_bp.route("/system/api/jobs/<job_id>/cancel", methods=["POST"])
@require_admin
def api_cancel_job(job_id):
    return jsonify(cancel_job(job_id)), 200


@system_bp.route("/system/api/realtime-health")
@require_admin
def api_realtime_health():
    from services.socketio_service import socketio
    from services.presence_engine import get_presence as get_presence_count
    redis_status = "connected"
    try:
        from services.redis_service import get_json
        get_json("health:ping")
        redis_status = "connected"
    except Exception:
        redis_status = "fallback"
    online_users = 0
    try:
        from services.redis_service import get_redis
        r = get_redis()
        if r:
            keys = r.keys("presence:state:*")
            online_users = len(keys) if keys else 0
    except Exception:
        pass
    from api_routes.message_routes import message_bp
    from api_routes.call_routes import call_bp
    from api_routes.notification_routes import notification_engine_bp
    message_routes = bool(message_bp)
    call_routes = bool(call_bp)
    notification_routes = bool(notification_engine_bp)
    return jsonify({
        "ok": True,
        "socketio": "registered",
        "redis": redis_status,
        "online_users": online_users if isinstance(online_users, int) else 0,
        "message_routes": message_routes,
        "call_routes": call_routes,
        "notification_routes": notification_routes,
    })


@system_bp.route("/dev/communication-test")
@require_admin
def dev_communication_test():
    if os.environ.get("CHAIN_DEV_TOOLS") != "1":
        return render_template("errors/404.html"), 404
    profile = get_current_profile()
    profile_id = (profile or {}).get("id") or "not_logged_in" if profile else "not_logged_in"
    username = (profile or {}).get("username") or "anonymous"
    return render_template("dev/communication_test.html", profile_id=profile_id, username=username)
