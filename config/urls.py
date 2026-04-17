from django.contrib import admin
from django.http import HttpResponse
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from accounts.views import public_profile_view
from core.views import index, settings_entry_view
from posts.views import (
    add_comment_view,
    author_posts_list_view,
    community_feed_view,
    community_suggestions_view,
    community_posts_list_view,
    delete_post_view,
    delete_comment_view,
    discover_view,
    edit_post_view,
    following_feed_view,
    friends_feed_view,
    hashtag_view,
    like_post_view,
    nearby_feed_view,
    people_suggestions_view,
    pin_comment_view,
    post_detail_view,
    preview_post_view,
    publish_draft_view,
    reels_feed_view,
    reply_comment_view,
    report_post_view,
    report_user_view,
    save_post_toggle_view,
    search_view,
    save_draft_view,
    share_post_view,
    studio_draft_view,
    studio_view,
    track_post_view,
    trending_feed_view,
)

urlpatterns = [
    path("", index, name="home"),
    path("healthz", lambda request: HttpResponse("ok")),
    path("admin/", admin.site.urls),
    path("settings/", settings_entry_view, name="settings"),
    path("profile/<str:username>/", public_profile_view, name="profile_detail"),
    path("studio/", studio_view, name="studio"),
    path("studio/create/", studio_view, name="studio_create"),
    path("studio/draft/", save_draft_view, name="save_draft"),
    path("studio/draft/<uuid:uuid>/", studio_draft_view, name="studio_draft"),
    path("studio/preview/<uuid:uuid>/", preview_post_view, name="preview_post"),
    path("post/<uuid:uuid>/", post_detail_view, name="post_detail"),
    path("post/<uuid:uuid>/edit/", edit_post_view, name="edit_post"),
    path("post/<uuid:uuid>/delete/", delete_post_view, name="delete_post"),
    path("post/<uuid:uuid>/publish/", publish_draft_view, name="publish_draft"),
    path("post/<uuid:uuid>/like/", like_post_view, name="like_post"),
    path("post/<uuid:uuid>/save/", save_post_toggle_view, name="save_post_toggle"),
    path("post/<uuid:uuid>/share/", share_post_view, name="share_post"),
    path("post/<uuid:uuid>/view/", track_post_view, name="track_post_view"),
    path("post/<uuid:uuid>/comment/", add_comment_view, name="add_comment"),
    path("post/<uuid:uuid>/report/", report_post_view, name="report_post"),
    path("comment/<int:id>/reply/", reply_comment_view, name="reply_comment"),
    path("comment/<int:id>/delete/", delete_comment_view, name="delete_comment"),
    path("comment/<int:id>/pin/", pin_comment_view, name="pin_comment"),
    path("profile/<str:username>/posts/", author_posts_list_view, name="author_posts"),
    path("profile/<str:username>/report/", report_user_view, name="report_user"),
    path("communities/<slug:slug>/posts/", community_posts_list_view, name="community_posts"),
    path("communities/<slug:slug>/feed/", community_feed_view, name="community_feed"),
    path("reels/feed/", reels_feed_view, name="reels_feed"),
    path("discover/", discover_view, name="discover"),
    path("discover/search/", search_view, name="discover_search"),
    path("discover/people/", people_suggestions_view, name="discover_people"),
    path("discover/communities/", community_suggestions_view, name="discover_communities"),
    path("hashtags/<str:tag>/", hashtag_view, name="hashtag"),
]

try:
    urlpatterns += [path("dating/", include("dating.urls"))]
except Exception:
    pass

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

try:
    urlpatterns += [path("communities/", include("communities.urls"))]
except Exception:
    pass

try:
    urlpatterns += [path("stories/", include("stories.urls"))]
except Exception:
    pass

try:
    urlpatterns += [path("ads/", include("ads.urls"))]
except Exception:
    pass

try:
    urlpatterns += [path("wallet/", include("wallet.urls"))]
except Exception:
    pass

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
