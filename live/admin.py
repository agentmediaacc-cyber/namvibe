from django.contrib import admin

from .models import LiveAccessPurchase, LiveGift, LiveMessage, LiveModerator, LiveReaction, LiveSession


@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    list_display = ("title", "host", "status", "access_type", "viewer_count", "peak_viewer_count", "like_count", "is_featured", "starts_at")
    search_fields = ("title", "description", "host__username", "host__profile__display_name")
    list_filter = ("status", "access_type", "chat_enabled", "is_featured", "starts_at")
    readonly_fields = ("uuid", "viewer_count", "peak_viewer_count", "like_count", "created_at", "updated_at")


@admin.register(LiveMessage)
class LiveMessageAdmin(admin.ModelAdmin):
    list_display = ("session", "user", "is_deleted", "created_at")
    search_fields = ("session__title", "user__username", "body")
    list_filter = ("is_deleted", "created_at")
    readonly_fields = ("created_at",)


@admin.register(LiveReaction)
class LiveReactionAdmin(admin.ModelAdmin):
    list_display = ("session", "user", "reaction_type", "created_at")
    search_fields = ("session__title", "user__username")
    list_filter = ("reaction_type", "created_at")
    readonly_fields = ("created_at",)


@admin.register(LiveModerator)
class LiveModeratorAdmin(admin.ModelAdmin):
    list_display = ("session", "user", "role", "created_at")
    search_fields = ("session__title", "user__username")
    list_filter = ("role", "created_at")
    readonly_fields = ("created_at",)


@admin.register(LiveGift)
class LiveGiftAdmin(admin.ModelAdmin):
    list_display = ("session", "sender", "gift_name", "token_amount", "created_at")
    search_fields = ("session__title", "sender__username", "gift_name")
    list_filter = ("gift_name", "created_at")
    readonly_fields = ("created_at",)


@admin.register(LiveAccessPurchase)
class LiveAccessPurchaseAdmin(admin.ModelAdmin):
    list_display = ("session", "user", "amount", "is_active", "created_at")
    search_fields = ("session__title", "user__username")
    list_filter = ("is_active", "created_at")
    readonly_fields = ("created_at",)
