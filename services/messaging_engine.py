import json
import uuid
import os
from datetime import datetime, timezone

from services.media_storage_service import upload_media_file
from services.moderation_engine import contains_profanity, detect_spam_burst, is_blocked
from services.neon_service import fast_query, write_query
from services.request_cache import build_request_key, request_memoize
from services.redis_service import cache_delete, cache_get, cache_set, set_json, get_json, delete_key
from services.socketio_service import emit_to_profile, emit_to_thread


_TYPING_TTL_SECONDS = 10
_DUPLICATE_TTL_SECONDS = 300


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _typing_key(thread_id, profile_id):
    return f"typing:{thread_id}:{profile_id}"


def _message_dedupe_key(thread_id, sender_profile_id, client_message_id):
    return f"message_dedupe:{thread_id}:{sender_profile_id}:{client_message_id}"


def _delivery_ack_key(message_id, profile_id):
    return f"message_ack:{message_id}:{profile_id}"


def list_threads(profile_id, include_archived=False, folder='primary', limit=30, offset=0):
    """Lists message threads for a profile in a specific folder with pagination."""
    archived_filter = "AND tm.is_archived = FALSE" if not include_archived else ""
    folder_filter = ""
    params = [profile_id, profile_id, profile_id, profile_id]
    
    if folder:
        folder_filter = "AND t.folder_type = %s"
        params.append(folder)
    
    params.extend([limit, offset])

    sql = f"""
        SELECT t.*,
               tm.last_read_at,
               tm.is_pinned,
               tm.is_archived,
               tm.muted,
               peer.profile_json AS other_member,
               latest.body AS last_message,
               latest.created_at AS last_message_at,
               COALESCE(unread.unread_count, 0) AS unread_count
        FROM chain_message_threads t
        JOIN chain_thread_members tm ON t.id = tm.thread_id
        LEFT JOIN LATERAL (
            SELECT json_build_object('id', p.id, 'username', p.username, 'avatar_url', p.avatar_url, 'full_name', p.full_name) AS profile_json
            FROM chain_thread_members tm2
            JOIN chain_profiles p ON tm2.profile_id = p.id
            WHERE tm2.thread_id = t.id AND tm2.profile_id != %s
            LIMIT 1
        ) peer ON TRUE
        LEFT JOIN LATERAL (
            SELECT body, created_at
            FROM chain_messages m
            WHERE m.thread_id = t.id AND m.deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
        ) latest ON TRUE
        LEFT JOIN LATERAL (
            SELECT COUNT(*) AS unread_count
            FROM chain_messages m
            WHERE m.thread_id = t.id
              AND m.sender_profile_id != %s
              AND COALESCE(m.is_seen, FALSE) = FALSE
              AND m.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM chain_message_deletions md 
                  WHERE md.message_id = m.id AND md.profile_id = %s
              )
        ) unread ON TRUE
        WHERE tm.profile_id = %s AND t.deleted_at IS NULL {archived_filter} {folder_filter}
        ORDER BY tm.is_pinned DESC, latest.created_at DESC NULLS LAST, t.updated_at DESC NULLS LAST
        LIMIT %s OFFSET %s
    """
    threads = request_memoize(
        build_request_key("message_threads", profile_id, include_archived, folder, limit, offset),
        lambda: fast_query(sql, tuple(params), timeout_ms=2000, default=[]),
    )
    
    # Process threads to handle group vs direct labels
    for thread in threads:
        if thread.get('thread_type') == 'group':
            thread['display_name'] = thread.get('thread_name') or "Unnamed Group"
            thread['display_avatar'] = thread.get('thread_avatar_url')
        elif thread.get('other_member'):
            thread['display_name'] = thread['other_member'].get('full_name') or thread['other_member'].get('username')
            thread['display_avatar'] = thread['other_member'].get('avatar_url')
    return threads


