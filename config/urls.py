from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from core.views import index

urlpatterns = [
    path("", index),
    path("feed/", include("posts.urls")),
    path("healthz", lambda request: HttpResponse("ok")),
    path("admin/", admin.site.urls),
]
