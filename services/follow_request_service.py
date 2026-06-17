"""Follow Request Service — handles private follow logic and approvals."""

import uuid
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query
from services.relationship_privacy_service import are_friends, is_follower
from services.logging_service import log_info, log_error
from services.socketio_service import emit_to_profile
from services.notification_engine import create_notification

def get_follow_status(viewer_id, target_id):
    """
    Returns the relationship status between two profiles:
    - 'self': viewer is target
    - 'following': viewer follows target
    - 'request_pending': viewer sent a request
    - 'request_received': target sent a request to viewer
    - 'none': no relationship
    """
    if not viewer_id or not target_id:
        return "none"
        
    if str(viewer_id) == str(target_id):
        return "self"

    if is_follower(viewer_id, target_id):
        return "following"
        
    # Check pending requests
    rows = fast_query(
        "SELECT id, requester_profile_id FROM chain_follow_requests "
        "WHERE ((requester_profile_id = %s AND target_profile_id = %s) "
        "OR (requester_profile_id = %s AND target_profile_id = %s)) "
        "AND status = 'pending' LIMIT 2",
        (viewer_id, target_id, target_id, viewer_id),
        default=[]
    )
    
    for row in rows:
        if str(row["requester_profile_id"]) == str(viewer_id):
            return "request_pending"
        else:
            return "request_received"
            
    return "none"

def cancel_follow_request(request_id, requester_profile_id):
    """Cancels an outgoing follow request."""
    try:
        write_query(
            "DELETE FROM chain_follow_requests WHERE id = %s AND requester_profile_id = %s AND status = 'pending'",
            (request_id, requester_profile_id)
        )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def is_private_follow_required(viewer_id, target_profile):
    """True if the target profile requires a follow request to see followers-only content."""
    if not target_profile:
        return False
    
    owner_id = target_profile.get("id")
    if not owner_id:
        return False
        
    if viewer_id and str(viewer_id) == str(owner_id):
        return False
        
    # Check friends first (friends always bypass)
    if viewer_id and are_friends(viewer_id, owner_id):
        return False
        
    visibility = target_profile.get("profile_visibility", "public")
    if visibility == "private":
        return True
    return False

def send_follow_request(requester_id, target_id, message=None):
    """Sends a follow request or follows directly if public."""
    from services.profile_service import get_profile_by_id
    target_profile = get_profile_by_id(target_id)
    if not target_profile:
        return {"ok": False, "error": "profile_not_found"}
        
    if not is_private_follow_required(requester_id, target_profile):
        # Direct follow
        from services.engagement_service import follow_profile
        follow_profile(requester_id, target_id)
        return {"ok": True, "status": "following"}
        
    # Private profile -> Request
    try:
        req_id = str(uuid.uuid4())
        write_query(
            "INSERT INTO chain_follow_requests (id, requester_profile_id, target_profile_id, status, message) "
            "VALUES (%s, %s, %s, 'pending', %s) "
            "ON CONFLICT (requester_profile_id, target_profile_id) DO UPDATE SET status = 'pending', updated_at = now()",
            (req_id, requester_id, target_id, message)
        )
        
        requester = get_profile_by_id(requester_id)
        requester_name = requester.get("display_name") or requester.get("username") or "Someone"
        
        create_notification(
            recipient_profile_id=target_id,
            actor_profile_id=requester_id,
            event_type="follow_request",
            title="New Follow Request",
            body=f"{requester_name} wants to follow you.",
            action_url=f"/profile/@{requester.get('username')}",
            entity_type="follow_request",
            entity_id=req_id
        )
        
        emit_to_profile(target_id, "follow_request:new", {
            "requester_id": requester_id,
            "requester_name": requester_name,
            "request_id": req_id
        })
        
        return {"ok": True, "status": "request_pending"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def approve_follow_request(request_id, target_profile_id):
    """Approves a follow request."""
    req = fast_query(
        "SELECT * FROM chain_follow_requests WHERE id = %s AND status = 'pending' LIMIT 1",
        (request_id,), default=[]
    )
    if not req:
        return {"ok": False, "error": "request_not_found"}

    if str(req[0]["target_profile_id"]) != str(target_profile_id):
        return {"ok": False, "error": "not_authorized"}

    requester_id = req[0]["requester_profile_id"]

    try:
        write_query(
            "UPDATE chain_follow_requests SET status = 'approved', responded_at = now(), updated_at = now() WHERE id = %s",
            (request_id,)
        )

        # 2. Add as follower
        from services.engagement_service import follow_profile
        follow_profile(requester_id, target_profile_id, toggle=False)
        
        # Notify requester
        target_p = fast_query("SELECT username, display_name FROM chain_profiles WHERE id = %s", (target_profile_id,), default=[])
        target_name = target_p[0].get("display_name") or target_p[0].get("username") if target_p else "Someone"
        
        create_notification(
            recipient_profile_id=requester_id,
            actor_profile_id=target_profile_id,
            event_type="follow_request_approved",
            title="Follow Request Approved",
            body=f"{target_name} approved your follow request.",
            action_url=f"/profile/@{target_p[0].get('username') if target_p else ''}",
            entity_type="follow_approval",
            entity_id=request_id
        )
        
        emit_to_profile(requester_id, "follow_request:approved", {
            "target_id": target_profile_id,
            "target_name": target_name
        })
        
        return {"ok": True, "status": "following"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def decline_follow_request(request_id, target_profile_id):
    """Declines a follow request."""
    try:
        write_query(
            "UPDATE chain_follow_requests SET status = 'declined', responded_at = now(), updated_at = now() "
            "WHERE id = %s AND target_profile_id = %s",
            (request_id, target_profile_id)
        )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def list_incoming_follow_requests(profile_id):
    """Lists pending incoming follow requests."""
    rows = fast_query(
        "SELECT fr.*, cp.username, cp.display_name, cp.avatar_url "
        "FROM chain_follow_requests fr "
        "JOIN chain_profiles cp ON fr.requester_profile_id = cp.id "
        "WHERE fr.target_profile_id = %s AND fr.status = 'pending' "
        "ORDER BY fr.created_at DESC",
        (profile_id,), default=[]
    )
    return rows

def list_outgoing_follow_requests(profile_id):
    """Lists pending outgoing follow requests."""
    rows = fast_query(
        "SELECT fr.*, cp.username, cp.display_name, cp.avatar_url "
        "FROM chain_follow_requests fr "
        "JOIN chain_profiles cp ON fr.target_profile_id = cp.id "
        "WHERE fr.requester_profile_id = %s AND fr.status = 'pending' "
        "ORDER BY fr.created_at DESC",
        (profile_id,), default=[]
    )
    return rows
