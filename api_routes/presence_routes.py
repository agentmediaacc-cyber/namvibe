from flask import Blueprint, jsonify, session, request
from services.profile_service import get_current_profile
from services.presence_engine import get_presence
from datetime import datetime

presence_bp = Blueprint('presence', __name__, url_prefix='/api/presence')

@presence_bp.route('/status')
def status():
    profile = get_current_profile()
    if profile:
        presence = get_presence([profile['id']])
        if presence:
            return jsonify(presence[0])
    return jsonify({'online': False, 'last_seen_at': None})

@presence_bp.route('/bulk', methods=['POST'])
def bulk_status():
    data = request.get_json(silent=True) or {}
    profile_ids = data.get('profile_ids', [])
    if not profile_ids:
        return jsonify([])
    
    results = get_presence(profile_ids)
    return jsonify(results)