def get_thread(thread_id, profile_id):
    """Gets a thread and its messages if the profile is a member."""
    check_sql = "SELECT * FROM chain_thread_members WHERE thread_id = %s AND profile_id = %s"
    memberships = fast_query(check_sql, (thread_id, profile_id), timeout_ms=1000, default=[])
    if not memberships:
        return None
    
    membership = memberships[0]

    thread_sql = "SELECT * FROM chain_message_threads WHERE id = %s AND deleted_at IS NULL"
    threads = fast_query(thread_sql, (thread_id,), timeout_ms=1000, default=[])
    if not threads:
        return None

    thread = threads[0]
    thread['membership'] = membership
    
    # Handle Display Metadata
    if thread.get('thread_type') == 'group':
        thread['display_name'] = thread.get('thread_name') or "Unnamed Group"
        thread['display_avatar'] = thread.get('thread_avatar_url')
    else:
        # Get peer for direct thread
        peer_sql = """
            SELECT p.id, p.username, p.full_name, p.avatar_url
            FROM chain_thread_members tm
            JOIN chain_profiles p ON tm.profile_id = p.id
            WHERE tm.thread_id = %s AND tm.profile_id != %s
            LIMIT 1
        """
        peers = fast_query(peer_sql, (thread_id, profile_id), timeout_ms=1000, default=[])
        if peers:
            thread['other_member'] = peers[0]
            thread['display_name'] = peers[0].get('full_name') or peers[0].get('username')
            thread['display_avatar'] = peers[0].get('avatar_url')

    msg_sql = """
        SELECT m.*, p.username AS sender_username, p.avatar_url AS sender_avatar,
               (SELECT json_agg(r) FROM (
                   SELECT profile_id, reaction_type FROM chain_message_reactions WHERE message_id = m.id
               ) r) AS reactions,
               (SELECT json_build_object('id', pm.id, 'body', pm.body, 'sender_id', pm.sender_profile_id)
                FROM chain_messages pm WHERE pm.id = m.parent_message_id) AS parent_message
        FROM chain_messages m
        JOIN chain_profiles p ON m.sender_profile_id = p.id
        WHERE m.thread_id = %s 
          AND m.deleted_at IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM chain_message_deletions md 
              WHERE md.message_id = m.id AND md.profile_id = %s
          )
        ORDER BY m.created_at ASC
        LIMIT 50
    """
    thread["messages"] = fast_query(msg_sql, (thread_id, profile_id), timeout_ms=1000, default=[])
    return thread


def get_or_create_direct_thread(profile_a, profile_b):
    """Finds an existing 1:1 thread or creates one."""
    if is_blocked(profile_a, profile_b):
        return None

    sql = """
        SELECT thread_id
        FROM chain_thread_members
        WHERE profile_id IN (%s, %s)
        GROUP BY thread_id
        HAVING COUNT(DISTINCT profile_id) = 2
        LIMIT 1
    """
    rows = fast_query(sql, (profile_a, profile_b), timeout_ms=1000, default=[])
    if rows:
        thread_id = rows[0]["thread_id"]
        t_rows = fast_query("SELECT thread_type FROM chain_message_threads WHERE id = %s", (thread_id,), timeout_ms=1000, default=[])
        if t_rows and t_rows[0]["thread_type"] == "direct":
            return thread_id

    # Create new thread
    thread_id = str(uuid.uuid4())
    try:
        # Check if they are mutual followers
        mutual_sql = """
            SELECT 1 FROM chain_follows f1
            JOIN chain_follows f2 ON f1.follower_profile_id = f2.following_profile_id 
            AND f1.following_profile_id = f2.follower_profile_id
            WHERE f1.follower_profile_id = %s AND f1.following_profile_id = %s
        """
        is_mutual = bool(fast_query(mutual_sql, (profile_a, profile_b)))
        
        folder_type = 'primary' if is_mutual else 'request'
        
        write_query(
            "INSERT INTO chain_message_threads (id, created_by_profile_id, thread_type, folder_type, created_at, updated_at) VALUES (%s, %s, 'direct', %s, now(), now())",
            (thread_id, profile_a, folder_type),
        )
        write_query(
            "INSERT INTO chain_thread_members (thread_id, profile_id) VALUES (%s, %s), (%s, %s)",
            (thread_id, profile_a, thread_id, profile_b),
        )
        return thread_id
    except Exception as error:
        print(f"[messaging_engine] Failed to create thread: {error}")
        return None


def can_message(profile_a, profile_b):
    return not is_blocked(profile_a, profile_b)


