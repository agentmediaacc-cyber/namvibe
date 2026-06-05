from flask import Blueprint, request, g
from services.api_auth_service import api_response, optional_api_user
from services.feed_engine import build_feed

feed_api_bp = Blueprint('feed_api', __name__, url_prefix='/feed')

@feed_api_bp.route('/', methods=['GET'])
@optional_api_user
def get_feed():
    limit = int(request.args.get('limit', 20))
    offset = int(request.args.get('offset', 0))
    profile_id = g.api_user['id'] if g.api_user else None
    
    feed = build_feed(profile_id=profile_id, limit=limit)
    
    return api_response(
        data=feed,
        meta={"limit": limit, "offset": offset, "count": len(feed)}
    )
