from django.urls import path

from .views import (
    dating_discover_view,
    dating_home_view,
    dating_like_view,
    dating_likes_view,
    dating_matches_view,
    dating_message_match_view,
    dating_pass_view,
    dating_profile_detail_view,
    dating_profile_edit_view,
)


urlpatterns = [
    path("", dating_home_view, name="dating"),
    path("profile/", dating_profile_edit_view, name="dating_profile_edit"),
    path("discover/", dating_discover_view, name="dating_discover"),
    path("matches/", dating_matches_view, name="dating_matches"),
    path("likes/", dating_likes_view, name="dating_likes"),
    path("<str:username>/", dating_profile_detail_view, name="dating_profile_detail"),
    path("<str:username>/message/", dating_message_match_view, name="dating_message_match"),
    path("action/like/<str:username>/", dating_like_view, name="dating_like"),
    path("action/pass/<str:username>/", dating_pass_view, name="dating_pass"),
]
