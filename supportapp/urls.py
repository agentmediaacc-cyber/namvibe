from django.urls import path

from .views import support_control_view, support_home_view


urlpatterns = [
    path("", support_home_view, name="support_center"),
    path("control/", support_control_view, name="support_control"),
]
