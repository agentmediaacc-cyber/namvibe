from django.urls import path

from .views import (
    live_chat_view,
    live_end_view,
    live_featured_view,
    live_home_view,
    live_message_view,
    live_gift_view,
    live_purchase_access_view,
    live_react_view,
    live_room_view,
    live_scheduled_view,
    live_start_view,
    live_studio_view,
)


urlpatterns = [
    path("", live_home_view, name="live_home"),
    path("featured/", live_featured_view, name="live_featured"),
    path("scheduled/", live_scheduled_view, name="live_scheduled"),
    path("start/", live_start_view, name="live_start"),
    path("studio/", live_studio_view, name="legacy_live_studio"),
    path("<uuid:uuid>/", live_room_view, name="live_room"),
    path("<uuid:uuid>/chat/", live_chat_view, name="live_chat"),
    path("<uuid:uuid>/message/", live_message_view, name="live_message"),
    path("<uuid:uuid>/gift/", live_gift_view, name="live_gift"),
    path("<uuid:uuid>/purchase/", live_purchase_access_view, name="live_purchase_access"),
    path("<uuid:uuid>/end/", live_end_view, name="live_end"),
    path("<uuid:uuid>/react/", live_react_view, name="live_react"),
]
