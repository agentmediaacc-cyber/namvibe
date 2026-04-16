from django.urls import path

from .consumers import LiveRoomConsumer

websocket_urlpatterns = [
    path("ws/livestream/rooms/<uuid:room_id>/", LiveRoomConsumer.as_asgi()),
]
