from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from core.views import index as real_index


def safe_index(request):
    try:
        return real_index(request)
    except Exception as e:
        return HttpResponse(f"Namvibe safe mode<br><br>{e}")


urlpatterns = [
    path("", safe_index),
    path("healthz", lambda request: HttpResponse("ok")),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("posts/", include("posts.urls")),
    path("feed/", include("posts.urls")),
    path("live/", include("live.urls")),
    path("wallet/", include("wallet.urls")),
    path("dating/", include("dating.urls")),
]
