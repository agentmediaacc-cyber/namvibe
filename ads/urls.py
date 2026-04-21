from django.urls import path

from .views import ad_click_view, ads_home_view, ads_starter_view


urlpatterns = [
    path("", ads_home_view, name="ads_home"),
    path("promotions/", ads_starter_view, name="ads_starter"),
    path("<int:id>/click/", ad_click_view, name="ad_click"),
]
