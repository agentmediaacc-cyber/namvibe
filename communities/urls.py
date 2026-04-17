from django.urls import path

from .views import community_create_view, community_detail_view, community_join_view, community_list_view


urlpatterns = [
    path("", community_list_view, name="community_list"),
    path("create/", community_create_view, name="community_create"),
    path("<slug:slug>/", community_detail_view, name="community_detail"),
    path("<slug:slug>/join/", community_join_view, name="community_join"),
]
