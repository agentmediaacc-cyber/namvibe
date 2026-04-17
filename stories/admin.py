from django.contrib import admin

from .models import StoryComment, StoryItem, StoryReaction, StoryShare, StoryView


@admin.register(StoryItem)
class StoryItemAdmin(admin.ModelAdmin):
    list_display = ("author", "media_type", "audience", "expires_at", "view_count", "like_count", "comment_count", "share_count")
    search_fields = ("author__username", "text_content", "caption")
    list_filter = ("media_type", "audience", "expires_at", "created_at")
    readonly_fields = ("view_count", "like_count", "comment_count", "share_count", "created_at")


@admin.register(StoryView)
class StoryViewAdmin(admin.ModelAdmin):
    list_display = ("story", "viewer", "session_key", "created_at")
    search_fields = ("story__author__username", "viewer__username", "session_key")
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)


@admin.register(StoryReaction)
class StoryReactionAdmin(admin.ModelAdmin):
    list_display = ("story", "user", "reaction_type", "created_at")
    search_fields = ("story__author__username", "user__username")
    list_filter = ("reaction_type", "created_at")
    readonly_fields = ("created_at",)


@admin.register(StoryComment)
class StoryCommentAdmin(admin.ModelAdmin):
    list_display = ("story", "author", "created_at")
    search_fields = ("story__author__username", "author__username", "body")
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)


@admin.register(StoryShare)
class StoryShareAdmin(admin.ModelAdmin):
    list_display = ("story", "user", "target", "created_at")
    search_fields = ("story__author__username", "user__username", "target")
    list_filter = ("target", "created_at")
    readonly_fields = ("created_at",)
