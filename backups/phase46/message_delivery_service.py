from uuid import uuid4
from datetime import datetime
from services.neon_service import fast_query, write_query

def now_iso():
    return datetime.utcnow().isoformat()

def ensure_message_tables():
    sql = """
    CREATE TABLE IF NOT EXISTS chain_message_delivery_events (
        id UUID PRIMARY KEY,
        message_id UUID,
        thread_id UUID,
        sender_profile_id UUID,
        recipient_profile_id UUID,
        event_type TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_chain_messages_thread_created
    ON chain_messages(thread_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_chain_messages_seen
    ON chain_messages(thread_id, sender_profile_id, is_seen);
    CREATE INDEX IF NOT EXISTS idx_chain_thread_members_profile
    ON chain_thread_members(profile_id, thread_id);
    """
    try:
        write_query(sql, ())
    except Exception as e:
        print("[message_delivery] ensure tables skipped:", e)

def get_thread_messages(thread_id, viewer_profile_id):
    rows = fast_query("""
        SELECT
            m.id,
            m.thread_id,
            m.sender_profile_id,
            m.body,
            m.message_type,
            m.media_url,
            m.delivery_status,
            m.is_seen,
            m.seen_at,
            m.read_at,
            m.delivered_at,
            m.created_at,
            m.deleted_at,
            m.deleted_for_everyone,
            m.reply_to_message_id,
            m.voice_duration_seconds,
            p.username AS sender_username,
            p.full_name AS sender_name,
            p.avatar_url AS sender_avatar
        FROM chain_messages m
        LEFT JOIN chain_profiles p ON p.id = m.sender_profile_id
        WHERE m.thread_id = %s
          AND m.deleted_at IS NULL
        ORDER BY m.created_at ASC
        LIMIT 100
    """, (thread_id,), default=[])

    try:
        write_query("""
            UPDATE chain_thread_members
            SET last_read_at = now()
            WHERE thread_id = %s AND profile_id = %s
        """, (thread_id, viewer_profile_id))

        write_query("""
            UPDATE chain_messages
            SET
                is_seen = TRUE,
                seen_at = COALESCE(seen_at, now()),
                read_at = COALESCE(read_at, now()),
                delivery_status = 'seen'
            WHERE thread_id = %s
              AND sender_profile_id != %s
              AND COALESCE(is_seen, FALSE) = FALSE
        """, (thread_id, viewer_profile_id))
    except Exception as e:
        print("[message_delivery] seen update skipped:", e)

    return rows or []

def send_message(thread_id, sender_profile_id, body, message_type="text",
                 media_url=None, file_url=None, audio_url=None,
                 voice_duration_seconds=None, reply_to_message_id=None):
    message_id = str(uuid4())

    member_rows = fast_query("""
        SELECT profile_id
        FROM chain_thread_members
        WHERE thread_id = %s
          AND profile_id != %s
    """, (thread_id, sender_profile_id), default=[])

    has_receiver = bool(member_rows)
    delivery_status = "delivered" if has_receiver else "sent"

    reply_col = ", reply_to_message_id" if reply_to_message_id else ""
    reply_val = ", %s" if reply_to_message_id else ""
    params = [
        message_id, thread_id, sender_profile_id, body,
        message_type, media_url, delivery_status, has_receiver
    ]
    if reply_to_message_id:
        params.append(reply_to_message_id)

    write_query(f"""
        INSERT INTO chain_messages (
            id, thread_id, sender_profile_id, body,
            message_type, media_url, delivery_status,
            delivered_at, is_seen, created_at{reply_col}
        )
        VALUES (
            %s,%s,%s,%s,%s,%s,%s,
            CASE WHEN %s THEN now() ELSE NULL END,
            FALSE, now(){reply_val}
        )
    """, tuple(params))

    if voice_duration_seconds is not None:
        try:
            write_query(
                "UPDATE chain_messages SET voice_duration_seconds = %s WHERE id = %s",
                (voice_duration_seconds, message_id)
            )
        except Exception:
            pass

    for row in member_rows:
        try:
            write_query("""
                INSERT INTO chain_message_delivery_events (
                    id, message_id, thread_id, sender_profile_id,
                    recipient_profile_id, event_type, created_at
                )
                VALUES (%s,%s,%s,%s,%s,%s,now())
            """, (
                str(uuid4()), message_id, thread_id,
                sender_profile_id, row["profile_id"], delivery_status
            ))
        except Exception:
            pass

    return {
        "id": message_id,
        "thread_id": thread_id,
        "sender_profile_id": sender_profile_id,
        "body": body,
        "message_type": message_type,
        "delivery_status": delivery_status,
        "is_delivered": has_receiver,
        "is_seen": False,
        "created_at": now_iso(),
        "reply_to_message_id": reply_to_message_id
    }

def unread_count(profile_id):
    rows = fast_query("""
        SELECT COUNT(*) AS total
        FROM chain_messages m
        JOIN chain_thread_members tm ON tm.thread_id = m.thread_id
        WHERE tm.profile_id = %s
          AND m.sender_profile_id != %s
          AND COALESCE(m.is_seen, FALSE) = FALSE
          AND m.deleted_at IS NULL
    """, (profile_id, profile_id), default=[{"total": 0}])
    return int(rows[0]["total"]) if rows else 0

def get_unread_counts_per_thread(profile_id):
    rows = fast_query("""
        SELECT m.thread_id, COUNT(*) AS cnt
        FROM chain_messages m
        JOIN chain_thread_members tm ON tm.thread_id = m.thread_id
        WHERE tm.profile_id = %s
          AND m.sender_profile_id != %s
          AND COALESCE(m.is_seen, FALSE) = FALSE
          AND m.deleted_at IS NULL
        GROUP BY m.thread_id
    """, (profile_id, profile_id), default=[])
    return {r["thread_id"]: int(r["cnt"]) for r in rows} if rows else {}

