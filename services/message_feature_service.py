import os
import re
import uuid
from datetime import datetime, timezone
import json

from services.neon_service import fast_query, get_pool_status, write_query
from services.socketio_service import emit_to_profile, emit_to_thread

_THREADS = {}
_MESSAGES = {}
_READS = {}
_REACTIONS = {}
_STARS = set()
_VOICE_NOTES = {}
_ATTACHMENTS = {}
_PINS = {}
_DRAFTS = {}
_SCHEDULED = {}
_WALLPAPERS = {}
_SHARED_ITEMS = {}
_AUTODOWNLOAD = {}
_ENCRYPTION = {}
_VOICE_DRAFTS = {}
_VOICE_PLAYBACK = {}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _uuid(value=None):
    if value:
        try:
            return str(uuid.UUID(str(value)))
        except (TypeError, ValueError):
            pass
    return str(uuid.uuid4())


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _safe_write(sql, params=(), timeout_ms=900):
    if not _db_available():
        raise RuntimeError("db_unavailable")
    return write_query(sql, params, timeout_ms=timeout_ms)


def _safe_query(sql, params=(), timeout_ms=700, default=None):
    if not _db_available():
        return default if default is not None else []
    return fast_query(sql, params, timeout_ms=timeout_ms, default=default if default is not None else [])


def create_direct_thread(profile_a, profile_b):
    profile_a = _uuid(profile_a)
    profile_b = _uuid(profile_b)
    if profile_a == profile_b:
        return {"ok": False, "error": "same_profile"}
    existing = _safe_query(
        """
        SELECT tm1.thread_id
        FROM chain_thread_members tm1
        JOIN chain_thread_members tm2 ON tm1.thread_id = tm2.thread_id
        JOIN chain_message_threads t ON t.id = tm1.thread_id
        WHERE tm1.profile_id = %s AND tm2.profile_id = %s AND t.thread_type = 'direct'
        LIMIT 1
        """,
        (profile_a, profile_b),
        default=[],
    )
    if existing:
        return {"ok": True, "thread_id": str(existing[0]["thread_id"]), "existing": True}

    thread_id = str(uuid.uuid4())
    try:
        _safe_write(
            "INSERT INTO chain_message_threads (id, created_by_profile_id, thread_type, folder_type, created_at, updated_at) VALUES (%s, %s, 'direct', 'primary', now(), now())",
            (thread_id, profile_a),
        )
        _safe_write(
            "INSERT INTO chain_thread_members (thread_id, profile_id) VALUES (%s, %s), (%s, %s) ON CONFLICT DO NOTHING",
            (thread_id, profile_a, thread_id, profile_b),
        )
    except Exception:
        _THREADS[thread_id] = {"id": thread_id, "thread_type": "direct", "members": [profile_a, profile_b], "created_at": _now()}
        _MESSAGES.setdefault(thread_id, [])
    return {"ok": True, "thread_id": thread_id, "existing": False}


