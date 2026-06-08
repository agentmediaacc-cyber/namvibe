from flask import Blueprint, jsonify, request, session, redirect, render_template_string
from uuid import uuid4
from datetime import datetime

message_upgrade_bp = Blueprint("message_upgrade", __name__, url_prefix="/messages")

def _now():
    return datetime.utcnow().isoformat()

def _groups():
    session.setdefault("chain_groups", [])
    return session["chain_groups"]

def _messages():
    session.setdefault("chain_thread_messages", {})
    return session["chain_thread_messages"]

def _calls():
    session.setdefault("chain_call_logs", [])
    return session["chain_call_logs"]

@message_upgrade_bp.route("/@<username>")
def open_username_chat(username):
    thread_id = "user-" + username.lower()
    msgs = _messages()
    msgs.setdefault(thread_id, [
        {
            "id": str(uuid4()),
            "sender": username,
            "body": f"Chat with @{username}",
            "created_at": _now(),
            "mine": False
        }
    ])
    session.modified = True
    return redirect(f"/messages/?open={thread_id}&name=@{username}")

@message_upgrade_bp.route("/thread/<thread_id>")
def get_thread(thread_id):
    msgs = _messages().get(thread_id, [])
    return jsonify({"ok": True, "thread_id": thread_id, "messages": msgs})

@message_upgrade_bp.route("/thread/<thread_id>/send", methods=["POST"])
def send_message(thread_id):
    data = request.get_json(silent=True) or request.form.to_dict()
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"ok": False, "error": "Empty message"}), 400

    msgs = _messages()
    msgs.setdefault(thread_id, [])
    msg = {
        "id": str(uuid4()),
        "sender": "You",
        "body": body,
        "created_at": _now(),
        "mine": True
    }
    msgs[thread_id].append(msg)
    session.modified = True
    return jsonify({"ok": True, "message": msg})

@message_upgrade_bp.route("/message/<message_id>/delete", methods=["POST"])
def delete_message(message_id):
    msgs = _messages()
    for tid, arr in msgs.items():
        msgs[tid] = [m for m in arr if m.get("id") != message_id]
    session.modified = True
    return jsonify({"ok": True})

@message_upgrade_bp.route("/groups/create", methods=["POST"])
def create_group_chat():
    data = request.get_json(silent=True) or request.form.to_dict()
    name = (data.get("name") or "New CHAIN Group").strip()
    members = (data.get("members") or "").strip()
    group_id = "group-" + str(uuid4())

    group = {
        "id": group_id,
        "name": name,
        "members": members,
        "host": "You",
        "allow_type": data.get("allow_type", True) in [True, "true", "on", "1", 1],
        "allow_reply": data.get("allow_reply", True) in [True, "true", "on", "1", 1],
        "allow_comments": data.get("allow_comments", True) in [True, "true", "on", "1", 1],
        "allow_invite": data.get("allow_invite", False) in [True, "true", "on", "1", 1],
        "public": data.get("public", True) in [True, "true", "on", "1", 1],
        "access_type": data.get("access_type", "public"),
        "join_fee": data.get("join_fee", "0"),
        "premium_only": data.get("premium_only", False) in [True, "true", "on", "1", 1],
        "approve_members": data.get("approve_members", False) in [True, "true", "on", "1", 1],
        "created_at": _now()
    }
    _groups().append(group)

    _messages().setdefault(group_id, [
        {
            "id": str(uuid4()),
            "sender": "System",
            "body": f"Group created: {name}. Members can join, share posts, send adverts, comment and start group calls depending on host permissions.",
            "created_at": _now(),
            "mine": False
        }
    ])

    session.modified = True
    return jsonify({"ok": True, "group": group, "url": f"/messages/?open={group_id}&name={name}"})

@message_upgrade_bp.route("/groups")
def list_groups():
    q = (request.args.get("q") or "").lower().strip()
    groups = _groups()
    if q:
        groups = [g for g in groups if q in g.get("name", "").lower() or q in g.get("members", "").lower()]
    return jsonify({"ok": True, "groups": groups})

