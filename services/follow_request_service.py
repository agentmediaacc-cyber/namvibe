"""Follow Request Service — handles private follow logic and approvals."""

import uuid
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query
from services.relationship_privacy_service import are_friends, is_follower, is_blocked_any
from services.engagement_service import follow_profile, is_following
from services.notification_engine import create_notification
from services.socketio_service import emit_to_profile

def is_private_follow_required(viewer_id, target_profile):
    """True if the target profile requires a follow request to see followers-only content."""
    if not target_profile:
        return False
    
    owner_id = target_profile.get("id")
    if not owner_id:
        return False
        
    if viewer_id and str(viewer_id) == str(owner_id):
        return False
        
    # Check if already following or friends
    if viewer_id:
        if is_following(viewer_id, owner_id):
            return False
        if are_friends(viewer_id, owner_id):
            return False
            
    visibility = target_profile.get("profile_visibility", "public")
    # If private or followers_only, we might need a request if not already friends/followers
    # For simplicity, if profile_visibility is 'private', it always requires approval.
    if visibility == "private":
        return True
        
    # If account kind is 'person' and it's not public, we might want to default to private-style follows
    # but let's stick to explicit profile_visibility for now.
    return False

def get_follow_status(viewer_id, target_id):
    """Returns the current follow relationship status."""
    if not viewer_id or not target_id:
        return "none"
        
    if str(viewer_id) == str(target_id):
        return "self"
        
    if is_blocked_any(viewer_id, target_id):
        return "blocked"
        
    if is_following(viewer_id, target_id):
        return "following"
        
    # Check for pending request
    pending = fast_query(
        "SELECT id, requester_profile_id FROM chain_follow_requests WHERE "
        "((requester_profile_id = %s AND target_profile_id = %s) OR "
        "(requester_profile_id = %s AND target_profile_id = %s)) "
        "AND status = 'pending' LIMIT 1",
        (viewer_id, target_id, target_id, viewer_id),
        default=[]
    )
    
    if pending:
        if str(pending[0]["requester_profile_id"]) == str(viewer_id):
            return "request_pending"
        else:
            return "request_received"
            
    return "none"

def send_follow_request(requester_id, target_id, message=None):
    """Sends a follow request or follows immediately if allowed."""
    if str(requester_id) == str(target_id):
        return {"ok": False, "error": "cannot_follow_self"}
        
    if is_blocked_any(requester_id, target_id):
        return {"ok": False, "error": "blocked"}
        
    if is_following(requester_id, target_id):
        return {"ok": True, "status": "following", "message": "Already following"}
        
    from services.profile_service import get_profile_by_id
    target_profile = get_profile_by_id(target_id)
    if not target_profile:
        return {"ok": False, "error": "profile_not_found"}
        
    if not is_private_follow_required(requester_id, target_profile):
        # Direct follow
        follow_profile(requester_id, target_id)
        return {"ok": True, "status": "following"}
        
    # Private follow request
    try:
        req_id = str(uuid.uuid4())
        write_query(
            "INSERT INTO chain_follow_requests (id, requester_profile_id, target_profile_id, status, message) "
            "VALUES (%s, %s, %s, 'pending', %s) "
            "ON CONFLICT (requester_profile_id, target_profile_id) DO UPDATE SET "
            "status = 'pending', message = %s, updated_at = now()",
            (req_id, requester_id, target_id, message, message)
        )
        
        # Notify target
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
        
        # Add to chain_follows
        follow_profile(requester_id, target_profile_id)
        
        # Notify requester
        target_p = fast_query("SELECT username, display_name FROM chain_profiles WHERE id = %s", (target_profile_id,), default=[])
        target_name = target_p[0].get("display_name") or target_p[0].get("username") if target_p else "Someone"
        
        create_notification(
            recipient_profile_id=requester_id,
            actor_profile_id=target_profile_id,
            event_type="follow_request_approved",
            title="Follow Request Approved",
            body=f"{target_name} approved your follow request.",
            action_url=f"/profile/@{target_p[0].get('username') if target_p else ''}"
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
    req = fast_query(
        "SELECT * FROM chain_follow_requests WHERE id = %s AND status = 'pending' LIMIT 1",
        (request_id,), default=[]
    )
    if not req:
        return {"ok": False, "error": "request_not_found"}
        
    if str(req[0]["target_profile_id"]) != str(target_profile_id):
        return {"ok": False, "error": "not_authorized"}
        
    try:
        write_query(
            "UPDATE chain_follow_requests SET status = 'declined', responded_at = now(), updated_at = now() WHERE id = %s",
            (request_id,)
        )
        
        requester_id = req[0]["requester_profile_id"]
        target_p = fast_query("SELECT username, display_name FROM chain_profiles WHERE id = %s", (target_profile_id,), default=[])
        target_name = target_p[0].get("display_name") or target_p[0].get("username") if target_p else "Someone"
        
        create_notification(
            recipient_profile_id=requester_id,
            actor_profile_id=target_profile_id,
            event_type="follow_request_declined",
            title="Follow Request Declined",
            body=f"{target_name} declined your follow request.",
            action_url=f"/profile/@{target_p[0].get('username') if target_p else ''}"
        )
        
        return {"ok": True, "status": "none"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def cancel_follow_request(request_id, requester_profile_id):
    """Cancels an outgoing follow request."""
    req = fast_query(
        "SELECT * FROM chain_follow_requests WHERE id = %s AND status = 'pending' LIMIT 1",
        (request_id,), default=[]
    )
    if not req:
        return {"ok": False, "error": "request_not_found"}
        
    if str(req[0]["requester_profile_id"]) != str(requester_profile_id):
        return {"ok": False, "error": "not_authorized"}
        
    try:
        write_query(
            "UPDATE chain_follow_requests SET status = 'cancelled', updated_at = now() WHERE id = %s",
            (request_id,)
        )
        return {"ok": True, "status": "none"}
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