def send_text_message(thread_id, sender_profile_id, body, **meta):
    thread_id = _uuid(thread_id)
    sender_profile_id = _uuid(sender_profile_id)
    body = (body or "").strip()
    if not body:
        return {"ok": False, "error": "empty_message"}
    message_id = str(uuid.uuid4())
    client_event_id = meta.get("client_event_id") or str(uuid.uuid4())
    parent_message_id = meta.get("parent_message_id")
    is_forwarded = bool(meta.get("is_forwarded"))
    try:
        encrypted = False
        encrypted_payload = None
        encryption_version = 1
        encryption_session_id = None
        try:
            member_rows = _safe_query(
                "SELECT profile_id FROM chain_thread_members WHERE thread_id = %s AND profile_id != %s LIMIT 1",
                (thread_id, sender_profile_id), default=[],
            )
            if member_rows and body:
                from services.e2ee_service import encrypt_message_payload
                target_id = str(member_rows[0]["profile_id"])
                enc_result = encrypt_message_payload(body, sender_profile_id, peer_profile_id=target_id, thread_id=thread_id)
                if enc_result.get("ok"):
                    encrypted = True
                    encrypted_payload = enc_result["encrypted_payload"]
                    encryption_version = enc_result.get("encryption_version", 1)
                    body = enc_result.get("fallback_body", body)
        except Exception:
            pass
        rows = _safe_write(
            """
            INSERT INTO chain_messages
                (id, thread_id, sender_profile_id, body, message_type, client_event_id, parent_message_id, is_forwarded, delivery_status, created_at, encrypted, encryption_version, encrypted_payload, encryption_session_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'sent', now(), %s, %s, %s::jsonb, %s)
            RETURNING id, thread_id, sender_profile_id, body, message_type, delivery_status, is_seen, created_at
            """,
            (message_id, thread_id, sender_profile_id, body, meta.get("message_type", "text"), client_event_id, parent_message_id, is_forwarded, encrypted, encryption_version, json.dumps(encrypted_payload) if encrypted_payload else None, encryption_session_id),
        )
        message = rows[0] if rows else {"id": message_id, "thread_id": thread_id, "sender_profile_id": sender_profile_id, "body": body}
        _safe_write("UPDATE chain_message_threads SET updated_at = now() WHERE id = %s", (thread_id,), timeout_ms=500)
    except Exception:
        message = {
            "id": message_id,
            "thread_id": thread_id,
            "sender_profile_id": sender_profile_id,
            "body": body,
            "message_type": meta.get("message_type", "text"),
            "delivery_status": "sent",
            "parent_message_id": parent_message_id,
            "is_forwarded": is_forwarded,
            "created_at": _now(),
        }
        _MESSAGES.setdefault(thread_id, []).append(message)
    emit_to_thread(thread_id, "message:new", message)
    return {"ok": True, "message": message, "message_id": message_id}


_MESSAGE_COLUMNS = "id, thread_id, sender_profile_id, body, message_type, media_url, delivery_status, is_seen, seen_at, read_at, delivered_at, created_at, edited_at, deleted_at, deleted_for_everyone, reply_to_message_id, parent_message_id, is_forwarded, client_event_id, voice_duration_seconds, encrypted, encrypted_payload, encryption_version, encryption_session_id"

def get_thread_messages(thread_id, profile_id=None, limit=100):
    thread_id = _uuid(thread_id)
    viewer_profile_id = profile_id or ""
    rows = _safe_query(
        f"""
        SELECT {_MESSAGE_COLUMNS} FROM chain_messages
        WHERE thread_id = %s AND deleted_at IS NULL
        ORDER BY created_at ASC
        LIMIT %s
        """,
        (thread_id, int(limit)),
        default=None,
    )
    if rows:
        for row in rows:
            if row.get("encrypted") and row.get("encrypted_payload") and viewer_profile_id:
                try:
                    from services.e2ee_service import decrypt_message_payload
                    ep = row["encrypted_payload"]
                    if isinstance(ep, str):
                        ep = json.loads(ep)
                    dec_result = decrypt_message_payload(ep, viewer_profile_id)
                    if dec_result.get("ok"):
                        row["body"] = dec_result["plaintext"]
                        row["decrypted"] = True
                    else:
                        row["body"] = "\U0001f512 Encrypted message"
                        row["decrypted"] = False
                except Exception:
                    row["body"] = "\U0001f512 Encrypted message"
                    row["decrypted"] = False
            else:
                row["decrypted"] = True
        return rows
    return [message for message in list(_MESSAGES.get(thread_id, [])) if not message.get("deleted_at")][-int(limit):]


def mark_delivered(thread_id, profile_id):
    thread_id = _uuid(thread_id)
    profile_id = _uuid(profile_id)
    try:
        _safe_write(
            "UPDATE chain_messages SET delivery_status = 'delivered', delivered_at = COALESCE(delivered_at, now()) WHERE thread_id = %s AND sender_profile_id != %s AND delivery_status = 'sent'",
            (thread_id, profile_id),
        )
    except Exception:
        for message in _MESSAGES.get(thread_id, []):
            if message.get("sender_profile_id") != profile_id and message.get("delivery_status") == "sent":
                message["delivery_status"] = "delivered"
                message["delivered_at"] = _now()
    emit_to_thread(thread_id, "message:delivered", {"thread_id": thread_id, "profile_id": profile_id})
    return {"ok": True}


