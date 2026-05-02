from django.urls import path
from . import views

urlpatterns = [
    path("", views.stories_home_view, name="stories_home"),
    path("create/", views.create_story_view, name="story_create"),
    path("<int:id>/", views.story_detail_view, name="story_detail"),
    path("<int:id>/like/", views.story_like_view, name="story_like"),
    path("<int:id>/comment/", views.story_comment_view, name="story_comment"),
    path("<int:id>/share/", views.story_share_view, name="story_share"),
    path("<int:id>/report/", views.story_report_view, name="story_report"),
    path("<int:id>/view/", views.story_view_view, name="story_view"),
    path("<int:id>/viewers/", views.story_viewers_view, name="story_viewers"),
]