@message_upgrade_bp.route("/groups/<group_id>/join", methods=["POST"])
def join_group(group_id):
    for g in _groups():
        if g["id"] == group_id:
            g["members"] = (g.get("members") or "") + ", You"
            _messages().setdefault(group_id, []).append({
                "id": str(uuid4()),
                "sender": "System",
                "body": "You joined the group.",
                "created_at": _now(),
                "mine": False
            })
            session.modified = True
            return jsonify({"ok": True, "group": g})
    return jsonify({"ok": False, "error": "Group not found"}), 404

@message_upgrade_bp.route("/groups/<group_id>/delete", methods=["POST"])
def delete_group(group_id):
    session["chain_groups"] = [g for g in _groups() if g["id"] != group_id]
    _messages().pop(group_id, None)
    session.modified = True
    return jsonify({"ok": True})

@message_upgrade_bp.route("/groups/<group_id>/post", methods=["POST"])
def group_post(group_id):
    data = request.get_json(silent=True) or request.form.to_dict()
    body = (data.get("body") or data.get("post") or "").strip()
    if not body:
        return jsonify({"ok": False}), 400
    msg = {
        "id": str(uuid4()),
        "sender": "You",
        "body": "📢 " + body,
        "created_at": _now(),
        "mine": True,
        "kind": "group_post"
    }
    _messages().setdefault(group_id, []).append(msg)
    session.modified = True
    return jsonify({"ok": True, "message": msg})

@message_upgrade_bp.route("/calls/start", methods=["POST"])
def start_demo_call():
    data = request.get_json(silent=True) or request.form.to_dict()
    target = (data.get("target") or data.get("username") or "CHAIN User").strip()
    call_type = data.get("call_type") or "audio"
    call_id = "call-" + str(uuid4())

    call = {
        "id": call_id,
        "target": target,
        "call_type": call_type,
        "direction": "outgoing",
        "status": "ringing",
        "duration_seconds": 0,
        "created_at": _now()
    }
    _calls().insert(0, call)
    session.modified = True
    return jsonify({"ok": True, "call": call, "url": f"/messages/?call={call_id}"})

@message_upgrade_bp.route("/calls/logs")
def call_logs():
    return jsonify({"ok": True, "calls": _calls()})

@message_upgrade_bp.route("/calls/<call_id>/delete", methods=["POST"])
def delete_call_log(call_id):
    session["chain_call_logs"] = [c for c in _calls() if c["id"] != call_id]
    session.modified = True
    return jsonify({"ok": True})


@message_upgrade_bp.route("/thread/<thread_id>/attachment", methods=["POST"])
def send_attachment(thread_id):
    file = request.files.get("file")
    kind = request.form.get("kind", "file")
    if not file:
        return jsonify({"ok": False, "error": "No file"}), 400

    msg = {
        "id": str(uuid4()),
        "sender": "You",
        "body": f"📎 Attached {kind}: {file.filename}",
        "filename": file.filename,
        "kind": kind,
        "created_at": _now(),
        "mine": True
    }
    _messages().setdefault(thread_id, []).append(msg)
    session.modified = True
    return jsonify({"ok": True, "message": msg})


@message_upgrade_bp.route("/thread/<thread_id>/voice-note", methods=["POST"])
def send_voice_note(thread_id):
    seconds = request.form.get("seconds") or request.json.get("seconds") if request.is_json else "0"
    msg = {
        "id": str(uuid4()),
        "sender": "You",
        "body": f"🎙 Voice note • {seconds}s",
        "kind": "voice_note",
        "created_at": _now(),
        "mine": True
    }
    _messages().setdefault(thread_id, []).append(msg)
    session.modified = True
    return jsonify({"ok": True, "message": msg})


@message_upgrade_bp.route("/typing/<thread_id>", methods=["POST"])
def typing_status(thread_id):
    return jsonify({
        "ok": True,
        "thread_id": thread_id,
        "status": "typing",
        "text": "Typing..."
    })


@message_upgrade_bp.route("/groups/empty")
def groups_empty():
    groups = _groups()
    return jsonify({
        "ok": True,
        "has_groups": bool(groups),
        "message": "No groups yet. Create a public, private, paid or premium group."
    })