def mark_delivered_for_online_user(profile_id):
    write_query("""
        UPDATE chain_messages m
        SET
            delivered_at = COALESCE(delivered_at, now()),
            delivery_status = CASE
                WHEN COALESCE(is_seen, FALSE) = TRUE THEN 'seen'
                ELSE 'delivered'
            END
        FROM chain_thread_members tm
        WHERE tm.thread_id = m.thread_id
          AND tm.profile_id = %s
          AND m.sender_profile_id != %s
          AND m.delivery_status = 'sent'
    """, (profile_id, profile_id))
    return True

def mark_thread_seen(thread_id, profile_id):
    try:
        write_query("""
            UPDATE chain_messages
            SET is_seen = TRUE,
                seen_at = COALESCE(seen_at, now()),
                read_at = COALESCE(read_at, now()),
                delivery_status = 'seen'
            WHERE thread_id = %s
              AND sender_profile_id != %s
              AND COALESCE(is_seen, FALSE) = FALSE
        """, (thread_id, profile_id))
        write_query("""
            UPDATE chain_thread_members
            SET last_read_at = now()
            WHERE thread_id = %s AND profile_id = %s
        """, (thread_id, profile_id))
        return True
    except Exception:
        return False

def react_to_message(message_id, profile_id, reaction):
    try:
        write_query("""
            INSERT INTO chain_message_reactions (id, message_id, profile_id, reaction_type, created_at)
            VALUES (%s, %s, %s, %s, now())
            ON CONFLICT (message_id, profile_id)
            DO UPDATE SET reaction_type = %s, created_at = now()
        """, (str(uuid4()), message_id, profile_id, reaction, reaction))
        return True
    except Exception:
        return False

def remove_reaction(message_id, profile_id):
    try:
        write_query(
            "DELETE FROM chain_message_reactions WHERE message_id = %s AND profile_id = %s",
            (message_id, profile_id)
        )
        return True
    except Exception:
        return False

def get_reactions(message_id):
    rows = fast_query("""
        SELECT r.reaction_type AS reaction, r.profile_id, r.created_at, p.username
        FROM chain_message_reactions r
        LEFT JOIN chain_profiles p ON p.id = r.profile_id
        WHERE r.message_id = %s
        ORDER BY r.created_at ASC
    """, (message_id,), default=[])
    return rows or []

def edit_message(message_id, profile_id, new_body):
    old_rows = fast_query(
        "SELECT body FROM chain_messages WHERE id = %s AND sender_profile_id = %s AND deleted_at IS NULL",
        (message_id, profile_id), default=[]
    )
    if not old_rows:
        return False
    old_body = old_rows[0].get("body", "")
    try:
        write_query(
            "UPDATE chain_messages SET body = %s WHERE id = %s AND sender_profile_id = %s",
            (new_body, message_id, profile_id)
        )
        write_query("""
            INSERT INTO chain_message_edits (id, message_id, editor_profile_id, old_body, new_body, created_at)
            VALUES (%s, %s, %s, %s, %s, now())
        """, (str(uuid4()), message_id, profile_id, old_body, new_body))
        return True
    except Exception:
        return False

def delete_message_for_everyone(message_id, profile_id):
    try:
        write_query("""
            UPDATE chain_messages
            SET body = 'This message was deleted.',
                deleted_at = now(),
                deleted_for_everyone = TRUE
            WHERE id = %s AND sender_profile_id = %s
        """, (message_id, profile_id))
        return True
    except Exception:
        return False

def update_presence(profile_id, status="online", device_type=None, socket_id=None):
    try:
        write_query("""
            INSERT INTO chain_online_presence (id, profile_id, status, device_type, socket_id, updated_at)
            VALUES (%s, %s, %s, %s, %s, now())
            ON CONFLICT (profile_id)
            DO UPDATE SET
                status = %s,
                device_type = COALESCE(%s, chain_online_presence.device_type),
                socket_id = COALESCE(%s, chain_online_presence.socket_id),
                updated_at = now()
        """, (str(uuid4()), profile_id, status, device_type, socket_id,
              status, device_type, socket_id))
        return True
    except Exception:
        return False

def get_presence(profile_id):
    rows = fast_query("""
        SELECT profile_id, status, last_seen, device_type, updated_at
        FROM chain_online_presence
        WHERE profile_id = %s
    """, (profile_id,), default=[])
    if rows:
        r = rows[0]
        return {
            "profile_id": r["profile_id"],
            "status": r["status"],
            "last_seen": r.get("last_seen") or r.get("updated_at"),
            "device_type": r.get("device_type"),
            "online": r.get("status") in ("online", "busy", "in_call")
        }
    return {"profile_id": profile_id, "status": "offline", "last_seen": None, "online": False}

def set_offline(profile_id):
    try:
        write_query(
            "UPDATE chain_online_presence SET status = 'offline', last_seen = now(), updated_at = now() WHERE profile_id = %s",
            (profile_id,)
        )
        return True
    except Exception:
        return False

def get_typing_users(thread_id, exclude_profile_id=None):
    rows = fast_query("""
        SELECT profile_id, username, full_name
        FROM chain_thread_members tm
        JOIN chain_profiles p ON p.id = tm.profile_id
        WHERE tm.thread_id = %s
    """, (thread_id,), default=[])
    return [r for r in rows if r["profile_id"] != exclude_profile_id] if exclude_profile_id else rows
