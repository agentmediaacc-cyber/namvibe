from django.urls import path

from .views import ad_click_view


urlpatterns = [
    path("<int:id>/click/", ad_click_view, name="ad_click"),
]
