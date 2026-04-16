from django.contrib import admin
from .models import AccountProfile


@admin.register(AccountProfile)
class AccountProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "cellphone_number", "current_country", "created_at")
    search_fields = ("full_name", "email", "cellphone_number", "user__username")
    list_filter = ("current_country", "country_of_origin", "profile_completed")
