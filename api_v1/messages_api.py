from flask import Blueprint, request, g
from services.api_auth_service import api_response, api_error, api_login_required
from services.messaging_engine import list_threads, get_thread, send_message, mark_thread_seen

messages_api_bp = Blueprint('messages_api', __name__, url_prefix='/messages')

@messages_api_bp.route('/threads', methods=['GET'])
@api_login_required
def get_threads():
    threads = list_threads(g.api_user['id'])
    return api_response(data=threads)

@messages_api_bp.route('/threads/<thread_id>', methods=['GET'])
@api_login_required
def get_single_thread(thread_id):
    thread = get_thread(thread_id, g.api_user['id'])
    if not thread:
        return api_error("Thread not found", code="not_found", status=404)
    return api_response(data=thread)

@messages_api_bp.route('/send', methods=['POST'])
@api_login_required
def send_message_api():
    thread_id = request.form.get('thread_id')
    body = request.form.get('body')
    file = request.files.get('media')
    
    if not body and not file:
        return api_error("Message body or media required", code="invalid_input")
        
    msg_id = send_message(thread_id, g.api_user['id'], body, file)
    if not msg_id:
        return api_error("Failed to send message", code="send_failed")
        
    return api_response(data={"id": msg_id}, status=201)

@messages_api_bp.route('/threads/<thread_id>/seen', methods=['POST'])
@api_login_required
def mark_seen_api(thread_id):
    mark_thread_seen(thread_id, g.api_user['id'])
    return api_response(data={"success": True})
