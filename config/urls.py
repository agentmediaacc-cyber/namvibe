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


# === ALIASES FOR TEMPLATE COMPATIBILITY ===
from django.shortcuts import redirect

def alias(to):
    return lambda request, *a, **kw: redirect(to)

urlpatterns += [
    path("reels/", alias("/posts/reels/feed/"), name="reels_feed"),
    path("discover/", alias("/posts/discover/"), name="discover"),
    path("discover/search/", alias("/posts/discover/search/"), name="discover_search"),
    path("studio/", alias("/posts/studio/"), name="studio"),

    path("profile/<str:username>/", alias("/accounts/profile/"), name="profile_detail"),

    path("post/<uuid:uuid>/", alias("/posts/"), name="post_detail"),

    path("like/<uuid:uuid>/", alias("/posts/"), name="like_post"),
    path("save-toggle/<uuid:uuid>/", alias("/posts/"), name="save_post_toggle"),
    path("share/<uuid:uuid>/", alias("/posts/"), name="share_post"),

    path("comment/<uuid:uuid>/", alias("/posts/"), name="add_comment"),
    path("delete/<uuid:uuid>/", alias("/posts/"), name="delete_post"),
    path("edit/<uuid:uuid>/", alias("/posts/"), name="edit_post"),

    path("draft/save/", alias("/posts/studio/draft/"), name="save_draft"),
    path("draft/publish/<uuid:uuid>/", alias("/posts/"), name="publish_draft"),
    path("preview/<uuid:uuid>/", alias("/posts/"), name="preview_post"),
]
