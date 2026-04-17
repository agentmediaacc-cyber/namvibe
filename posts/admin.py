from django.contrib import admin

from .models import (
    Comment,
    CommentReaction,
    FlyerMeta,
    Like,
    LiveAnnouncement,
    Poll,
    PollOption,
    PollVote,
    Post,
    PostMedia,
    PostView,
    Report,
    Save,
    Share,
)


class PostMediaInline(admin.TabularInline):
    model = PostMedia
    extra = 0
    readonly_fields = ("created_at",)


class PollOptionInline(admin.TabularInline):
    model = PollOption
    extra = 2


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "post_type",
        "audience",
        "share_target",
        "status",
        "premium_badge",
        "published_at",
        "view_count",
        "like_count",
        "comment_count",
    )
    search_fields = ("title", "caption", "author__username", "hashtags", "mentions")
    list_filter = ("post_type", "audience", "share_target", "status", "premium_badge", "is_sensitive", "published_at")
    readonly_fields = (
        "uuid",
        "view_count",
        "like_count",
        "comment_count",
        "share_count",
        "save_count",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "published_at"
    inlines = [PostMediaInline]


@admin.register(PostMedia)
class PostMediaAdmin(admin.ModelAdmin):
    list_display = ("post", "media_type", "sort_order", "display_mode", "crop_style", "image_effect", "created_at")
    search_fields = ("post__title", "alt_text", "overlay_text")
    list_filter = ("media_type", "display_mode", "crop_style", "image_effect")
    readonly_fields = ("created_at",)


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ("question", "post", "multiple_choice", "closes_at")
    search_fields = ("question", "post__title")
    list_filter = ("multiple_choice", "closes_at")
    inlines = [PollOptionInline]


@admin.register(PollOption)
class PollOptionAdmin(admin.ModelAdmin):
    list_display = ("text", "poll", "vote_count", "sort_order")
    search_fields = ("text", "poll__question")
    readonly_fields = ("vote_count",)


@admin.register(PollVote)
class PollVoteAdmin(admin.ModelAdmin):
    list_display = ("poll", "option", "user", "created_at")
    search_fields = ("poll__question", "option__text", "user__username")
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)


@admin.register(FlyerMeta)
class FlyerMetaAdmin(admin.ModelAdmin):
    list_display = ("flyer_title", "post", "call_to_action", "background_style", "layout_style")
    search_fields = ("flyer_title", "body", "call_to_action", "post__title")
    list_filter = ("background_style", "layout_style")


@admin.register(LiveAnnouncement)
class LiveAnnouncementAdmin(admin.ModelAdmin):
    list_display = ("stream_title", "post", "scheduled_for", "access_type", "ticket_price")
    search_fields = ("stream_title", "post__title")
    list_filter = ("access_type", "scheduled_for")


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("user", "post", "reaction_type", "created_at")
    search_fields = ("user__username", "post__title")
    list_filter = ("reaction_type", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("author", "post", "parent", "is_pinned", "is_deleted", "like_count", "created_at")
    search_fields = ("author__username", "post__title", "body")
    list_filter = ("is_pinned", "is_deleted", "created_at")
    readonly_fields = ("like_count", "created_at", "updated_at")


@admin.register(CommentReaction)
class CommentReactionAdmin(admin.ModelAdmin):
    list_display = ("user", "comment", "reaction_type", "created_at")
    search_fields = ("user__username", "comment__body")
    list_filter = ("reaction_type", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = ("user", "post", "target", "created_at")
    search_fields = ("user__username", "post__title", "message")
    list_filter = ("target", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Save)
class SaveAdmin(admin.ModelAdmin):
    list_display = ("user", "post", "created_at")
    search_fields = ("user__username", "post__title")
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)


@admin.register(PostView)
class PostViewAdmin(admin.ModelAdmin):
    list_display = ("post", "user", "session_key", "duration_seconds", "completed", "created_at")
    search_fields = ("post__title", "user__username", "session_key")
    list_filter = ("completed", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("reporter", "post", "reported_user", "reason", "status", "created_at")
    search_fields = ("reporter__username", "post__title", "reported_user__username", "details")
    list_filter = ("reason", "status", "created_at")
    readonly_fields = ("created_at", "updated_at")
