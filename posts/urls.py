from django.urls import path
from .views import feed_view, create_post_view, save_post_view

urlpatterns = [
    path("", feed_view, name="feed"),
    path("create/", create_post_view, name="create_post"),
    path("save/", save_post_view, name="save_post"),
]