def send_message(thread_id, sender_profile_id, body=None, file=None, client_message_id=None, 
                 parent_message_id=None, is_forwarded=False, status_id=None,
                 sticker_id=None, gif_url=None, location=None, contact=None):
    """Sends a message to a thread and triggers realtime events."""
    client_message_id = client_message_id or f"optimistic-{uuid.uuid4()}"
    dedupe_key = _message_dedupe_key(thread_id, sender_profile_id, client_message_id)
    existing = cache_get(dedupe_key)
    if existing:
        return existing

    normalized_body = (body or "").strip()
    if normalized_body:
        if contains_profanity(normalized_body):
            return {"error": "Message failed moderation", "optimistic_id": client_message_id, "success": False}
        if detect_spam_burst(sender_profile_id, normalized_body):
            return {"error": "Message blocked for spam burst", "optimistic_id": client_message_id, "success": False}

    sql_members = "SELECT profile_id FROM chain_thread_members WHERE thread_id = %s AND profile_id != %s"
    members = fast_query(sql_members, (thread_id, sender_profile_id), timeout_ms=1000, default=[])
    for member in members:
        if is_blocked(sender_profile_id, member["profile_id"]):
            return {"error": "Messaging unavailable", "optimistic_id": client_message_id, "success": False}

    media_url = None
    media_type = None
    storage_bucket = None
    storage_path = None
    if file:
        # Validate audio for voice notes
        if getattr(file, "content_type", "").startswith("audio/"):
            # Max 10MB for voice notes
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(0)
            if size > 10 * 1024 * 1024:
                return {"error": "Voice note too large (max 10MB)", "optimistic_id": client_message_id, "success": False}
            
            allowed_audio = {"audio/webm", "audio/ogg", "audio/mpeg", "audio/mp3", "audio/m4a", "audio/x-m4a", "audio/wav", "audio/x-wav"}
            if file.content_type not in allowed_audio:
                return {"error": f"Unsupported audio format: {file.content_type}", "optimistic_id": client_message_id, "success": False}

        res, error = upload_media_file(file, bucket_name="chain-messages", profile_id=sender_profile_id, upload_type="message_media")
        if error:
            return {"error": error, "optimistic_id": client_message_id}
        if res:
            media_url = res["public_url"]
            media_type = getattr(file, "content_type", None)
            storage_bucket = res["bucket"]
            storage_path = res["file_path"]

    message_id = str(uuid.uuid4())
    sql = """
        INSERT INTO chain_messages (
            id, thread_id, sender_profile_id, body, media_url, media_type, storage_bucket, storage_path, 
            client_event_id, parent_message_id, is_forwarded, status_id, 
            sticker_id, gif_url, location_lat, location_lng, contact_data, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
        RETURNING id
    """
    lat = location.get('lat') if location else None
    lng = location.get('lng') if location else None
    contact_json = json.dumps(contact) if contact else None

    try:
        write_query(sql, (
            message_id, thread_id, sender_profile_id, normalized_body or None, 
            media_url, media_type, storage_bucket, storage_path, 
            client_message_id, parent_message_id, is_forwarded, status_id,
            sticker_id, gif_url, lat, lng, contact_json
        ))
        write_query("UPDATE chain_message_threads SET updated_at = now() WHERE id = %s", (thread_id,))
        
        # Get parent message info if exists
        parent_info = None
        if parent_message_id:
            parent_rows = fast_query("SELECT id, body, sender_profile_id FROM chain_messages WHERE id = %s", (parent_message_id,))
            if parent_rows:
                parent_info = parent_rows[0]

        payload = {
            "id": message_id,
            "thread_id": thread_id,
            "sender_profile_id": sender_profile_id,
            "body": normalized_body,
            "media_url": media_url,
            "media_type": media_type,
            "parent_message": parent_info,
            "is_forwarded": is_forwarded,
            "status_id": status_id,
            "sticker_id": sticker_id,
            "gif_url": gif_url,
            "location": location,
            "contact": contact,
            "created_at": _utcnow_iso(),
            "optimistic_id": client_message_id,
        }
        emit_to_thread(thread_id, "message:new", payload)

        for member in members:
            recipient_id = member["profile_id"]
            muted_check = fast_query("SELECT muted FROM chain_thread_members WHERE thread_id = %s AND profile_id = %s", (thread_id, recipient_id))
            if muted_check and muted_check[0]['muted']:
                continue

            from services.notification_engine import create_notification
            create_notification(
                recipient_profile_id=recipient_id,
                actor_profile_id=sender_profile_id,
                event_type="new_message",
                title="New Message",
                body=(normalized_body[:50] if normalized_body else "Sent a media message"),
                action_url=f"/messages/{thread_id}",
            )
            cache_delete(f"unread_count_{recipient_id}")
            emit_to_profile(recipient_id, "message:notify", {"thread_id": thread_id, "optimistic_id": client_message_id})

        result = {
            "id": message_id,
            "message_id": message_id,
            "server_message_id": message_id,
            "client_event_id": client_message_id,
            "optimistic_id": client_message_id,
            "duplicate": False,
            "success": True,
            "payload": payload
        }
        cache_set(dedupe_key, result, ttl=_DUPLICATE_TTL_SECONDS)
        return result
    except Exception as error:
        if "duplicate key value" in str(error) or "client_event" in str(error):
            existing = fast_query(
                "SELECT id FROM chain_messages WHERE thread_id = %s AND sender_profile_id = %s AND client_event_id = %s LIMIT 1",
                (thread_id, sender_profile_id, client_message_id),
                timeout_ms=1000,
                default=[],
            )
            if existing:
                return {
                    "id": existing[0]["id"],
                    "message_id": existing[0]["id"],
                    "server_message_id": existing[0]["id"],
                    "client_event_id": client_message_id,
                    "optimistic_id": client_message_id,
                    "duplicate": True,
                    "success": True,
                }
        print(f"[messaging_engine] Failed to send message: {error}")
        return {"error": "Failed to send message", "optimistic_id": client_message_id, "success": False}


