from django.conf import settings
from django.http import JsonResponse
from urllib.parse import urlparse
import os

def db_env_debug(request):
    raw = os.environ.get("DATABASE_URL", "")
    parsed = urlparse(raw) if raw else None
    return JsonResponse({
        "database_url_exists": bool(raw),
        "username": parsed.username if parsed else "",
        "host": parsed.hostname if parsed else "",
        "port": parsed.port if parsed else "",
        "engine_user": settings.DATABASES["default"].get("USER", ""),
        "engine_host": settings.DATABASES["default"].get("HOST", ""),
        "engine_port": settings.DATABASES["default"].get("PORT", ""),
    })
