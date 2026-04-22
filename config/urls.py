from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import include, path
from django.views.generic import RedirectView

from accounts.views import public_profile_view
from core.product_views import (
    channels_view,
    coins_view,
    flyer_tools_view,
    gaming_view,
    gifting_view,
    image_tools_view,
    notifications_view,
    photo_selling_view,
    premium_tier_view,
    support_view,
)
from core.views import (
    feed_live_view,
    feed_sponsored_view,
    feed_videos_view,
    index as real_index,
)
from posts.views import (
    add_comment_view,
    author_posts_list_view,
    community_posts_list_view,
    delete_comment_view,
    delete_post_view,
    discover_view,
    edit_post_view,
    hashtag_view,
    like_post_view,
    media_album_detail_view,
    media_albums_view,
    pin_comment_view,
    post_detail_view,
    preview_post_view,
    publish_draft_view,
    react_comment_view,
    reels_feed_view,
    reply_comment_view,
    report_post_view,
    report_user_view,
    save_draft_view,
    saved_posts_view,
    save_post_toggle_view,
    search_view,
    share_post_view,
    studio_draft_view,
    studio_view,
    track_post_view,
)
from supportapp.views import support_control_view


def community_list_alias(request):
    return redirect("community_list")


def settings_alias(request):
    return redirect("profile_edit")


def discover_people_alias(request):
    return redirect("dating")


def safe_index(request):
    try:
        return real_index(request)
    except Exception as exc:
        return HttpResponse(f"Namvibe safe mode<br><br>{exc}")


urlpatterns = [
    path("", safe_index, name="home"),
    path("favicon.ico", RedirectView.as_view(url=f"{settings.STATIC_URL}images/favicon.svg", permanent=False)),
    path("healthz", lambda request: HttpResponse("ok"), name="healthz"),
    path("admin/", admin.site.urls),
    path("notifications/", notifications_view, name="notifications"),
    path("channels/", channels_view, name="channels"),
    path("gaming/", gaming_view, name="gaming"),
    path("photo-selling/", photo_selling_view, name="photo_selling"),
    path("flyers/", flyer_tools_view, name="flyer_tools"),
    path("image-tools/", image_tools_view, name="image_tools"),
    path("gifting/", gifting_view, name="gifting"),
    path("coins/", coins_view, name="coins"),
    path("support/", support_view, name="support_help"),
    path("support/control/", support_control_view, name="support_control"),
    path("premium/<str:tier>/", premium_tier_view, name="premium_tier"),
    path("community-list/", community_list_alias, name="community_list_alias"),
    path("settings/", settings_alias, name="settings"),
    path("discover/people/", discover_people_alias, name="discover_people"),
    path("hashtags/<str:tag>/", hashtag_view, name="hashtag"),
    path("reels/", reels_feed_view, name="reels_feed"),
    path("discover/", discover_view, name="discover"),
    path("discover/search/", search_view, name="discover_search"),
    path("feed/videos/", feed_videos_view, name="feed_videos"),
    path("feed/live/", feed_live_view, name="feed_live"),
    path("feed/sponsored/", feed_sponsored_view, name="feed_sponsored"),
    path("studio/", studio_view, name="studio"),
    path("studio/create/", studio_view, name="studio_create"),
    path("studio/draft/<uuid:uuid>/", studio_draft_view, name="studio_draft"),
    path("profile/<str:username>/", public_profile_view, name="profile_detail"),
    path("profile/<str:username>/report/", report_user_view, name="report_user"),
    path("post/<uuid:uuid>/", post_detail_view, name="post_detail"),
    path("author/<str:username>/", author_posts_list_view, name="author_posts"),
    path("community/<slug:slug>/posts/", community_posts_list_view, name="community_posts"),
    path("like/<uuid:uuid>/", like_post_view, name="like_post"),
    path("save-toggle/<uuid:uuid>/", save_post_toggle_view, name="save_post_toggle"),
    path("share/<uuid:uuid>/", share_post_view, name="share_post"),
    path("track/<uuid:uuid>/", track_post_view, name="track_post_view"),
    path("report/<uuid:uuid>/", report_post_view, name="report_post"),
    path("comment/<uuid:uuid>/", add_comment_view, name="add_comment"),
    path("comment/<int:id>/reply/", reply_comment_view, name="reply_comment"),
    path("comment/<int:id>/delete/", delete_comment_view, name="delete_comment"),
    path("comment/<int:id>/pin/", pin_comment_view, name="pin_comment"),
    path("comment/<int:id>/react/", react_comment_view, name="react_comment"),
    path("delete/<uuid:uuid>/", delete_post_view, name="delete_post"),
    path("edit/<uuid:uuid>/", edit_post_view, name="edit_post"),
    path("draft/save/", save_draft_view, name="save_draft"),
    path("draft/publish/<uuid:uuid>/", publish_draft_view, name="publish_draft"),
    path("preview/<uuid:uuid>/", preview_post_view, name="preview_post"),
    path("saved/", saved_posts_view, name="saved_posts"),
    path("albums/", media_albums_view, name="media_albums"),
    path("albums/<str:kind>/", media_album_detail_view, name="media_album_detail"),
    path("accounts/", include("accounts.urls")),
    path("api/", include("api.urls")),
    path("posts/", include("posts.urls")),
    path("feed/", include("posts.urls")),
    path("live/", include("live.urls")),
    path("livestream/", include("livestream.urls")),
    path("messaging/", include(("messaging.urls", "messaging"), namespace="messaging")),
    path("wallet/", include("wallet.urls")),
    path("stories/", include("stories.urls")),
    path("ads/", include("ads.urls")),
    path("dating/", include("dating.urls")),
    path("communities/", include("communities.urls")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
