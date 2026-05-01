from django.conf import settings
from django.http import Http404, JsonResponse
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
    if not settings.DEBUG:
        raise Http404()
    return JsonResponse({
        "database_url_exists": bool(getattr(settings, "DATABASE_URL", "")),
        "engine": connection.settings_dict.get("ENGINE", ""),
        "host_visible": False,
        "credentials_visible": False,
    })
