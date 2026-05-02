from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def notification_group_name(user_id):
    return f"user_notifications_{user_id}"


def conversation_group_name(conversation_id):
    return f"conversation_{conversation_id}"


def call_group_name(conversation_id):
    return f"call_room_{conversation_id}"


def _group_send(group_name, event):
    layer = get_channel_layer()
    if not layer:
        return False
    try:
        async_to_sync(layer.group_send)(group_name, event)
        return True
    except Exception:
        return False


def _notification_counts_for(user):
    from accounts.models import Notification
    from messaging.models import Message

    notification_count = Notification.objects.filter(recipient=user, is_read=False).count()
    message_count = (
        Message.objects.filter(conversation__participants=user, read_at__isnull=True)
        .exclude(sender=user)
        .count()
    )
    return notification_count, message_count


def push_notification_counts(user):
    notification_count, message_count = _notification_counts_for(user)
    return _group_send(
        notification_group_name(user.id),
        {
            "type": "notification.counts",
            "payload": {
                "notification_count": notification_count,
                "message_count": message_count,
            },
        },
    )


def push_notification_event(notification, title=None):
    user = notification.recipient
    notification_count, message_count = _notification_counts_for(user)
    sender = getattr(notification, "sender", None)
    return _group_send(
        notification_group_name(user.id),
        {
            "type": "notification.event",
            "payload": {
                "id": notification.id,
                "title": title or "Notification",
                "notification_type": notification.notification_type,
                "message": notification.message,
                "target_url": notification.target_url or "/notifications/",
                "created_at": notification.created_at.isoformat(),
                "is_read": notification.is_read,
                "notification_count": notification_count,
                "message_count": message_count,
                "sender": {
                    "id": getattr(sender, "id", None),
                    "username": getattr(sender, "username", ""),
                },
            },
        },
    )


def push_message_badge(user):
    notification_count, message_count = _notification_counts_for(user)
    return _group_send(
        notification_group_name(user.id),
        {
            "type": "message.badge",
            "payload": {
                "notification_count": notification_count,
                "message_count": message_count,
            },
        },
    )
