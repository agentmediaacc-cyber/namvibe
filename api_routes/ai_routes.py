from flask import Blueprint, jsonify, request, session, render_template
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.ai_assistant_service import (
    create_session, get_sessions, get_session, delete_session,
    chat, creator_assistant, marketplace_assistant, dating_safety_assistant,
    moderation_assistant, message_suggestions, caption_generator,
    profile_suggestions, ai_search, submit_feedback,
    log_moderation_action, get_suggestion_history, get_moderation_log,
    mark_suggestion_applied, mark_suggestion_dismissed,
    ASSISTANT_TYPES,
)

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')

# ─── HTML Pages ───

@ai_bp.route('/')
def index():
    profile = get_current_profile()
    return render_template('ai/index.html', profile=profile, assistants=ASSISTANT_TYPES)

# ─── Session management ───

@ai_bp.route('/api/sessions', methods=['GET'])
@login_required
def api_list_sessions():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    assistant_type = request.args.get('assistant_type')
    sessions = get_sessions(profile_id, assistant_type=assistant_type)
    return jsonify({'ok': True, 'sessions': sessions})

@ai_bp.route('/api/sessions', methods=['POST'])
@login_required
def api_create_session():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    assistant_type = data.get('assistant_type', 'general')
    title = data.get('title')
    result = create_session(profile_id, assistant_type, title=title)
    if result.get('ok'):
        return jsonify(result), 200
    return jsonify(result), 400

@ai_bp.route('/api/sessions/<session_id>', methods=['GET'])
@login_required
def api_get_session(session_id):
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    sess = get_session(profile_id, session_id)
    if not sess:
        return jsonify({'ok': False, 'error': 'session_not_found'}), 404
    return jsonify({'ok': True, 'session': sess})

@ai_bp.route('/api/sessions/<session_id>', methods=['DELETE'])
@login_required
def api_delete_session(session_id):
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    result = delete_session(profile_id, session_id)
    if result.get('ok'):
        return jsonify({'ok': True}), 200
    return jsonify(result), 404

# ─── Chat ───

@ai_bp.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    assistant_type = data.get('assistant_type', 'general')
    message = data.get('message', '').strip()
    session_id = data.get('session_id')
    context = data.get('context')
    if not message:
        return jsonify({'ok': False, 'error': 'message_required'}), 400
    result = chat(profile_id, assistant_type, message, session_id=session_id, context=context)
    if result.get('ok'):
        return jsonify(result), 200
    return jsonify(result), 400

# ─── Feature-specific assistants ───

@ai_bp.route('/api/creator', methods=['POST'])
@login_required
def api_creator_assistant():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    query = data.get('query', '').strip()
    context = data.get('context')
    if not query:
        return jsonify({'ok': False, 'error': 'query_required'}), 400
    result = creator_assistant(profile_id, query, context=context)
    return jsonify(result), 200

@ai_bp.route('/api/marketplace', methods=['POST'])
@login_required
def api_marketplace_assistant():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    query = data.get('query', '').strip()
    context = data.get('context')
    if not query:
        return jsonify({'ok': False, 'error': 'query_required'}), 400
    result = marketplace_assistant(profile_id, query, context=context)
    return jsonify(result), 200

@ai_bp.route('/api/dating-safety', methods=['POST'])
@login_required
def api_dating_safety():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    query = data.get('query', '').strip()
    context = data.get('context')
    if not query:
        return jsonify({'ok': False, 'error': 'query_required'}), 400
    result = dating_safety_assistant(profile_id, query, context=context)
    return jsonify(result), 200

@ai_bp.route('/api/moderation', methods=['POST'])
@login_required
def api_moderation():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    query = data.get('query', '').strip()
    context = data.get('context')
    if not query:
        return jsonify({'ok': False, 'error': 'query_required'}), 400
    result = moderation_assistant(profile_id, query, context=context)
    return jsonify(result), 200

@ai_bp.route('/api/message-suggestions', methods=['POST'])
@login_required
def api_message_suggestions():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    conversation_context = data.get('context', {})
    result = message_suggestions(profile_id, conversation_context)
    return jsonify(result), 200

@ai_bp.route('/api/captions', methods=['POST'])
@login_required
def api_captions():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    post_context = data.get('context', {})
    result = caption_generator(profile_id, post_context=post_context)
    return jsonify(result), 200

@ai_bp.route('/api/profile-suggestions', methods=['POST'])
@login_required
def api_profile_suggestions():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    profile_data = data.get('profile_data', {})
    result = profile_suggestions(profile_id, profile_data=profile_data)
    return jsonify(result), 200

@ai_bp.route('/api/search', methods=['POST'])
@login_required
def api_ai_search():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    query = data.get('query', '').strip()
    search_context = data.get('context', {})
    if not query:
        return jsonify({'ok': False, 'error': 'query_required'}), 400
    result = ai_search(profile_id, query, search_context=search_context)
    return jsonify(result), 200

# ─── Feedback ───

@ai_bp.route('/api/feedback', methods=['POST'])
@login_required
def api_feedback():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    assistant_type = data.get('assistant_type', 'general')
    rating = int(data.get('rating', 0))
    comment = data.get('comment', '')
    suggestion_id = data.get('suggestion_id')
    result = submit_feedback(profile_id, assistant_type, rating, comment=comment, suggestion_id=suggestion_id)
    if result.get('ok'):
        return jsonify({'ok': True}), 200
    return jsonify(result), 400

# ─── Suggestion history ───

@ai_bp.route('/api/suggestions', methods=['GET'])
@login_required
def api_suggestions():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    assistant_type = request.args.get('assistant_type')
    limit = request.args.get('limit', 50, type=int)
    suggestions = get_suggestion_history(profile_id, assistant_type=assistant_type, limit=limit)
    return jsonify({'ok': True, 'suggestions': suggestions})

@ai_bp.route('/api/suggestions/<suggestion_id>/apply', methods=['POST'])
@login_required
def api_apply_suggestion(suggestion_id):
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    result = mark_suggestion_applied(suggestion_id)
    return jsonify(result), 200

@ai_bp.route('/api/suggestions/<suggestion_id>/dismiss', methods=['POST'])
@login_required
def api_dismiss_suggestion(suggestion_id):
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    result = mark_suggestion_dismissed(suggestion_id)
    return jsonify(result), 200

# ─── Moderation log ───

@ai_bp.route('/api/moderation-log', methods=['GET'])
@login_required
def api_moderation_log():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    limit = request.args.get('limit', 50, type=int)
    log = get_moderation_log(limit=limit)
    return jsonify({'ok': True, 'log': log})

@ai_bp.route('/api/moderation-log', methods=['POST'])
@login_required
def api_log_moderation():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    action_type = data.get('action_type')
    target_type = data.get('target_type')
    target_id = data.get('target_id')
    target_profile_id = data.get('target_profile_id')
    reason = data.get('reason')
    confidence = data.get('confidence', 0.0)
    result = log_moderation_action(profile_id, action_type, target_type=target_type, target_id=target_id, target_profile_id=target_profile_id, reason=reason, confidence=confidence)
    if result.get('ok'):
        return jsonify({'ok': True}), 200
    return jsonify(result), 400

# ─── Assistant list ───

@ai_bp.route('/api/assistants', methods=['GET'])
def api_assistants():
    return jsonify({'ok': True, 'assistants': list(ASSISTANT_TYPES)})