def send_message_realtime(thread_id, sender_profile_id, body=None, file=None, client_event_id=None):
    return send_message(thread_id, sender_profile_id, body=body, file=file, client_message_id=client_event_id)


def mark_thread_seen(thread_id, profile_id):
    """Marks a thread as seen and emits realtime update (Blue Ticks)."""
    write_query("UPDATE chain_thread_members SET last_read_at = now() WHERE thread_id = %s AND profile_id = %s", (thread_id, profile_id))
    write_query(
        "UPDATE chain_messages SET is_seen = TRUE, seen_at = now(), read_at = now(), delivery_status = 'seen' WHERE thread_id = %s AND sender_profile_id != %s AND is_seen = FALSE",
        (thread_id, profile_id),
    )
    emit_to_thread(thread_id, "message:seen", {"profile_id": profile_id, "thread_id": thread_id, "read_at": _utcnow_iso()})
    return True


def acknowledge_delivery(message_id, profile_id):
    payload = {"message_id": message_id, "profile_id": profile_id, "acked_at": _utcnow_iso()}
    set_json(_delivery_ack_key(message_id, profile_id), payload, ttl=300)
    write_query("UPDATE chain_messages SET delivery_status = 'delivered' WHERE id = %s AND delivery_status = 'sent'", (message_id,))
    emit_to_profile(profile_id, "message:delivered", {"message_id": message_id, "delivered_at": payload['acked_at']})
    return payload


def delivery_acknowledged(message_id, profile_id):
    return get_json(_delivery_ack_key(message_id, profile_id))


def set_typing(thread_id, profile_id, is_typing=True):
    """Sets typing status with expiry and emits update."""
    key = _typing_key(thread_id, profile_id)
    if is_typing:
        cache_set(key, {"profile_id": profile_id, "thread_id": thread_id, "expires_at": _utcnow_iso()}, ttl=_TYPING_TTL_SECONDS)
    else:
        cache_delete(key)
    emit_to_thread(thread_id, "typing:update", {"profile_id": profile_id, "typing": bool(is_typing)})
    return True


def clear_expired_typing_statuses(thread_id, profile_ids):
    cleared = []
    for profile_id in profile_ids or []:
        key = _typing_key(thread_id, profile_id)
        if cache_get(key) is None:
            cleared.append(profile_id)
    return cleared


def recover_thread_messages(thread_id, profile_id, since_iso=None, limit=50):
    if not get_thread(thread_id, profile_id):
        return []
    params = [thread_id]
    since_clause = ""
    if since_iso:
        since_clause = "AND m.created_at >= %s"
        params.append(since_iso)
    params.append(int(limit))
    sql = f"""
        SELECT m.*, p.username AS sender_username, p.avatar_url AS sender_avatar
        FROM chain_messages m
        JOIN chain_profiles p ON m.sender_profile_id = p.id
        WHERE m.thread_id = %s
          AND m.deleted_at IS NULL
          {since_clause}
        ORDER BY m.created_at DESC
        LIMIT %s
    """
    rows = fast_query(sql, tuple(params), timeout_ms=1000, default=[])
    return list(reversed(rows))


def reconnect_sync(thread_id, profile_id, last_seen_message_id=None, last_seen_at=None, limit=100):
    if not get_thread(thread_id, profile_id):
        return []
    limit = max(min(int(limit or 100), 100), 1)
    params = [thread_id]
    where_clause = ""
    if last_seen_message_id:
        where_clause = """
          AND m.created_at > COALESCE(
            (SELECT created_at FROM chain_messages WHERE id = %s LIMIT 1),
            to_timestamp(0)
          )
        """
        params.append(last_seen_message_id)
    elif last_seen_at:
        where_clause = "AND m.created_at >= %s"
        params.append(last_seen_at)
    params.append(limit)
    sql = f"""
        SELECT m.*, p.username AS sender_username, p.avatar_url AS sender_avatar
        FROM chain_messages m
        JOIN chain_profiles p ON m.sender_profile_id = p.id
        WHERE m.thread_id = %s
          AND m.deleted_at IS NULL
          {where_clause}
        ORDER BY m.created_at ASC
        LIMIT %s
    """
    return fast_query(sql, tuple(params), timeout_ms=1000, default=[])


