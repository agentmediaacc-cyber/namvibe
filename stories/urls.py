from django.urls import path

from .views import create_story_view, stories_home_view, story_comment_view, story_detail_view, story_like_view, story_report_view, story_share_view, story_view_view


urlpatterns = [
    path("", stories_home_view, name="stories_home"),
    path("create/", create_story_view, name="story_create"),
    path("<int:id>/", story_detail_view, name="story_detail"),
    path("<int:id>/like/", story_like_view, name="story_like"),
    path("<int:id>/comment/", story_comment_view, name="story_comment"),
    path("<int:id>/share/", story_share_view, name="story_share"),
    path("<int:id>/report/", story_report_view, name="story_report"),
    path("<int:id>/view/", story_view_view, name="story_view"),
]
