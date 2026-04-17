from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from core.views import index as real_index
from django.shortcuts import redirect

def community_list_alias(request):
    return redirect("/communities/")


def safe_index(request):
    try:
        return real_index(request)
    except Exception as e:
        return HttpResponse(f"Namvibe safe mode<br><br>{e}")


urlpatterns = [
    path("", safe_index, name="home"),
    path("healthz", lambda request: HttpResponse("ok")),
    path("admin/", admin.site.urls),
    path("community-list/", community_list_alias, name="community_list"),
    path("accounts/", include("accounts.urls")),
    path("posts/", include("posts.urls")),
    path("feed/", include("posts.urls")),
    path("live/", include("live.urls")),
    path("wallet/", include("wallet.urls")),
    path("dating/", include("dating.urls")),
    path("communities/", include(("communities.urls", "communities"), namespace="communities")),
]
