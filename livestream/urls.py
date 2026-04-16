from django.urls import path
from .views import (
    live_studio_view,
    live_join_view,
    live_broadcast_view,
    live_rooms_api,
    create_live_room_api,
    start_live_room_api,
    end_live_room_api,
    update_live_room_api,
    live_comments_api,
    create_live_comment_api,
    live_gifts_api,
    create_live_gift_api,
)

urlpatterns = [
    path('studio/', live_studio_view, name='live_studio'),
    path('room/<uuid:room_id>/', live_join_view, name='live_join'),
    path('broadcast/<uuid:room_id>/', live_broadcast_view, name='live_broadcast'),
    path('api/rooms/', live_rooms_api, name='live_rooms_api'),
    path('api/rooms/create/', create_live_room_api, name='create_live_room_api'),
    path('api/rooms/<uuid:room_id>/start/', start_live_room_api, name='start_live_room_api'),
    path('api/rooms/<uuid:room_id>/end/', end_live_room_api, name='end_live_room_api'),
    path('api/rooms/<uuid:room_id>/update/', update_live_room_api, name='update_live_room_api'),
    path('api/rooms/<uuid:room_id>/comments/', live_comments_api, name='live_comments_api'),
    path('api/rooms/<uuid:room_id>/comments/create/', create_live_comment_api, name='create_live_comment_api'),
    path('api/rooms/<uuid:room_id>/gifts/', live_gifts_api, name='live_gifts_api'),
    path('api/rooms/<uuid:room_id>/gifts/create/', create_live_gift_api, name='create_live_gift_api'),
]
