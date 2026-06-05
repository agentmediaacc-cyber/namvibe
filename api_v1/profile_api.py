from flask import Blueprint, request, g
from services.api_auth_service import api_response, api_error, api_login_required, optional_api_user
from services.profile_service import get_current_profile, get_profile_by_username

profile_api_bp = Blueprint('profile_api', __name__, url_prefix='/profile')

@profile_api_bp.route('/me', methods=['GET'])
@api_login_required
def get_me_api():
    return api_response(data=g.api_user)

@profile_api_bp.route('/<username>', methods=['GET'])
@optional_api_user
def get_user_profile_api(username):
    profile = get_profile_by_username(username)
    if not profile:
        return api_error("Profile not found", code="not_found", status=404)
    return api_response(data=profile)
