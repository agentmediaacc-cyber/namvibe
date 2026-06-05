from flask import Blueprint, request, g
from services.api_auth_service import api_response, api_error, api_login_required, optional_api_user
from services.reels_engine import list_reels, get_reel, create_reel, record_reel_view, like_reel

reels_api_bp = Blueprint('reels_api', __name__, url_prefix='/reels')

@reels_api_bp.route('/', methods=['GET'])
@optional_api_user
def get_reels():
    limit = int(request.args.get('limit', 20))
    reels = list_reels(limit=limit)
    return api_response(data=reels, meta={"count": len(reels)})

@reels_api_bp.route('/<reel_id>', methods=['GET'])
def get_single_reel(reel_id):
    reel = get_reel(reel_id)
    if not reel:
        return api_error("Reel not found", code="not_found", status=404)
    return api_response(data=reel)

@reels_api_bp.route('/upload', methods=['POST'])
@api_login_required
def upload_reel_api():
    file = request.files.get('video')
    thumb = request.files.get('thumbnail')
    caption = request.form.get('caption', '')
    
    reel_id, error = create_reel(g.api_user['id'], caption, file, thumb)
    if error:
        return api_error(error, code="upload_failed")
        
    return api_response(data={"id": reel_id}, status=201)

@reels_api_bp.route('/<reel_id>/view', methods=['POST'])
def view_reel_api(reel_id):
    record_reel_view(reel_id)
    return api_response(data={"success": True})

@reels_api_bp.route('/<reel_id>/like', methods=['POST'])
@api_login_required
def like_reel_api(reel_id):
    like_reel(reel_id, g.api_user['id'])
    return api_response(data={"success": True})
