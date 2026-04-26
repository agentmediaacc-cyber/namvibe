from django.http import JsonResponse
from django.db import connection

def healthz(request):
    return JsonResponse({"status": "ok"})

def health_db(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"database": "ok"})
    except Exception as e:
        return JsonResponse({"database": "fail", "error": str(e)})

def db_env_debug(request):
    import os
    from urllib.parse import urlparse

    raw = os.environ.get("DATABASE_URL", "")
    parsed = urlparse(raw) if raw else None

    return JsonResponse({
        "database_url_exists": bool(raw),
        "username": parsed.username if parsed else "",
        "host": parsed.hostname if parsed else "",
        "port": parsed.port if parsed else "",
    })
