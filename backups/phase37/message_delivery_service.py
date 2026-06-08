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
                 voice_duration_seconds=None):
    message_id = str(uuid4())

    member_rows = fast_query("""
        SELECT profile_id
        FROM chain_thread_members
        WHERE thread_id = %s
          AND profile_id != %s
    """, (thread_id, sender_profile_id), default=[])

    has_receiver = bool(member_rows)
    delivery_status = "delivered" if has_receiver else "sent"

    write_query("""
        INSERT INTO chain_messages (
            id,
            thread_id,
            sender_profile_id,
            body,
            message_type,
            media_url,
            delivery_status,
            delivered_at,
            is_seen,
            created_at
        )
        VALUES (
            %s,%s,%s,%s,%s,%s,%s,
            CASE WHEN %s THEN now() ELSE NULL END,
            FALSE,
            now()
        )
    """, (
        message_id,
        thread_id,
        sender_profile_id,
        body,
        message_type,
        media_url,
        delivery_status,
        has_receiver,
    ))

    for row in member_rows:
        try:
            write_query("""
                INSERT INTO chain_message_delivery_events (
                    id, message_id, thread_id, sender_profile_id,
                    recipient_profile_id, event_type, created_at
                )
                VALUES (%s,%s,%s,%s,%s,%s,now())
            """, (
                str(uuid4()),
                message_id,
                thread_id,
                sender_profile_id,
                row["profile_id"],
                delivery_status
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
        "created_at": now_iso()
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
