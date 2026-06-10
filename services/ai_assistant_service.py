"""Premium AI Assistant Ecosystem — safe fallback, no auto-actions, suggestions only."""

import os, json, hashlib, random
from datetime import datetime, timezone

from services.neon_service import fast_query, write_query, get_pool_status
from services.supabase_safe import safe_insert, safe_select, safe_update, safe_delete
from services.profile_service import get_current_profile, get_lightweight_profile

PLATFORM = "CHAIN"
AI_MARKER = "[AI Suggestion]"

ASSISTANT_TYPES = (
    'general', 'creator', 'marketplace', 'dating_safety', 'moderation',
    'messages', 'captions', 'profile_suggestions', 'search'
)

def _db_available():
    if os.getenv('FLASK_TESTING') == '1' or os.getenv('CHAIN_FAST_LOCAL') == '1':
        return False
    status = get_pool_status()
    return bool(status.get('pool_ready') or status.get('recent_success') or status.get('configured'))

def _utcnow():
    return datetime.now(timezone.utc).isoformat()

def _has_api_key():
    return bool(os.getenv('OPENAI_API_KEY') or os.getenv('AI_API_KEY') or os.getenv('ANTHROPIC_API_KEY'))

def _sanitize(text):
    if not text:
        return ''
    cleaned = text.replace('<', '&lt;').replace('>', '&gt;')
    if len(cleaned) > 5000:
        cleaned = cleaned[:5000]
    return cleaned

def _truncate_context(context, max_chars=2000):
    raw = json.dumps(context) if isinstance(context, dict) else str(context)
    if len(raw) > max_chars:
        return raw[:max_chars] + '…'
    return raw

# ─── Mock AI fallback ───

def _mock_response(assistant_type, user_input, context=None):
    """Return a safe mock response when no AI provider is configured."""
    input_lower = (user_input or '').lower()
    suggestions = {
        'general': [
            "Try exploring the Discover tab to find new creators and content.",
            "Your profile looks great! Consider adding a bio to help others learn about you.",
            "Engage with your audience by responding to comments on your posts.",
            "Use the CHAIN marketplace to find unique products and services.",
            "Stay safe online — never share personal contact information publicly.",
        ],
        'creator': [
            "Post consistently to grow your audience. Aim for 3-4 posts per week.",
            "Engage with your followers by replying to comments and DMs.",
            "Collaborate with other creators to cross-promote your content.",
            "Use analytics to see which content resonates most with your audience.",
            "Offer subscription tiers to provide exclusive content to your fans.",
        ],
        'marketplace': [
            "High-quality product photos increase sales by up to 40%.",
            "Respond to customer inquiries promptly to build trust.",
            "Offer competitive pricing by researching similar products.",
            "Promote your shop on your profile and in your posts.",
            "Positive reviews help build credibility — encourage satisfied buyers to leave feedback.",
        ],
        'dating_safety': [
            "Never share personal financial information with matches.",
            "Meet in public places for first dates and tell a friend where you're going.",
            "Trust your instincts — if something feels off, report and block.",
            "Keep conversations on the platform until you're comfortable.",
            "CHAIN will never ask for your password or payment details through DMs.",
        ],
        'moderation': [
            "Review reported content carefully before taking action.",
            "Consider context — not all controversial content violates guidelines.",
            "Document your reasoning for moderation decisions.",
            "Escalate complex cases to senior moderators.",
            "Apply warnings before permanent bans when appropriate.",
        ],
        'messages': [
            "Keep your messages friendly and respectful.",
            "Ask open-ended questions to keep the conversation flowing.",
            "Share relevant content or links when appropriate.",
            "Be mindful of response times — prompt replies show respect.",
            "If someone isn't responding, give them space.",
        ],
        'captions': [
            "Here's a caption idea: 'Living my best life! ✨ What's your favorite way to unwind?'",
            "Try this: 'New chapter, same mission. 🚀 Ready for what's next.'",
            "Caption suggestion: 'Grateful for this journey. 💫 Who's with me?'",
            "Consider: 'Some moments just hit different. 🎯 Drop a 🫶 if you agree.'",
            "How about: 'Leveling up every single day. 📈 What's one goal you're working on?'",
        ],
        'profile_suggestions': [
            "Add a clear profile photo that shows your face.",
            "Write a bio that tells people what you're about and what you create.",
            "Link your other social media accounts to build cross-platform presence.",
            "Highlight your best content in your featured section.",
            "Include your interests and hobbies to connect with like-minded people.",
        ],
        'search': [
            "Try searching by category to narrow down results.",
            "Use specific keywords for better search results.",
            "Filter by location to find content and creators near you.",
            "Check trending topics to discover what's popular.",
            "Save your favorite searches for quick access later.",
        ],
    }
    defaults = suggestions.get(assistant_type, suggestions['general'])
    response = random.choice(defaults)
    return {
        'ok': True,
        'response': f"{AI_MARKER} {response}",
        'suggestions': [f"{AI_MARKER} {s}" for s in random.sample(defaults, min(3, len(defaults)))],
        'provider': 'mock',
        'warning': 'AI provider not configured. Using offline suggestions.'
    }

