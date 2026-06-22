from uuid import uuid4

from services.neon_service import fast_query, write_query
from services.thread_security_service import can_access_thread


MESSAGE_SELECT = """
    SELECT
        m.id, m.thread_id, m.sender_profile_id,
        CASE WHEN m.deleted_for_everyone_at IS NOT NULL OR m.deleted_at IS NOT NULL THEN NULL ELSE m.body END AS body,
        CASE WHEN m.deleted_for_everyone_at IS NOT NULL OR m.deleted_at IS NOT NULL THEN TRUE ELSE FALSE END AS deleted_for_everyone,
        m.message_type, m.media_url, m.media_type, m.mime_type,
        COALESCE(m.status, m.delivery_status, 'sent') AS status,
        m.delivered_at, m.seen_at, m.created_at,
        m.client_temp_id, m.client_event_id,
        m.reply_to_message_id, m.forwarded_from_message_id,
        m.duration_seconds, m.file_size, m.voice_duration_seconds, m.size_bytes,
        p.username AS sender_username,
        p.display_name AS sender_display_name
    FROM chain_messages m
    LEFT JOIN chain_profiles p ON p.id = m.sender_profile_id
"""


def latest_messages(thread_id, profile_id, limit=50, since=None):
    if not can_access_thread(profile_id, thread_id):
        return {"ok": False, "error": "thread_not_found", "messages": []}
    params = [thread_id]
    where = "WHERE m.thread_id = %s"
    if since:
        where += " AND m.created_at > %s"
        params.append(since)
    params.append(int(limit))
    rows = fast_query(
        MESSAGE_SELECT + f"""
        {where}
        ORDER BY m.created_at ASC, m.id ASC
        LIMIT %s
        """,
        tuple(params),
        default=[],
    )
    return {"ok": True, "messages": rows}


def older_messages(thread_id, profile_id, limit=50, before=None):
    if not can_access_thread(profile_id, thread_id):
        return {"ok": False, "error": "thread_not_found", "messages": []}
    params = [thread_id]
    where = "WHERE m.thread_id = %s"
    if before:
        where += " AND m.created_at < %s"
        params.append(before)
    params.append(int(limit))
    rows = fast_query(
        MESSAGE_SELECT + f"""
        {where}
        ORDER BY m.created_at DESC, m.id DESC
        LIMIT %s
        """,
        tuple(params),
        default=[],
    )
    rows.reverse()
    return {"ok": True, "messages": rows}


def unread_count(profile_id):
    rows = fast_query(
        """
        SELECT COUNT(*) AS total
        FROM chain_messages m
        JOIN chain_thread_members tm ON tm.thread_id = m.thread_id
        WHERE tm.profile_id = %s
          AND m.sender_profile_id != %s
          AND COALESCE(m.is_seen, FALSE) = FALSE
          AND m.deleted_at IS NULL
          AND m.deleted_for_everyone_at IS NULL
        """,
        (profile_id, profile_id),
        default=[{"total": 0}],
    )
    return int((rows[0] or {}).get("total") or 0)


def create_group(owner_profile_id, title, member_ids=None):
    thread_id = str(uuid4())
    title = (title or "Group").strip()[:120]
    write_query(
        "INSERT INTO chain_message_threads (id, thread_type, title, created_by_profile_id, created_at, updated_at) VALUES (%s, 'group', %s, %s, now(), now())",
        (thread_id, title, owner_profile_id),
    )
    all_members = {str(owner_profile_id), *(str(mid) for mid in (member_ids or []) if mid)}
    for member_id in all_members:
        write_query(
            "INSERT INTO chain_thread_members (thread_id, profile_id, role, created_at) VALUES (%s, %s, %s, now()) ON CONFLICT DO NOTHING",
            (thread_id, member_id, "admin" if member_id == str(owner_profile_id) else "member"),
        )
    return {"ok": True, "thread_id": thread_id, "title": title}


def add_group_member(thread_id, actor_profile_id, member_id):
    if not can_access_thread(actor_profile_id, thread_id):
        return {"ok": False, "error": "thread_not_found"}
    write_query(
        "INSERT INTO chain_thread_members (thread_id, profile_id, role, created_at) VALUES (%s, %s, 'member', now()) ON CONFLICT DO NOTHING",
        (thread_id, member_id),
    )
    return {"ok": True, "thread_id": thread_id, "member_id": member_id}


def _is_admin_or_owner(thread_id, profile_id):
    rows = fast_query(
        "SELECT role FROM chain_thread_members WHERE thread_id = %s AND profile_id = %s",
        (thread_id, profile_id),
        default=[],
    )
    return bool(rows and rows[0].get("role") in ("admin", "owner"))


