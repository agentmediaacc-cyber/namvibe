from django.contrib import admin

from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "updated_at")
    filter_horizontal = ("participants",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "attachment_type", "read_at", "created_at")
    list_filter = ("attachment_type", "read_at", "created_at")
    search_fields = ("text", "sender__username", "sender__email")
