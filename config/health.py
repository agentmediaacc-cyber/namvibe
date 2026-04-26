import logging
from django.conf import settings

from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.http import HttpResponse, JsonResponse


logger = logging.getLogger(__name__)


def _database_health_payload():
    payload = {
        "app": "ok",
        "database": "unknown",
        "database_error": None,
        "database_url_exists": bool(getattr(settings, "DATABASE_URL", "")),
        "engine": connection.settings_dict.get("ENGINE", "unknown"),
        "vendor": connection.vendor,
        "migrations_accessible": False,
    }
    try:
        connection.ensure_connection()
        payload["database"] = "ok"
        recorder = MigrationRecorder(connection)
        payload["migrations_accessible"] = recorder.has_table()
    except Exception as exc:
        payload["database"] = "fail"
        payload["database_error"] = exc.__class__.__name__
        logger.exception("Database health check failed with %s", exc.__class__.__name__)
    return payload


def healthz(_request):
    return HttpResponse("ok", content_type="text/plain; charset=utf-8")


def health_db(_request):
    payload = _database_health_payload()
    return JsonResponse(payload, status=200 if payload["database"] == "ok" else 503)
