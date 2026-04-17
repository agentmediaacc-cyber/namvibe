from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include

def railway_home(request):
    return HttpResponse("ok")

urlpatterns = [
    path("", railway_home),
    path("healthz", railway_home),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("posts/", include("posts.urls")),
    path("feed/", include("posts.urls")),
    path("live/", include("live.urls")),
    path("wallet/", include("wallet.urls")),
    path("dating/", include("dating.urls")),
]
