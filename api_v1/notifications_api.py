from flask import Blueprint, request, g
from services.api_auth_service import api_response, api_login_required
from services.notification_engine import list_notifications, unread_count, mark_read, mark_all_read

notifications_api_bp = Blueprint('notifications_api', __name__, url_prefix='/notifications')

@notifications_api_bp.route('/', methods=['GET'])
@api_login_required
def get_notifications_api():
    limit = int(request.args.get('limit', 30))
    notifs = list_notifications(g.api_user['id'], limit=limit)
    return api_response(data=notifs, meta={"count": len(notifs)})

@notifications_api_bp.route('/unread-count', methods=['GET'])
@api_login_required
def get_unread_count_api():
    count = unread_count(g.api_user['id'])
    return api_response(data={"count": count})

@notifications_api_bp.route('/<notif_id>/read', methods=['POST'])
@api_login_required
def mark_read_api(notif_id):
    mark_read(notif_id, g.api_user['id'])
    return api_response(data={"success": True})

@notifications_api_bp.route('/read-all', methods=['POST'])
@api_login_required
def mark_all_read_api():
    mark_all_read(g.api_user['id'])
    return api_response(data={"success": True})
