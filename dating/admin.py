from django.contrib import admin

from .models import DatingCoinBalance, DatingLike, DatingPass, DatingPhoto, DatingPreference, DatingProfile, Match


class DatingPhotoInline(admin.TabularInline):
    model = DatingPhoto
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(DatingProfile)
class DatingProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "gender", "city", "region", "relationship_goal", "premium_tier", "is_visible", "is_verified_dating", "created_at")
    search_fields = ("display_name", "user__username", "bio", "city", "region", "occupation")
    list_filter = ("gender", "relationship_goal", "premium_tier", "is_visible", "is_verified_dating", "city", "region")
    readonly_fields = ("created_at", "updated_at")
    inlines = [DatingPhotoInline]


@admin.register(DatingPhoto)
class DatingPhotoAdmin(admin.ModelAdmin):
    list_display = ("dating_profile", "sort_order", "is_primary", "created_at")
    search_fields = ("dating_profile__display_name", "dating_profile__user__username")
    list_filter = ("is_primary", "created_at")
    readonly_fields = ("created_at",)


@admin.register(DatingPreference)
class DatingPreferenceAdmin(admin.ModelAdmin):
    list_display = ("dating_profile", "age_min", "age_max", "preferred_region", "preferred_city", "distance_km")
    search_fields = ("dating_profile__display_name", "preferred_region", "preferred_city")


@admin.register(DatingLike)
class DatingLikeAdmin(admin.ModelAdmin):
    list_display = ("from_user", "to_user", "is_super_like", "created_at")
    search_fields = ("from_user__username", "to_user__username")
    list_filter = ("is_super_like", "created_at",)
    readonly_fields = ("created_at",)


@admin.register(DatingPass)
class DatingPassAdmin(admin.ModelAdmin):
    list_display = ("from_user", "to_user", "created_at")
    search_fields = ("from_user__username", "to_user__username")
    list_filter = ("created_at",)
    readonly_fields = ("created_at",)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("user_one", "user_two", "is_active", "created_at")
    search_fields = ("user_one__username", "user_two__username")
    list_filter = ("is_active", "created_at")
    readonly_fields = ("created_at",)


@admin.register(DatingCoinBalance)
class DatingCoinBalanceAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "updated_at")
    search_fields = ("user__username",)
    readonly_fields = ("updated_at",)
