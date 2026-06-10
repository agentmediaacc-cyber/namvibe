import uuid
import os
import json
from datetime import datetime, timezone
from services.notification_engine import (
    create_notification as engine_create,
    list_notifications as engine_list,
    list_notifications_tab,
    unread_count as engine_unread_count,
    mark_read as engine_mark_read,
    mark_all_read as engine_mark_all_read,
    delete_notification as engine_delete,
    delete_selected_notifications,
    mute_notification_type,
    get_notification_preferences,
    update_notification_preferences,
    _NOTIF_TYPE_CATEGORIES,
    _NOTIF_ICONS,
)

_NOTIFICATION_TYPE_CATEGORIES = _NOTIF_TYPE_CATEGORIES
_NOTIFICATION_ICONS = _NOTIF_ICONS


def format_notification(row):
    if not row:
        return None
    d = dict(row)
    d["category"] = _NOTIFICATION_TYPE_CATEGORIES.get(d.get("notification_type", ""), "activity")
    d["icon"] = _NOTIFICATION_ICONS.get(d.get("notification_type", ""), "fa-bell")
    if isinstance(d.get("created_at"), datetime):
        d["created_at"] = d["created_at"].isoformat()
    if isinstance(d.get("read_at"), datetime):
        d["read_at"] = d["read_at"].isoformat()
    if isinstance(d.get("deleted_at"), datetime):
        d["deleted_at"] = d["deleted_at"].isoformat()
    return d


def create_notification(
    recipient_profile_id,
    notification_type,
    title,
    body=None,
    actor_profile_id=None,
    target_type=None,
    target_id=None,
    action_url=None,
    image_url=None,
    metadata=None,
):
    from services.notification_engine import create_notification as _engine_create
    return _engine_create(
        recipient_profile_id=recipient_profile_id,
        event_type=notification_type,
        title=title,
        body=body,
        actor_profile_id=actor_profile_id,
        entity_type=target_type,
        entity_id=target_id,
        action_url=action_url,
    )


def list_notifications(profile_id, tab="all", page=1, limit=30):
    if page < 1:
        page = 1
    if limit < 1:
        limit = 10
    limit = min(limit, 50)
    try:
        items, has_more = list_notifications_tab(profile_id, tab=tab, page=page, limit=limit)
        return [format_notification(item) for item in items], has_more
    except Exception:
        return [], False


def unread_count(profile_id):
    try:
        return engine_unread_count(profile_id)
    except Exception:
        return 0


def mark_read(profile_id, notification_id):
    try:
        return engine_mark_read(notification_id, profile_id)
    except Exception:
        return False


def mark_all_read(profile_id):
    try:
        return engine_mark_all_read(profile_id)
    except Exception:
        return False


def delete_notification(profile_id, notification_id):
    try:
        return engine_delete(notification_id, profile_id)
    except Exception:
        return False


def delete_selected(profile_id, notification_ids):
    if not notification_ids:
        return False
    try:
        return delete_selected_notifications(notification_ids, profile_id)
    except Exception:
        return False


def get_preferences(profile_id):
    try:
        return get_notification_preferences(profile_id)
    except Exception:
        return {"profile_id": profile_id, "muted_types": []}


def update_preferences(profile_id, prefs_data):
    try:
        return update_notification_preferences(profile_id, prefs_data)
    except Exception:
        return False


def mute_type(profile_id, notification_type, muted=True):
    try:
        return mute_notification_type(profile_id, notification_type, muted=muted)
    except Exception:
        return False
