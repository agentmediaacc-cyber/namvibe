from flask import Blueprint, g
from services.api_auth_service import api_response, api_login_required
from services.creator_analytics_engine import get_creator_stats

creator_api_bp = Blueprint('creator_api', __name__, url_prefix='/creator')

@creator_api_bp.route('/analytics', methods=['GET'])
@api_login_required
def get_analytics():
    stats = get_creator_stats(g.api_user['id'])
    return api_response(data=stats)
