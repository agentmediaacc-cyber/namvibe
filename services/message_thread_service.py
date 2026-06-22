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


def remove_group_member(thread_id, actor_profile_id, member_id):
    if not can_access_thread(actor_profile_id, thread_id):
        return {"ok": False, "error": "thread_not_found"}
    write_query(
        "DELETE FROM chain_thread_members WHERE thread_id = %s AND profile_id = %s",
        (thread_id, member_id),
    )
    return {"ok": True, "thread_id": thread_id, "member_id": member_id}


def leave_group(thread_id, profile_id):
    write_query(
        "DELETE FROM chain_thread_members WHERE thread_id = %s AND profile_id = %s",
        (thread_id, profile_id),
    )
    return {"ok": True, "thread_id": thread_id}
