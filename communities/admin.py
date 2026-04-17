from django.contrib import admin

from .models import Community, CommunityMembership


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "privacy", "owner", "member_count", "created_at")
    search_fields = ("name", "slug", "description", "owner__username")
    list_filter = ("privacy", "created_at")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("member_count", "created_at", "updated_at")


@admin.register(CommunityMembership)
class CommunityMembershipAdmin(admin.ModelAdmin):
    list_display = ("community", "user", "role", "status", "created_at")
    search_fields = ("community__name", "community__slug", "user__username")
    list_filter = ("role", "status", "created_at")
    readonly_fields = ("created_at", "updated_at")
