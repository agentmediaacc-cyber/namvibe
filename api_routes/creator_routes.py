from flask import Blueprint, render_template, g
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.creator_analytics_engine import get_creator_stats

creator_bp = Blueprint('creator', __name__, url_prefix='/creator')

@creator_bp.route('/dashboard')
@login_required
def dashboard():
    profile = get_current_profile()
    stats = get_creator_stats(profile['id'])
    return render_template('creator/dashboard.html', stats=stats)
