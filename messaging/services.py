from django.contrib.auth import get_user_model
from django.db.models import Max

from .forms import MessageForm
from .models import Conversation


def conversations_for_user(user):
    return (
        Conversation.objects.filter(participants=user)
        .annotate(last_message_at=Max("messages__created_at"))
        .order_by("-last_message_at", "-updated_at")
        .prefetch_related("participants", "messages")
    )


def get_user_conversation(user, conversation_id):
    if not conversation_id:
        return None
    return conversations_for_user(user).filter(pk=conversation_id).first()


def get_or_create_direct_conversation(user, other_user):
    existing = (
        Conversation.objects.filter(participants=user)
        .filter(participants=other_user)
        .distinct()
        .first()
    )
    if existing:
        return existing

    conversation = Conversation.objects.create()
    conversation.participants.add(user, other_user)
    return conversation


def messaging_dashboard_context(user, conversation_id=None):
    conversations = list(conversations_for_user(user))
    active_conversation = get_user_conversation(user, conversation_id)
    selected_conversation_id = bool(conversation_id and active_conversation)

    if active_conversation:
        active_conversation.mark_read_for(user)

    conversation_items = []
    for conversation in conversations:
        messages = list(conversation.messages.all())
        last_message = messages[-1] if messages else None
        conversation_items.append({
            "conversation": conversation,
            "other": conversation.other_participant(user),
            "unread_count": conversation.unread_count_for(user),
            "last_message": last_message,
        })

    active_messages = []
    active_other = None
    if active_conversation:
        active_other = active_conversation.other_participant(user)
        active_messages = list(
            active_conversation.messages.select_related("sender", "reply_to", "reply_to__sender", "forwarded_from")
        )

    return {
        "chat_conversations": conversation_items,
        "active_conversation": active_conversation,
        "has_selected_conversation": selected_conversation_id,
        "active_chat_other": active_other,
        "active_messages": active_messages,
        "message_form": MessageForm(),
        "all_chat_users": get_user_model().objects.exclude(pk=user.pk).order_by("username")[:25],
    }
