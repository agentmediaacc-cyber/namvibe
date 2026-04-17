from django.contrib import admin
from .models import AccountProfile, Block, Follow, FriendRequest, Mute, Profile


@admin.register(AccountProfile)
class AccountProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "cellphone_number", "current_country", "created_at")
    search_fields = ("full_name", "email", "cellphone_number", "user__username")
    list_filter = ("current_country", "country_of_origin", "profile_completed")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "display_name",
        "user",
        "location",
        "is_creator",
        "is_verified",
        "is_private",
        "follower_count",
        "following_count",
        "post_count",
    )
    search_fields = ("username", "display_name", "user__username", "user__email", "location")
    list_filter = ("is_creator", "is_verified", "is_private", "location")
    readonly_fields = ("follower_count", "following_count", "post_count", "created_at", "updated_at")


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("follower", "following", "created_at")
    search_fields = ("follower__username", "following__username")
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)


@admin.register(FriendRequest)
class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ("from_user", "to_user", "status", "created_at", "updated_at")
    search_fields = ("from_user__username", "to_user__username")
    list_filter = ("status", "created_at")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("blocker", "blocked", "created_at")
    search_fields = ("blocker__username", "blocked__username")
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)


@admin.register(Mute)
class MuteAdmin(admin.ModelAdmin):
    list_display = ("muter", "muted", "created_at")
    search_fields = ("muter__username", "muted__username")
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)