# ─── AI Provider call (mock only — no external API) ───

def _call_ai_provider(assistant_type, user_input, context=None):
    if _has_api_key():
        pass
    return _mock_response(assistant_type, user_input, context)

# ─── Session management ───

def create_session(profile_id, assistant_type, title=None):
    if assistant_type not in ASSISTANT_TYPES:
        assistant_type = 'general'
    payload = {
        'profile_id': profile_id,
        'assistant_type': assistant_type,
        'title': title or f'{assistant_type.replace("_", " ").title()} Chat',
        'messages': json.dumps([]),
        'context': json.dumps({}),
        'created_at': _utcnow(),
        'updated_at': _utcnow(),
    }
    result = safe_insert('chain_ai_chat_sessions', payload)
    if result:
        return {'ok': True, 'session_id': result[0].get('id')}
    return {'ok': True, 'session_id': None, 'warning': 'Could not persist session'}

def get_sessions(profile_id, assistant_type=None):
    filters = {'profile_id': profile_id}
    if assistant_type:
        filters['assistant_type'] = assistant_type
    return safe_select('chain_ai_chat_sessions', limit=50, filters=filters, order_by='updated_at', desc=True)

def get_session(profile_id, session_id):
    rows = safe_select('chain_ai_chat_sessions', limit=1, filters={'id': session_id, 'profile_id': profile_id})
    return rows[0] if rows else None

def delete_session(profile_id, session_id):
    existing = safe_select('chain_ai_chat_sessions', limit=1, filters={'id': session_id, 'profile_id': profile_id})
    if not existing:
        return {'ok': False, 'error': 'Session not found'}
    safe_delete('chain_ai_chat_sessions', eq={'id': session_id})
    return {'ok': True}

# ─── Core chat ───

def chat(profile_id, assistant_type, message, session_id=None, context=None):
    if assistant_type not in ASSISTANT_TYPES:
        assistant_type = 'general'
    sanitized = _sanitize(message)
    if not sanitized:
        return {'ok': False, 'error': 'Message cannot be empty'}
    response = _call_ai_provider(assistant_type, sanitized, context)
    if not session_id:
        sess = create_session(profile_id, assistant_type)
        session_id = sess.get('session_id')
    if session_id:
        existing = get_session(profile_id, session_id)
        if existing:
            msgs = existing.get('messages') or []
            if isinstance(msgs, str):
                try:
                    msgs = json.loads(msgs)
                except (json.JSONDecodeError, TypeError):
                    msgs = []
            msgs.append({'role': 'user', 'content': sanitized, 'timestamp': _utcnow()})
            msgs.append({'role': 'assistant', 'content': response.get('response', ''), 'timestamp': _utcnow()})
            if len(msgs) > 100:
                msgs = msgs[-100:]
            safe_update('chain_ai_chat_sessions', {'messages': json.dumps(msgs), 'updated_at': _utcnow()}, eq={'id': session_id})
    if response.get('ok'):
        safe_insert('chain_ai_suggestions', {
            'profile_id': profile_id,
            'assistant_type': assistant_type,
            'input_text': sanitized,
            'output_text': response.get('response', ''),
            'context': json.dumps(context or {}),
        })
    return {
        'ok': True,
        'response': response.get('response', ''),
        'suggestions': response.get('suggestions', []),
        'session_id': session_id,
        'provider': response.get('provider', 'mock'),
        'warning': response.get('warning'),
    }

# ─── Feature-specific assistants ───

def creator_assistant(profile_id, query, context=None):
    return chat(profile_id, 'creator', query, context=context)

def marketplace_assistant(profile_id, query, context=None):
    return chat(profile_id, 'marketplace', query, context=context)

def dating_safety_assistant(profile_id, query, context=None):
    return chat(profile_id, 'dating_safety', query, context=context)

def moderation_assistant(profile_id, query, context=None):
    return chat(profile_id, 'moderation', query, context=context)

def message_suggestions(profile_id, conversation_context):
    sanitized = _sanitize(_truncate_context(conversation_context))
    response = _call_ai_provider('messages', sanitized)
    safe_insert('chain_ai_suggestions', {
        'profile_id': profile_id,
        'assistant_type': 'messages',
        'input_text': sanitized[:500],
        'output_text': response.get('response', ''),
        'context': json.dumps({'type': 'message_suggestion'}),
    })
    return {
        'ok': True,
        'suggestion': f"{AI_MARKER} {response.get('response', '')}",
        'alternatives': [f"{AI_MARKER} {s}" for s in response.get('suggestions', [])],
        'warning': 'These are suggestions. Review before sending.',
    }

