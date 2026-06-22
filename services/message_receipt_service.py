from datetime import datetime, timezone

from services.neon_service import fast_query, write_query
from services.thread_security_service import can_access_thread


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _emit(event, payload, thread_id=None):
    try:
        from services.socketio_service import emit_to_thread
        if thread_id:
            emit_to_thread(thread_id, event, payload)
    except Exception:
        pass


def _message_row(message_id):
    rows = fast_query(
        "SELECT id, thread_id, sender_profile_id FROM chain_messages WHERE id = %s LIMIT 1",
        (message_id,),
        default=[],
    )
    return rows[0] if rows else None


def upsert_receipt(message_id, user_id, status):
    message = _message_row(message_id)
    if not message or not can_access_thread(user_id, message["thread_id"]):
        return {"ok": False, "error": "message_not_found"}

    delivered_expr = "COALESCE(chain_message_receipts.delivered_at, now())" if status in {"delivered", "seen"} else "chain_message_receipts.delivered_at"
    seen_expr = "COALESCE(chain_message_receipts.seen_at, now())" if status == "seen" else "chain_message_receipts.seen_at"
    write_query(
        f"""
        INSERT INTO chain_message_receipts (message_id, user_id, status, delivered_at, seen_at, updated_at)
        VALUES (%s, %s, %s,
                CASE WHEN %s IN ('delivered','seen') THEN now() ELSE NULL END,
                CASE WHEN %s = 'seen' THEN now() ELSE NULL END,
                now())
        ON CONFLICT (message_id, user_id)
        DO UPDATE SET
            status = CASE
                WHEN chain_message_receipts.status = 'seen' THEN 'seen'
                WHEN EXCLUDED.status = 'seen' THEN 'seen'
                WHEN EXCLUDED.status = 'delivered' THEN 'delivered'
                ELSE chain_message_receipts.status
            END,
            delivered_at = {delivered_expr},
            seen_at = {seen_expr},
            updated_at = now()
        """,
        (message_id, user_id, status, status, status),
    )

    if status in {"delivered", "seen"}:
        write_query(
            """
            UPDATE chain_messages
            SET delivered_at = COALESCE(delivered_at, now()),
                status = CASE WHEN COALESCE(status, delivery_status) = 'seen' THEN 'seen' ELSE 'delivered' END,
                delivery_status = CASE WHEN COALESCE(delivery_status, status) = 'seen' THEN 'seen' ELSE 'delivered' END
            WHERE id = %s AND sender_profile_id != %s
            """,
            (message_id, user_id),
        )
    if status == "seen":
        write_query(
            """
            UPDATE chain_messages
            SET seen_at = COALESCE(seen_at, now()),
                read_at = COALESCE(read_at, now()),
                is_seen = TRUE,
                status = 'seen',
                delivery_status = 'seen'
            WHERE id = %s AND sender_profile_id != %s
            """,
            (message_id, user_id),
        )
        write_query(
            "UPDATE chain_thread_members SET last_read_at = now() WHERE thread_id = %s AND profile_id = %s",
            (message["thread_id"], user_id),
        )

    payload = {
        "message_id": message_id,
        "profile_id": user_id,
        "thread_id": message["thread_id"],
        "status": status,
        f"{status}_at": _now_iso(),
    }
    _emit(f"message:{status}", payload, thread_id=message["thread_id"])
    _emit("unread:update", {"profile_id": user_id, "thread_id": message["thread_id"]}, thread_id=message["thread_id"])
    return {"ok": True, **payload}


def mark_message_delivered(message_id, user_id):
    return upsert_receipt(message_id, user_id, "delivered")


def mark_message_seen(message_id, user_id):
    return upsert_receipt(message_id, user_id, "seen")


def mark_thread_seen(thread_id, user_id):
    if not can_access_thread(user_id, thread_id):
        return {"ok": False, "error": "thread_not_found"}
    rows = fast_query(
        """
        SELECT id
        FROM chain_messages
        WHERE thread_id = %s
          AND sender_profile_id != %s
          AND COALESCE(is_seen, FALSE) = FALSE
          AND deleted_at IS NULL
        ORDER BY created_at ASC, id ASC
        """,
        (thread_id, user_id),
        default=[],
    )
    for row in rows:
        upsert_receipt(row["id"], user_id, "seen")
    return {"ok": True, "thread_id": thread_id, "seen_count": len(rows)}