def clear_delivery_ack(message_id, profile_id):
    delete_key(_delivery_ack_key(message_id, profile_id))

def add_reaction(message_id, profile_id, reaction_type):
    sql = "INSERT INTO chain_message_reactions (message_id, profile_id, reaction_type) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING"
    write_query(sql, (message_id, profile_id, reaction_type))
    t_sql = "SELECT thread_id FROM chain_messages WHERE id = %s"
    rows = fast_query(t_sql, (message_id,))
    if rows:
        emit_to_thread(rows[0]['thread_id'], "message:reaction", {
            "message_id": message_id,
            "profile_id": profile_id,
            "reaction_type": reaction_type,
            "action": "added"
        })
    return True

def remove_reaction(message_id, profile_id, reaction_type):
    sql = "DELETE FROM chain_message_reactions WHERE message_id = %s AND profile_id = %s AND reaction_type = %s"
    write_query(sql, (message_id, profile_id, reaction_type))
    t_sql = "SELECT thread_id FROM chain_messages WHERE id = %s"
    rows = fast_query(t_sql, (message_id,))
    if rows:
        emit_to_thread(rows[0]['thread_id'], "message:reaction", {
            "message_id": message_id,
            "profile_id": profile_id,
            "reaction_type": reaction_type,
            "action": "removed"
        })
    return True

def delete_message(message_id, profile_id, for_everyone=False):
    msg_sql = "SELECT sender_profile_id, thread_id FROM chain_messages WHERE id = %s"
    rows = fast_query(msg_sql, (message_id,))
    if not rows:
        return False
    
    msg = rows[0]
    if for_everyone:
        if msg['sender_profile_id'] != profile_id:
            return False
        write_query("UPDATE chain_messages SET deleted_at = now() WHERE id = %s", (message_id,))
        emit_to_thread(msg['thread_id'], "message:delete", {"message_id": message_id, "for_everyone": True})
    else:
        write_query("INSERT INTO chain_message_deletions (message_id, profile_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (message_id, profile_id))
        emit_to_profile(profile_id, "message:delete", {"message_id": message_id, "for_everyone": False})
    
    return True

def pin_thread(thread_id, profile_id, pinned=True):
    write_query("UPDATE chain_thread_members SET is_pinned = %s WHERE thread_id = %s AND profile_id = %s", (pinned, thread_id, profile_id))
    cache_delete(f"message_threads_{profile_id}_False")
    cache_delete(f"message_threads_{profile_id}_True")
    return True

def archive_thread(thread_id, profile_id, archived=True):
    write_query("UPDATE chain_thread_members SET is_archived = %s WHERE thread_id = %s AND profile_id = %s", (archived, thread_id, profile_id))
    cache_delete(f"message_threads_{profile_id}_False")
    cache_delete(f"message_threads_{profile_id}_True")
    return True

def mute_thread(thread_id, profile_id, muted=True):
    write_query("UPDATE chain_thread_members SET muted = %s WHERE thread_id = %s AND profile_id = %s", (muted, thread_id, profile_id))
    return True

def move_thread(thread_id, folder_type):
    """Moves a thread to a specific folder (primary, request, spam)."""
    sql = "UPDATE chain_message_threads SET folder_type = %s WHERE id = %s"
    return write_query(sql, (folder_type, thread_id))

def search_messages(profile_id, query):
    if not query or len(query) < 2:
        return []
    sql = """
        SELECT m.*, t.thread_type, t.thread_name
        FROM chain_messages m
        JOIN chain_thread_members tm ON m.thread_id = tm.thread_id
        JOIN chain_message_threads t ON m.thread_id = t.id
        WHERE tm.profile_id = %s 
          AND m.body ILIKE %s
          AND m.deleted_at IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM chain_message_deletions md 
              WHERE md.message_id = m.id AND md.profile_id = %s
          )
        ORDER BY m.created_at DESC
        LIMIT 50
    """
    return fast_query(sql, (profile_id, f"%{query}%", profile_id))

def get_stickers():
    return fast_query("SELECT * FROM chain_stickers", default=[])
