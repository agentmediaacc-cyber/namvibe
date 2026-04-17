from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from core.views import index  # your real homepage

urlpatterns = [
    path("", index),  # ✅ restore real homepage
    path("healthz", lambda request: HttpResponse("ok")),  # keep for Railway
    path("admin/", admin.site.urls),

    # apps
    path("accounts/", include("accounts.urls")),
    path("posts/", include("posts.urls")),
    path("feed/", include("posts.urls")),
    path("live/", include("live.urls")),
    path("wallet/", include("wallet.urls")),
    path("dating/", include("dating.urls")),
]