def _notify_group_members(thread_id, event_type, actor_id, title, body, entity_id=None):
    from services.notification_engine import create_notification
    members = fast_query(
        "SELECT profile_id FROM chain_thread_members WHERE thread_id = %s",
        (thread_id,),
        default=[],
    )
    for m in members:
        pid = m["profile_id"]
        if pid == actor_id:
            continue
        create_notification(
            recipient_profile_id=pid,
            event_type=event_type,
            title=title,
            body=body,
            actor_profile_id=actor_id,
            entity_type="thread",
            entity_id=entity_id or thread_id,
        )


def remove_group_member(thread_id, actor_profile_id, member_id):
    if not can_access_thread(actor_profile_id, thread_id):
        return {"ok": False, "error": "thread_not_found"}
    if not _is_admin_or_owner(thread_id, actor_profile_id):
        return {"ok": False, "error": "not_admin"}
    write_query(
        "DELETE FROM chain_thread_members WHERE thread_id = %s AND profile_id = %s",
        (thread_id, member_id),
    )
    _notify_group_members(thread_id, "member_removed", actor_profile_id,
                          "Member removed", f"A member was removed from the group",
                          entity_id=thread_id)
    return {"ok": True, "thread_id": thread_id, "member_id": member_id}


def leave_group(thread_id, profile_id):
    write_query(
        "DELETE FROM chain_thread_members WHERE thread_id = %s AND profile_id = %s",
        (thread_id, profile_id),
    )
    return {"ok": True, "thread_id": thread_id}


def rename_group(thread_id, actor_profile_id, new_title):
    if not can_access_thread(actor_profile_id, thread_id):
        return {"ok": False, "error": "thread_not_found"}
    if not _is_admin_or_owner(thread_id, actor_profile_id):
        return {"ok": False, "error": "not_admin"}
    new_title = (new_title or "").strip()[:120]
    if not new_title:
        return {"ok": False, "error": "title_required"}
    write_query(
        "UPDATE chain_message_threads SET title = %s, updated_at = now() WHERE id = %s",
        (new_title, thread_id),
    )
    _notify_group_members(thread_id, "group_update", actor_profile_id,
                          "Group renamed", f"Group renamed to \"{new_title}\"",
                          entity_id=thread_id)
    return {"ok": True, "thread_id": thread_id, "title": new_title}


def update_group_avatar(thread_id, actor_profile_id, avatar_url):
    if not can_access_thread(actor_profile_id, thread_id):
        return {"ok": False, "error": "thread_not_found"}
    if not _is_admin_or_owner(thread_id, actor_profile_id):
        return {"ok": False, "error": "not_admin"}
    write_query(
        "UPDATE chain_message_threads SET avatar_url = %s, updated_at = now() WHERE id = %s",
        (avatar_url, thread_id),
    )
    _notify_group_members(thread_id, "group_update", actor_profile_id,
                          "Group avatar changed", "Group avatar was updated",
                          entity_id=thread_id)
    return {"ok": True, "thread_id": thread_id, "avatar_url": avatar_url}


def promote_admin(thread_id, actor_profile_id, member_id):
    if not can_access_thread(actor_profile_id, thread_id):
        return {"ok": False, "error": "thread_not_found"}
    if not _is_admin_or_owner(thread_id, actor_profile_id):
        return {"ok": False, "error": "not_admin"}
    write_query(
        "UPDATE chain_thread_members SET role = 'admin' WHERE thread_id = %s AND profile_id = %s",
        (thread_id, member_id),
    )
    _notify_group_members(thread_id, "admin_promoted", actor_profile_id,
                          "Admin promoted", "A member was promoted to admin",
                          entity_id=thread_id)
    return {"ok": True, "thread_id": thread_id, "member_id": member_id, "role": "admin"}


def demote_admin(thread_id, actor_profile_id, member_id):
    if not can_access_thread(actor_profile_id, thread_id):
        return {"ok": False, "error": "thread_not_found"}
    if not _is_admin_or_owner(thread_id, actor_profile_id):
        return {"ok": False, "error": "not_admin"}
    write_query(
        "UPDATE chain_thread_members SET role = 'member' WHERE thread_id = %s AND profile_id = %s",
        (thread_id, member_id),
    )
    _notify_group_members(thread_id, "admin_demoted", actor_profile_id,
                          "Admin demoted", "An admin was demoted to member",
                          entity_id=thread_id)
    return {"ok": True, "thread_id": thread_id, "member_id": member_id, "role": "member"}
