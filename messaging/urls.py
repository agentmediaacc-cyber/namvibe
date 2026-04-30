from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.messages_home_view, name="messages_home"),
    path("conversation/<int:conversation_id>/", views.conversation_redirect, name="conversation"),
    path("conversation/<int:conversation_id>/send/", views.send_message, name="send_message"),
    path("message/<int:message_id>/delete/", views.delete_message, name="delete_message"),
    path("start/<int:user_id>/", views.start_chat, name="start_chat"),
    path("calls/start/<int:user_id>/", views.call_lobby_view, name="call_lobby"),
    path("call/<int:user_id>/<str:mode>/", views.call_gate_view, name="call_gate"),
]
