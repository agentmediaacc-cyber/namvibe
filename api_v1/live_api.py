from flask import Blueprint, request, g
from services.api_auth_service import api_response, api_error, api_login_required, optional_api_user
from services.live_service import get_live_rooms_public, get_room

live_api_bp = Blueprint('live_api', __name__, url_prefix='/live')

@live_api_bp.route('/rooms', methods=['GET'])
@optional_api_user
def get_live_rooms_api():
    limit = int(request.args.get('limit', 10))
    rooms = get_live_rooms_public(limit=limit)
    return api_response(data=rooms, meta={"count": len(rooms)})

@live_api_bp.route('/rooms/<room_id>', methods=['GET'])
def get_single_room_api(room_id):
    room = get_room(room_id)
    if not room:
        return api_error("Room not found", code="not_found", status=404)
    return api_response(data=room)
