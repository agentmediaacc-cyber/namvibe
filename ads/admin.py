from django.contrib import admin

from .models import Advertisement


@admin.action(description="Mark selected ads active")
def mark_active(modeladmin, request, queryset):
    queryset.update(status=Advertisement.Status.ACTIVE)


@admin.action(description="Pause selected ads")
def mark_paused(modeladmin, request, queryset):
    queryset.update(status=Advertisement.Status.PAUSED)


@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    list_display = ("title", "sponsor_name", "placement", "status", "priority", "starts_at", "ends_at", "impression_count", "click_count")
    search_fields = ("title", "sponsor_name", "description", "slug")
    list_filter = ("placement", "status", "is_public", "starts_at", "ends_at")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("impression_count", "click_count", "created_at", "updated_at")
    actions = [mark_active, mark_paused]
