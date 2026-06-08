#!/usr/bin/env bash
set -e

echo "=== PHASE 20: PRODUCTION NEON MESSAGE DELIVERY ==="

mkdir -p backups/phase20 services api_routes
cp api_routes/message_upgrade_routes.py backups/phase20/message_upgrade_routes.py.bak 2>/dev/null || true

cat > services/message_delivery_service.py <<'PY'
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
            m.file_url,
            m.audio_url,
            m.voice_duration_seconds,
            m.delivery_status,
            m.is_delivered,
            m.delivered_at,
            m.is_seen,
            m.seen_at,
            m.read_at,
            m.created_at,
            p.username AS sender_username,
            p.full_name AS sender_name,
            p.avatar_url AS sender_avatar
        FROM chain_messages m
        LEFT JOIN chain_profiles p ON p.id = m.sender_profile_id
        WHERE m.thread_id = %s
          AND COALESCE(m.is_deleted, FALSE) = FALSE
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
            file_url,
            audio_url,
            voice_duration_seconds,
            delivery_status,
            is_delivered,
            delivered_at,
            is_seen,
            created_at
        )
        VALUES (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
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
        file_url,
        audio_url,
        voice_duration_seconds,
        delivery_status,
        has_receiver,
        has_receiver
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
          AND COALESCE(m.is_deleted, FALSE) = FALSE
    """, (profile_id, profile_id), default=[{"total": 0}])
    return int(rows[0]["total"]) if rows else 0

def mark_delivered_for_online_user(profile_id):
    write_query("""
        UPDATE chain_messages m
        SET
            is_delivered = TRUE,
            delivered_at = COALESCE(delivered_at, now()),
            delivery_status = CASE
                WHEN COALESCE(is_seen, FALSE) = TRUE THEN 'seen'
                ELSE 'delivered'
            END
        FROM chain_thread_members tm
        WHERE tm.thread_id = m.thread_id
          AND tm.profile_id = %s
          AND m.sender_profile_id != %s
          AND COALESCE(m.is_delivered, FALSE) = FALSE
    """, (profile_id, profile_id))
    return True
PY

cat > api_routes/message_production_routes.py <<'PY'
from flask import Blueprint, jsonify, request, session
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.message_delivery_service import (
    ensure_message_tables,
    get_thread_messages,
    send_message,
    unread_count,
    mark_delivered_for_online_user,
)

message_production_bp = Blueprint("message_production", __name__, url_prefix="/messages/api")

@message_production_bp.before_app_request
def _ensure_once():
    if not getattr(_ensure_once, "done", False):
        ensure_message_tables()
        _ensure_once.done = True

@message_production_bp.route("/thread/<thread_id>", methods=["GET"])
@login_required
def api_thread(thread_id):
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Login required"}), 401

    rows = get_thread_messages(thread_id, profile["id"])
    return jsonify({
        "ok": True,
        "thread_id": thread_id,
        "messages": rows
    })

@message_production_bp.route("/thread/<thread_id>/send", methods=["POST"])
@login_required
def api_send(thread_id):
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Login required"}), 401

    data = request.get_json(silent=True) or request.form.to_dict()
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"ok": False, "error": "Message is empty"}), 400

    msg = send_message(
        thread_id=thread_id,
        sender_profile_id=profile["id"],
        body=body,
        message_type=data.get("message_type", "text")
    )
    return jsonify({"ok": True, "message": msg})

@message_production_bp.route("/thread/<thread_id>/voice-note", methods=["POST"])
@login_required
def api_voice(thread_id):
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "Login required"}), 401

    seconds = request.form.get("seconds") or "0"
    msg = send_message(
        thread_id=thread_id,
        sender_profile_id=profile["id"],
        body=f"🎙 Voice note • {seconds}s",
        message_type="voice_note",
        voice_duration_seconds=int(float(seconds or 0))
    )
    return jsonify({"ok": True, "message": msg})

@message_production_bp.route("/unread-count", methods=["GET"])
@login_required
def api_unread():
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": True, "unread": 0})
    return jsonify({"ok": True, "unread": unread_count(profile["id"])})

@message_production_bp.route("/online", methods=["POST"])
@login_required
def api_online():
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False}), 401
    mark_delivered_for_online_user(profile["id"])
    return jsonify({"ok": True, "delivery": "updated"})
PY

python3 - <<'PY'
from pathlib import Path

p = Path("app.py")
text = p.read_text()

if "message_production_bp" not in text:
    text = "from api_routes.message_production_routes import message_production_bp\n" + text

if "app.register_blueprint(message_production_bp)" not in text:
    marker = "app.register_blueprint(message_upgrade_bp)"
    if marker in text:
        text = text.replace(marker, marker + "\napp.register_blueprint(message_production_bp)")
    else:
        text += "\napp.register_blueprint(message_production_bp)\n"

p.write_text(text)
print("Registered message_production_bp")
PY

python3 - <<'PY'
from pathlib import Path

p = Path("templates/messages/index.html")
text = p.read_text()

text = text.replace(
    "fetch('/messages/thread/' + encodeURIComponent(id))",
    "fetch('/messages/api/thread/' + encodeURIComponent(id))"
)

text = text.replace(
    "'/messages/thread/' + encodeURIComponent(currentThreadId) + '/send'",
    "'/messages/api/thread/' + encodeURIComponent(currentThreadId) + '/send'"
)

text = text.replace(
    "'/messages/thread/' + encodeURIComponent(currentThreadId) + '/voice-note'",
    "'/messages/api/thread/' + encodeURIComponent(currentThreadId) + '/voice-note'"
)

if "loadUnreadCount()" not in text:
    text = text.replace(
        "})();",
        """
    async function loadUnreadCount(){
        try{
            const res = await fetch('/messages/api/unread-count');
            const json = await res.json();
            let badge = document.getElementById('messageUnreadBadge');
            if(!badge){
                badge = document.createElement('span');
                badge.id = 'messageUnreadBadge';
                badge.style.cssText = 'margin-left:6px;background:#ff0050;color:white;border-radius:999px;padding:3px 7px;font-size:11px;font-weight:950;';
                document.querySelector('.chain-msg-brand h1')?.appendChild(badge);
            }
            badge.textContent = json.unread > 0 ? json.unread : '';
        }catch(e){}
    }

    fetch('/messages/api/online',{method:'POST'}).catch(()=>{});
    loadUnreadCount();
    setInterval(loadUnreadCount, 10000);
})();
"""
    )

p.write_text(text)
print("Frontend now uses production message API")
PY

python3 -m py_compile app.py api_routes/*.py services/*.py

echo ""
echo "=== ROUTES CHECK ==="
PYTHONPATH=. python3 - <<'PY'
from app import app
for r in sorted(app.url_map.iter_rules(), key=lambda x: str(x)):
    if str(r).startswith('/messages/api'):
        print(r, '=>', r.endpoint)
PY

echo ""
echo "✅ Phase 20 complete."
echo "Messages now save to Neon with sent/delivered/seen/unread logic."
