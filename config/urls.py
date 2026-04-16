from django.contrib import admin
from django.http import HttpResponse
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from core.views import index

urlpatterns = [
    path("", index, name="home"),
    path("healthz", lambda request: HttpResponse("ok")),
    path("admin/", admin.site.urls),
]

try:
    urlpatterns += [path("api/", include("api.urls"))]
except Exception:
    pass

try:
    urlpatterns += [path("accounts/", include("accounts.urls"))]
except Exception:
    pass

try:
    urlpatterns += [path("posts/", include("posts.urls"))]
except Exception:
    pass

try:
    urlpatterns += [path("feed/", include("posts.urls"))]
except Exception:
    pass

try:
    urlpatterns += [path("live/", include("live.urls"))]
except Exception:
    pass

try:
    urlpatterns += [path("livestream/", include("livestream.urls"))]
except Exception:
    pass

try:
    urlpatterns += [path("messages/", include("messaging.urls"))]
except Exception:
    pass

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