def mark_seen(thread_id, profile_id):
    thread_id = _uuid(thread_id)
    profile_id = _uuid(profile_id)
    try:
        _safe_write(
            "UPDATE chain_messages SET is_seen = TRUE, delivery_status = 'seen', seen_at = COALESCE(seen_at, now()), read_at = COALESCE(read_at, now()) WHERE thread_id = %s AND sender_profile_id != %s",
            (thread_id, profile_id),
        )
        _safe_write("UPDATE chain_thread_members SET last_read_at = now() WHERE thread_id = %s AND profile_id = %s", (thread_id, profile_id), timeout_ms=500)
    except Exception:
        _READS[(thread_id, profile_id)] = _now()
        for message in _MESSAGES.get(thread_id, []):
            if message.get("sender_profile_id") != profile_id:
                message["is_seen"] = True
                message["delivery_status"] = "seen"
                message["seen_at"] = _now()
    emit_to_thread(thread_id, "message:seen", {"thread_id": thread_id, "profile_id": profile_id})
    return {"ok": True}


def unread_count(profile_id):
    profile_id = _uuid(profile_id)
    rows = _safe_query(
        """
        SELECT COUNT(*) AS count
        FROM chain_messages m
        JOIN chain_thread_members tm ON tm.thread_id = m.thread_id AND tm.profile_id = %s
        WHERE m.sender_profile_id != %s AND COALESCE(m.is_seen, FALSE) = FALSE AND m.deleted_at IS NULL
        """,
        (profile_id, profile_id),
        default=None,
    )
    if rows:
        return int(rows[0].get("count") or 0)
    total = 0
    for thread_id, messages in _MESSAGES.items():
        if profile_id in (_THREADS.get(thread_id, {}).get("members") or []):
            total += sum(1 for m in messages if m.get("sender_profile_id") != profile_id and not m.get("is_seen"))
    return total


def add_reaction(message_id, profile_id, reaction_type):
    message_id = _uuid(message_id)
    profile_id = _uuid(profile_id)
    reaction_type = (reaction_type or "like").strip()
    try:
        _safe_write(
            "INSERT INTO chain_message_reactions (message_id, profile_id, reaction_type) VALUES (%s, %s, %s) ON CONFLICT (message_id, profile_id) DO NOTHING",
            (message_id, profile_id, reaction_type),
        )
    except Exception:
        _REACTIONS.setdefault(message_id, set()).add((profile_id, reaction_type))
    thread_id = message_thread_id(message_id)
    payload = {"message_id": message_id, "thread_id": thread_id, "profile_id": profile_id, "reaction_type": reaction_type, "reaction": reaction_type, "added": True}
    emit_to_thread(thread_id, "message:reaction", payload)
    emit_to_thread(thread_id, "reaction:new", payload)
    return {"ok": True}


def edit_message(message_id, editor_profile_id, new_body):
    message_id = _uuid(message_id)
    editor_profile_id = _uuid(editor_profile_id)
    new_body = (new_body or "").strip()
    if not new_body:
        return {"ok": False, "error": "empty_message"}
    try:
        rows = _safe_query("SELECT body, thread_id FROM chain_messages WHERE id = %s LIMIT 1", (message_id,), default=[])
        old_body = rows[0].get("body") if rows else None
        _safe_write("UPDATE chain_messages SET body = %s, edited_at = now() WHERE id = %s AND sender_profile_id = %s", (new_body, message_id, editor_profile_id))
        _safe_write("INSERT INTO chain_message_edits (id, message_id, editor_profile_id, old_body, new_body) VALUES (%s, %s, %s, %s, %s)", (str(uuid.uuid4()), message_id, editor_profile_id, old_body, new_body), timeout_ms=500)
    except Exception:
        for messages in _MESSAGES.values():
            for message in messages:
                if message.get("id") == message_id:
                    message["body"] = new_body
                    message["edited_at"] = _now()
    return {"ok": True, "message_id": message_id, "body": new_body}


