from django.urls import path

from .consumers import CallSignalingConsumer, ChatConsumer


websocket_urlpatterns = [
    path("ws/messages/<int:conversation_id>/", ChatConsumer.as_asgi()),
    path("ws/calls/<int:conversation_id>/", CallSignalingConsumer.as_asgi()),
]
