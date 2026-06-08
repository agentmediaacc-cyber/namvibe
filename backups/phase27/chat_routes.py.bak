from flask import Blueprint, flash, redirect, render_template, request, url_for, session, jsonify
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.messaging_engine import list_threads, get_thread_messages, send_message, find_or_create_direct_thread
from services.neon_service import write_query

chat_bp = Blueprint("chat_v2", __name__, url_prefix="/chat")

@chat_bp.route("/")
@login_required
def inbox():
    profile = get_current_profile()
    threads = list_threads(profile["id"])
    return render_template("messages/index.html", threads=threads, profile=profile)

@chat_bp.route("/<thread_id>")
@login_required
def thread(thread_id):
    profile = get_current_profile()
    messages = get_thread_messages(thread_id, profile["id"])
    
    from services.neon_service import fast_query
    thread_info = fast_query("SELECT id FROM chain_message_threads WHERE id = %s", (thread_id,))
    if not thread_info:
        return redirect(url_for("messages.inbox"))
    
    # Mark as read
    write_query("UPDATE chain_thread_members SET last_read_at = now() WHERE thread_id = %s AND profile_id = %s", (thread_id, profile["id"]))
    
    return render_template("messages/thread.html", thread=thread_info[0], messages=messages, profile=profile)

@chat_bp.route("/start/<other_id>")
@login_required
def start_chat(other_id):
    current = get_current_profile()
    thread_id = find_or_create_direct_thread(current["id"], other_id)
    if not thread_id:
        flash("Could not start chat", "error")
        return redirect(url_for("messages.inbox"))
    
    return redirect(url_for("chat_v2.thread", thread_id=thread_id))

@chat_bp.route("/api/send", methods=["POST"])
@login_required
def api_send():
    profile = get_current_profile()
    thread_id = request.form.get("thread_id")
    body = request.form.get("body")
    media_file = request.files.get("media")

    if not body and not media_file:
        return jsonify({"error": "Message cannot be empty"}), 400

    msg_id = send_message(thread_id, profile["id"], body, media_file)
    if msg_id:
        return jsonify({"success": True, "message_id": msg_id}), 200
    return jsonify({"error": "Failed to send message"}), 500