def caption_generator(profile_id, post_context=None):
    context = post_context or {}
    sanitized = _sanitize(_truncate_context(context))
    response = _call_ai_provider('captions', sanitized)
    safe_insert('chain_ai_suggestions', {
        'profile_id': profile_id,
        'assistant_type': 'captions',
        'input_text': sanitized[:500],
        'output_text': response.get('response', ''),
        'context': json.dumps({'type': 'caption_generation'}),
    })
    return {
        'ok': True,
        'caption': f"{AI_MARKER} {response.get('response', '')}",
        'alternatives': [f"{AI_MARKER} {s}" for s in response.get('suggestions', [])],
    }

def profile_suggestions(profile_id, profile_data=None):
    context = profile_data or {}
    sanitized = _sanitize(_truncate_context(context))
    response = _call_ai_provider('profile_suggestions', sanitized)
    safe_insert('chain_ai_suggestions', {
        'profile_id': profile_id,
        'assistant_type': 'profile_suggestions',
        'input_text': sanitized[:500],
        'output_text': response.get('response', ''),
        'context': json.dumps({'type': 'profile_suggestion'}),
    })
    return {
        'ok': True,
        'suggestion': f"{AI_MARKER} {response.get('response', '')}",
        'alternatives': [f"{AI_MARKER} {s}" for s in response.get('suggestions', [])],
    }

def ai_search(profile_id, query, search_context=None):
    sanitized = _sanitize(query)
    if not sanitized:
        return {'ok': False, 'error': 'Search query cannot be empty'}
    context = search_context or {}
    response = _call_ai_provider('search', sanitized, context)
    safe_insert('chain_ai_suggestions', {
        'profile_id': profile_id,
        'assistant_type': 'search',
        'input_text': sanitized,
        'output_text': response.get('response', ''),
        'context': json.dumps(context),
    })
    return {
        'ok': True,
        'suggestion': f"{AI_MARKER} {response.get('response', '')}",
        'alternatives': [f"{AI_MARKER} {s}" for s in response.get('suggestions', [])],
    }

# ─── Feedback ───

def submit_feedback(profile_id, assistant_type, rating, comment=None, suggestion_id=None):
    if rating < 1 or rating > 5:
        return {'ok': False, 'error': 'Rating must be 1-5'}
    if assistant_type not in ASSISTANT_TYPES:
        return {'ok': False, 'error': 'Invalid assistant type'}
    safe_insert('chain_ai_feedback', {
        'profile_id': profile_id,
        'assistant_type': assistant_type,
        'suggestion_id': suggestion_id,
        'rating': rating,
        'comment': _sanitize(comment or ''),
        'created_at': _utcnow(),
    })
    return {'ok': True}

# ─── Moderation log ───

def log_moderation_action(moderator_id, action_type, target_type=None, target_id=None, target_profile_id=None, reason=None, confidence=0.0):
    valid_actions = ('auto_flag', 'auto_remove', 'assisted_review', 'escalated', 'dismissed')
    if action_type not in valid_actions:
        return {'ok': False, 'error': 'Invalid action type'}
    safe_insert('chain_ai_moderation_log', {
        'moderator_profile_id': moderator_id,
        'target_profile_id': target_profile_id,
        'target_type': target_type,
        'target_id': target_id,
        'action_type': action_type,
        'confidence_score': float(confidence),
        'reason': _sanitize(reason or ''),
        'ai_summary': f'{AI_MARKER} Auto-flagged by AI moderation',
        'created_at': _utcnow(),
    })
    return {'ok': True}

# ─── History / log retrieval ───

def get_suggestion_history(profile_id, assistant_type=None, limit=50):
    filters = {'profile_id': profile_id}
    if assistant_type:
        filters['assistant_type'] = assistant_type
    return safe_select('chain_ai_suggestions', limit=limit, filters=filters, order_by='created_at', desc=True)

def get_moderation_log(moderator_id=None, limit=50):
    if moderator_id:
        return safe_select('chain_ai_moderation_log', limit=limit, filters={'moderator_profile_id': moderator_id}, order_by='created_at', desc=True)
    return safe_select('chain_ai_moderation_log', limit=limit, order_by='created_at', desc=True)

def mark_suggestion_applied(suggestion_id):
    safe_update('chain_ai_suggestions', {'was_applied': True}, eq={'id': suggestion_id})
    return {'ok': True}

def mark_suggestion_dismissed(suggestion_id):
    safe_update('chain_ai_suggestions', {'was_dismissed': True}, eq={'id': suggestion_id})
    return {'ok': True}
