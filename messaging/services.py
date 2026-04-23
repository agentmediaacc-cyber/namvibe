from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Max

from accounts.models import Follow, Profile
from wallet.services import active_membership_for, ensure_wallet

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


def _recommended_chat_users(user, conversation_items):
    existing_user_ids = {
        item["other"].id
        for item in conversation_items
        if item.get("other") is not None
    }
    candidate_ids = []

    following_ids = list(
        Follow.objects.filter(follower=user)
        .order_by("-created_at")
        .values_list("following_id", flat=True)[:12]
    )
    follower_ids = list(
        Follow.objects.filter(following=user)
        .order_by("-created_at")
        .values_list("follower_id", flat=True)[:12]
    )
    creator_ids = list(
        Profile.objects.filter(is_creator=True)
        .exclude(user=user)
        .order_by("-follower_count", "-post_count")
        .values_list("user_id", flat=True)[:12]
    )

    for candidate_id in [*following_ids, *follower_ids, *creator_ids]:
        if candidate_id and candidate_id not in existing_user_ids and candidate_id != user.id and candidate_id not in candidate_ids:
            candidate_ids.append(candidate_id)

    if not candidate_ids:
        return list(get_user_model().objects.exclude(pk=user.pk).order_by("username")[:18])

    ordering = {candidate_id: idx for idx, candidate_id in enumerate(candidate_ids)}
    users = list(get_user_model().objects.filter(pk__in=candidate_ids).select_related("profile"))
    users.sort(key=lambda candidate: ordering.get(candidate.id, len(ordering)))
    return users[:18]


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
            "message_count": len(messages),
        })

    active_messages = []
    active_other = None
    if active_conversation:
        active_other = active_conversation.other_participant(user)
        active_messages = list(
            active_conversation.messages.select_related("sender", "reply_to", "reply_to__sender", "forwarded_from")
        )

    unread_total = sum(item["unread_count"] for item in conversation_items)
    media_message_count = sum(1 for item in active_messages if item.attachment) if active_messages else 0
    recommended_users = _recommended_chat_users(user, conversation_items)

    return {
        "chat_conversations": conversation_items,
        "active_conversation": active_conversation,
        "has_selected_conversation": selected_conversation_id,
        "active_chat_other": active_other,
        "active_messages": active_messages,
        "message_form": MessageForm(),
        "all_chat_users": recommended_users,
        "chat_unread_total": unread_total,
        "chat_unread_threads": sum(1 for item in conversation_items if item["unread_count"]),
        "chat_total_messages": sum(item["message_count"] for item in conversation_items),
        "chat_media_messages": media_message_count,
    }


def call_gate_state(user, mode="voice"):
    cost = Decimal("25.00") if mode == "video" else Decimal("10.00")
    membership = active_membership_for(user)
    wallet = ensure_wallet(user)
    unlocked = bool(membership) or wallet.available_balance >= cost
    return {
        "mode": mode,
        "cost": cost,
        "wallet": wallet,
        "membership": membership,
        "unlocked": unlocked,
        "reason": "Premium members can start calls without token charges." if membership else f"{mode.title()} calls require Premium or N${cost} in wallet credits.",
    }
