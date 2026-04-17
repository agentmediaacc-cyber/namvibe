from django.contrib import admin

from .models import CreatorEntitlement, GiftCatalog, GiftEvent, MembershipPlan, UserMembership, WalletAccount, WalletTransaction


@admin.register(WalletAccount)
class WalletAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "available_balance", "pending_balance", "lifetime_earned", "lifetime_spent", "is_active", "updated_at")
    search_fields = ("user__username", "user__email", "user__profile__display_name")
    list_filter = ("is_active", "created_at")
    readonly_fields = ("created_at", "updated_at")


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("uuid", "wallet", "transaction_type", "status", "amount", "currency", "created_at", "completed_at")
    search_fields = ("uuid", "wallet__user__username", "reference")
    list_filter = ("transaction_type", "status", "currency", "created_at")
    readonly_fields = ("uuid", "created_at", "completed_at")


@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "price", "billing_period", "is_active", "updated_at")
    search_fields = ("name", "slug", "description")
    list_filter = ("billing_period", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")


@admin.register(UserMembership)
class UserMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "starts_at", "ends_at", "auto_renew")
    search_fields = ("user__username", "plan__name")
    list_filter = ("status", "auto_renew", "plan")
    readonly_fields = ("created_at", "updated_at")


@admin.register(GiftCatalog)
class GiftCatalogAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "coin_cost", "value_to_creator", "is_active", "created_at")
    search_fields = ("name", "slug")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at",)


@admin.register(GiftEvent)
class GiftEventAdmin(admin.ModelAdmin):
    list_display = ("gift", "sender", "recipient", "live_session", "quantity", "total_cost", "creator_value", "created_at")
    search_fields = ("gift__name", "sender__username", "recipient__username", "live_session__title")
    list_filter = ("gift", "created_at")
    readonly_fields = ("created_at",)


@admin.register(CreatorEntitlement)
class CreatorEntitlementAdmin(admin.ModelAdmin):
    list_display = ("buyer", "creator", "live_session", "entitlement_type", "active", "starts_at", "ends_at")
    search_fields = ("buyer__username", "creator__username", "live_session__title")
    list_filter = ("entitlement_type", "active", "starts_at")
    readonly_fields = ("created_at",)
