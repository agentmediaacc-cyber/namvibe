from django.contrib import admin

from .models import LiveComment, LiveGift, LiveRoom, LiveViewer


@admin.register(LiveRoom)
class LiveRoomAdmin(admin.ModelAdmin):
    list_display = ("title", "host", "status", "audience", "room_access", "viewer_count", "created_at")
    list_filter = ("status", "audience", "room_access", "allow_gifts", "allow_comments")
    search_fields = ("title", "host__username", "host_full_name", "host_username")
    readonly_fields = ("id", "created_at", "updated_at", "started_at", "ended_at")


@admin.register(LiveComment)
class LiveCommentAdmin(admin.ModelAdmin):
    list_display = ("room", "username", "is_host", "created_at")
    list_filter = ("is_host", "created_at")
    search_fields = ("room__title", "username", "message")


@admin.register(LiveGift)
class LiveGiftAdmin(admin.ModelAdmin):
    list_display = ("room", "sender_username", "gift_name", "token_amount", "created_at")
    list_filter = ("gift_name", "created_at")
    search_fields = ("room__title", "sender_username", "gift_name")


@admin.register(LiveViewer)
class LiveViewerAdmin(admin.ModelAdmin):
    list_display = ("room", "display_name", "user", "joined_at", "last_seen_at")
    search_fields = ("room__title", "display_name", "user__username")