def delete_message(message_id, profile_id, for_everyone=False):
    message_id = _uuid(message_id)
    profile_id = _uuid(profile_id)
    try:
        if for_everyone:
            _safe_write("UPDATE chain_messages SET deleted_at = now(), deleted_for_everyone = TRUE WHERE id = %s AND sender_profile_id = %s", (message_id, profile_id))
        else:
            _safe_write("INSERT INTO chain_message_deletions (message_id, profile_id, delete_scope) VALUES (%s, %s, 'me') ON CONFLICT DO NOTHING", (message_id, profile_id))
    except Exception:
        for messages in _MESSAGES.values():
            for message in messages:
                if message.get("id") == message_id:
                    if for_everyone:
                        message["deleted_at"] = _now()
                    else:
                        message.setdefault("deleted_for", []).append(profile_id)
    thread_id = message_thread_id(message_id)
    payload = {"message_id": message_id, "thread_id": thread_id, "for_everyone": bool(for_everyone)}
    emit_to_thread(thread_id, "message:delete", payload)
    emit_to_thread(thread_id, "message:deleted", payload)
    return {"ok": True}


def star_message(message_id, profile_id, starred=True):
    message_id = _uuid(message_id)
    profile_id = _uuid(profile_id)
    try:
        if starred:
            _safe_write("INSERT INTO chain_message_stars (message_id, profile_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (message_id, profile_id))
        else:
            _safe_write("DELETE FROM chain_message_stars WHERE message_id = %s AND profile_id = %s", (message_id, profile_id))
    except Exception:
        key = (message_id, profile_id)
        _STARS.add(key) if starred else _STARS.discard(key)
    return {"ok": True, "starred": bool(starred)}


def pin_message(message_id, profile_id, pinned=True):
    message_id = _uuid(message_id)
    profile_id = _uuid(profile_id)
    thread_id = message_thread_id(message_id)
    payload = {"message_id": message_id, "profile_id": profile_id, "thread_id": thread_id, "pinned": bool(pinned), "updated_at": _now()}
    try:
        if pinned:
            _safe_write(
                """
                INSERT INTO chain_message_pins (message_id, thread_id, profile_id, pinned)
                VALUES (%s, %s, %s, TRUE)
                """,
                (message_id, thread_id or None, profile_id),
            )
        else:
            _safe_write("UPDATE chain_message_pins SET pinned = FALSE, updated_at = now() WHERE message_id = %s AND profile_id = %s", (message_id, profile_id))
    except Exception:
        _PINS[(message_id, profile_id)] = payload
    emit_to_thread(thread_id, "message:pinned", payload)
    return {"ok": True, "pinned": bool(pinned), "message_id": message_id}


def forward_messages(profile_id, message_ids, to_thread_ids):
    profile_id = _uuid(profile_id)
    message_ids = [_uuid(mid) for mid in (message_ids or [])]
    to_thread_ids = [_uuid(tid) for tid in (to_thread_ids or [])]
    forwarded = []
    for source_id in message_ids:
        source_thread = message_thread_id(source_id)
        source = None
        rows = _safe_query(f"SELECT {_MESSAGE_COLUMNS} FROM chain_messages WHERE id = %s LIMIT 1", (source_id,), default=[])
        if rows:
            source = rows[0]
        else:
            for messages in _MESSAGES.values():
                for message in messages:
                    if message.get("id") == source_id:
                        source = message
                        break
        if not source:
            continue
        for thread_id in to_thread_ids:
            sent = send_text_message(thread_id, profile_id, source.get("body") or "", parent_message_id=source_id, is_forwarded=True, message_type=source.get("message_type") or "text")
            if not sent.get("ok"):
                continue
            forwarded_id = sent["message_id"]
            try:
                _safe_write(
                    "INSERT INTO chain_message_forwards (source_message_id, forwarded_message_id, from_thread_id, to_thread_id, profile_id) VALUES (%s, %s, %s, %s, %s)",
                    (source_id, forwarded_id, source_thread or None, thread_id, profile_id),
                    timeout_ms=700,
                )
            except Exception:
                pass
            payload = {"source_message_id": source_id, "forwarded_message_id": forwarded_id, "to_thread_id": thread_id, "profile_id": profile_id}
            forwarded.append(payload)
            emit_to_thread(thread_id, "message:forwarded", payload)
    return {"ok": True, "forwarded": forwarded, "count": len(forwarded)}


def multi_select_action(profile_id, message_ids, action, **kwargs):
    message_ids = [_uuid(mid) for mid in (message_ids or [])]
    results = []
    for message_id in message_ids:
        if action == "star":
            results.append(star_message(message_id, profile_id, True))
        elif action == "unstar":
            results.append(star_message(message_id, profile_id, False))
        elif action == "pin":
            results.append(pin_message(message_id, profile_id, True))
        elif action == "unpin":
            results.append(pin_message(message_id, profile_id, False))
        elif action == "delete_for_me":
            results.append(delete_message(message_id, profile_id, False))
        elif action == "delete_for_everyone":
            results.append(delete_message(message_id, profile_id, True))
        elif action == "forward":
            results.append(forward_messages(profile_id, [message_id], kwargs.get("to_thread_ids") or []))
    return {"ok": True, "action": action, "count": len(results), "results": results}


def save_draft(thread_id, profile_id, body="", **payload):
    thread_id = _uuid(thread_id)
    profile_id = _uuid(profile_id)
    record = {"thread_id": thread_id, "profile_id": profile_id, "body": body or "", "payload": payload, "updated_at": _now()}
    try:
        _safe_write(
            """
            INSERT INTO chain_message_drafts (thread_id, profile_id, body, attachment_payload, voice_note_payload)
            VALUES (%s, %s, %s, %s::jsonb, %s::jsonb)
            """,
            (thread_id, profile_id, body or "", json.dumps(payload.get("attachments") or {}), json.dumps(payload.get("voice_note") or {})),
        )
    except Exception:
        _DRAFTS[(thread_id, profile_id)] = record
    emit_to_thread(thread_id, "message:draft", record)
    return {"ok": True, "draft": record}


def schedule_message(thread_id, profile_id, body, scheduled_for, **payload):
    thread_id = _uuid(thread_id)
    profile_id = _uuid(profile_id)
    scheduled_id = str(uuid.uuid4())
    record = {"id": scheduled_id, "thread_id": thread_id, "sender_profile_id": profile_id, "body": body or "", "scheduled_for": scheduled_for, "status": "scheduled", "payload": payload}
    try:
        _safe_write(
            """
            INSERT INTO chain_message_scheduled (id, thread_id, sender_profile_id, body, message_type, scheduled_for, payload)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (scheduled_id, thread_id, profile_id, body or "", payload.get("message_type", "text"), scheduled_for, json.dumps(payload)),
        )
    except Exception:
        _SCHEDULED[scheduled_id] = record
    return {"ok": True, "scheduled": record}


def save_wallpaper(thread_id, profile_id, wallpaper_key=None, wallpaper_url=None, **settings):
    thread_id = _uuid(thread_id)
    profile_id = _uuid(profile_id)
    record = {"thread_id": thread_id, "profile_id": profile_id, "wallpaper_key": wallpaper_key, "wallpaper_url": wallpaper_url, "settings": settings}
    try:
        _safe_write(
            "INSERT INTO chain_message_wallpapers (thread_id, profile_id, wallpaper_key, wallpaper_url, settings) VALUES (%s, %s, %s, %s, %s::jsonb)",
            (thread_id, profile_id, wallpaper_key, wallpaper_url, json.dumps(settings)),
        )
    except Exception:
        _WALLPAPERS[(thread_id, profile_id)] = record
    return {"ok": True, "wallpaper": record}


def save_shared_item(thread_id, message_id, profile_id, item_type, **meta):
    thread_id = _uuid(thread_id)
    message_id = _uuid(message_id) if message_id else None
    profile_id = _uuid(profile_id) if profile_id else None
    item_type = item_type if item_type in {"media", "document", "link"} else "link"
    record = {"id": str(uuid.uuid4()), "thread_id": thread_id, "message_id": message_id, "profile_id": profile_id, "item_type": item_type, **meta}
    try:
        _safe_write(
            """
            INSERT INTO chain_message_shared_items (id, thread_id, message_id, profile_id, item_type, title, url, mime_type, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (record["id"], thread_id, message_id, profile_id, item_type, meta.get("title"), meta.get("url"), meta.get("mime_type"), json.dumps(meta.get("metadata") or {})),
        )
    except Exception:
        _SHARED_ITEMS.setdefault(thread_id, []).append(record)
    return {"ok": True, "item": record}


def list_shared_items(thread_id, item_type=None):
    thread_id = _uuid(thread_id)
    params = [thread_id]
    clause = "thread_id = %s"
    if item_type:
        clause += " AND item_type = %s"
        params.append(item_type)
    rows = _safe_query(f"SELECT id, thread_id, message_id, profile_id, item_type, title, url, mime_type, metadata, created_at FROM chain_message_shared_items WHERE {clause} ORDER BY created_at DESC LIMIT 100", tuple(params), default=None)
    if rows:
        return rows
    items = list(_SHARED_ITEMS.get(thread_id, []))
    return [item for item in items if not item_type or item.get("item_type") == item_type]


def save_autodownload_settings(profile_id, **settings):
    profile_id = _uuid(profile_id)
    defaults = {
        "wifi_photos": True,
        "wifi_videos": False,
        "wifi_documents": True,
        "mobile_photos": False,
        "mobile_videos": False,
        "mobile_documents": False,
    }
    defaults.update({key: bool(value) for key, value in settings.items() if key in defaults})
    try:
        _safe_write(
            """
            INSERT INTO chain_message_autodownload_settings
            (profile_id, wifi_photos, wifi_videos, wifi_documents, mobile_photos, mobile_videos, mobile_documents)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (profile_id, defaults["wifi_photos"], defaults["wifi_videos"], defaults["wifi_documents"], defaults["mobile_photos"], defaults["mobile_videos"], defaults["mobile_documents"]),
        )
    except Exception:
        _AUTODOWNLOAD[profile_id] = defaults
    return {"ok": True, "settings": defaults}


def save_encryption_status(thread_id, profile_id=None, status="transport_protected", **metadata):
    thread_id = _uuid(thread_id)
    profile_id = _uuid(profile_id) if profile_id else None
    record = {"thread_id": thread_id, "profile_id": profile_id, "status": status, "metadata": metadata}
    try:
        _safe_write(
            "INSERT INTO chain_message_encryption_status (thread_id, profile_id, status, metadata) VALUES (%s, %s, %s, %s::jsonb)",
            (thread_id, profile_id, status, json.dumps(metadata)),
        )
    except Exception:
        _ENCRYPTION[(thread_id, profile_id)] = record
    return {"ok": True, "encryption": record}


def save_voice_note(message_id, profile_id, audio_url=None, duration_seconds=0, waveform=None, **meta):
    message_id = _uuid(message_id)
    profile_id = _uuid(profile_id)
    payload = {
        "message_id": message_id,
        "profile_id": profile_id,
        "audio_url": audio_url,
        "duration_seconds": float(duration_seconds or 0),
        "waveform": waveform or [],
        "mime_type": meta.get("mime_type"),
        "file_size": meta.get("file_size"),
        "playback_speed": float(meta.get("playback_speed") or 1),
        "played": bool(meta.get("played", False)),
        "draft_state": meta.get("draft_state"),
    }
    try:
        _safe_write(
            """
            INSERT INTO chain_message_voice_notes (message_id, profile_id, audio_url, duration_seconds, waveform, mime_type, file_size, playback_speed, played, draft_state)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
            """,
            (message_id, profile_id, audio_url, payload["duration_seconds"], json.dumps(payload["waveform"]), payload["mime_type"], payload["file_size"], payload["playback_speed"], payload["played"], payload["draft_state"]),
        )
    except Exception:
        _VOICE_NOTES[message_id] = payload
    return {"ok": True, "voice_note": payload}


def save_voice_note_draft(thread_id, profile_id, **meta):
    thread_id = _uuid(thread_id)
    profile_id = _uuid(profile_id)
    draft_id = str(uuid.uuid4())
    payload = {"id": draft_id, "thread_id": thread_id, "profile_id": profile_id, **meta}
    try:
        _safe_write(
            """
            INSERT INTO chain_voice_note_drafts (id, thread_id, profile_id, audio_url, duration_seconds, waveform, mime_type, file_size, draft_state)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
            """,
            (draft_id, thread_id, profile_id, meta.get("audio_url"), meta.get("duration_seconds") or 0, json.dumps(meta.get("waveform") or []), meta.get("mime_type"), meta.get("file_size"), meta.get("draft_state") or "draft"),
        )
    except Exception:
        _VOICE_DRAFTS[draft_id] = payload
    return {"ok": True, "draft": payload}


def save_voice_playback_state(message_id, profile_id, playback_speed=1, played=False, position_seconds=0):
    message_id = _uuid(message_id)
    profile_id = _uuid(profile_id)
    payload = {"message_id": message_id, "profile_id": profile_id, "playback_speed": float(playback_speed or 1), "played": bool(played), "position_seconds": float(position_seconds or 0)}
    try:
        _safe_write(
            """
            INSERT INTO chain_voice_note_playback_state (message_id, profile_id, playback_speed, played, position_seconds)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (message_id, profile_id, payload["playback_speed"], payload["played"], payload["position_seconds"]),
        )
    except Exception:
        _VOICE_PLAYBACK[(message_id, profile_id)] = payload
    return {"ok": True, "playback": payload}


def save_attachment(message_id, profile_id, attachment_type="file", **meta):
    message_id = _uuid(message_id)
    profile_id = _uuid(profile_id)
    payload = {"message_id": message_id, "profile_id": profile_id, "attachment_type": attachment_type, **meta}
    try:
        _safe_write(
            """
            INSERT INTO chain_message_attachments (message_id, profile_id, attachment_type, file_name, media_url, storage_bucket, storage_path, mime_type, file_size)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (message_id, profile_id, attachment_type, meta.get("file_name"), meta.get("media_url"), meta.get("storage_bucket"), meta.get("storage_path"), meta.get("mime_type"), meta.get("file_size")),
        )
    except Exception:
        _ATTACHMENTS.setdefault(message_id, []).append(payload)
    return {"ok": True, "attachment": payload}


def search_messages(profile_id, query):
    profile_id = _uuid(profile_id)
    query = (query or "").strip()
    if len(query) < 2:
        return []
    rows = _safe_query(
        """
        SELECT m.id, m.thread_id, m.sender_profile_id, m.body, m.message_type,
               m.media_url, m.delivery_status, m.is_seen, m.seen_at, m.read_at,
               m.delivered_at, m.created_at, m.edited_at, m.deleted_at,
               m.deleted_for_everyone, m.reply_to_message_id, m.parent_message_id,
               m.is_forwarded, m.client_event_id, m.voice_duration_seconds
        FROM chain_messages m
        JOIN chain_thread_members tm ON tm.thread_id = m.thread_id
        WHERE tm.profile_id = %s AND m.body ILIKE %s AND m.deleted_at IS NULL
        ORDER BY m.created_at DESC LIMIT 50
        """,
        (profile_id, f"%{query}%"),
        default=None,
    )
    if rows:
        return rows
    pattern = re.compile(re.escape(query), re.I)
    return [m for messages in _MESSAGES.values() for m in messages if pattern.search(m.get("body") or "")]


def get_message_info(message_id, profile_id):
    message_id = _uuid(message_id)
    profile_id = _uuid(profile_id)
    try:
        rows = _safe_query(
            f"SELECT {_MESSAGE_COLUMNS} FROM chain_messages WHERE id = %s LIMIT 1",
            (message_id,), default=[]
        )
        if rows:
            m = rows[0]
            sender_username = None
            try:
                sr = _safe_query("SELECT username FROM chain_profiles WHERE id = %s", (m.get("sender_profile_id"),), default=[])
                if sr:
                    sender_username = sr[0].get("username")
            except Exception:
                pass
            return {"ok": True, "message": {**m, "sender_username": sender_username}}
    except Exception:
        for messages in _MESSAGES.values():
            for message in messages:
                if message.get("id") == message_id:
                    return {"ok": True, "message": message}
    return {"ok": False, "error": "not_found"}


def message_thread_id(message_id):
    message_id = str(message_id)
    rows = _safe_query("SELECT thread_id FROM chain_messages WHERE id = %s LIMIT 1", (message_id,), default=[])
    if rows:
        return str(rows[0]["thread_id"])
    for thread_id, messages in _MESSAGES.items():
        if any(m.get("id") == message_id for m in messages):
            return thread_id
    return ""
