"""
Friendship Service — Helper functions for the NamVibe friendship system.
"""
from services.neon_service import fast_query, write_query
from services.friend_service import send_friend_request as _send_fr, accept_friend_request as _accept_fr, decline_friend_request as _decline_fr, cancel_friend_request as _cancel_fr
from services.relationship_cache_service import get_relationship_state, invalidate_relationship_state
from services.notification_engine import create_notification
from services.socketio_service import emit_to_profile
from services.redis_service import cache_delete


def get_current_profile_id():
    from flask import session
    return session.get("profile_id") or session.get("auth_user_id")


def normalize_pair(a, b):
    return (a, b) if a < b else (b, a)


def are_friends(profile_id, other_id):
    if not profile_id or not other_id:
        return False
    state = get_relationship_state(profile_id, other_id)
    return state.get("is_friend", False)


def get_friendship_status(profile_id, other_id):
    if not profile_id or not other_id:
        return {"status": "unknown", "friendship": None}
    if profile_id == other_id:
        return {"status": "self", "friendship": None}
    state = get_relationship_state(profile_id, other_id)
    if state.get("is_friend"):
        return {"status": "friends", "friendship": "friends"}
    if state.get("friend_request_sent"):
        return {"status": "pending_sent", "friendship": "pending"}
    if state.get("friend_request_received"):
        return {"status": "pending_received", "friendship": "pending"}
    return {"status": "none", "friendship": None}


def send_friend_request(sender_id, receiver_id, message=None):
    result = _send_fr(sender_id, receiver_id)
    if result.get("success"):
        sender = fast_query("SELECT username, display_name FROM chain_profiles WHERE id = %s", [sender_id])
        sender_name = sender[0].get('display_name') or sender[0].get('username', 'Someone') if sender else 'Someone'
        create_notification(
            recipient_profile_id=receiver_id,
            event_type="friend_request",
            title="New Friend Request",
            body=f"{sender_name} sent you a friend request.",
            actor_profile_id=sender_id,
            entity_type="friend_request",
            entity_id=result.get("request_id"),
            action_url="/social/friend-requests"
        )
        emit_to_profile(receiver_id, "friend_request:new", {
            "request_id": result.get("request_id"),
            "sender_id": sender_id,
            "sender_name": sender_name,
        })
    return result


def accept_friend_request(request_id, receiver_id):
    result = _accept_fr(receiver_id, request_id)
    if result.get("success"):
        req = fast_query("SELECT sender_profile_id, recipient_profile_id FROM chain_friend_requests WHERE id = %s", [request_id])
        if req:
            sender_id = req[0]['sender_profile_id']
            accepter = fast_query("SELECT username, display_name FROM chain_profiles WHERE id = %s", [receiver_id])
            accepter_name = accepter[0].get('display_name') or accepter[0].get('username', 'Someone') if accepter else 'Someone'
            create_notification(
                recipient_profile_id=sender_id,
                event_type="friend_request_accepted",
                title="Friend Request Accepted",
                body=f"{accepter_name} accepted your friend request. You are now friends!",
                actor_profile_id=receiver_id,
                entity_type="friend_request",
                entity_id=request_id,
                action_url=f"/profile/@{accepter[0].get('username') if accepter else ''}"
            )
            emit_to_profile(sender_id, "friend_request:accepted", {
                "request_id": request_id,
                "accepter_id": receiver_id,
                "accepter_name": accepter_name,
            })
    return result


def decline_friend_request(request_id, receiver_id):
    result = _decline_fr(receiver_id, request_id)
    if result.get("success"):
        req = fast_query("SELECT sender_profile_id FROM chain_friend_requests WHERE id = %s", [request_id])
        if req:
            sender_id = req[0]['sender_profile_id']
            decliner = fast_query("SELECT username, display_name FROM chain_profiles WHERE id = %s", [receiver_id])
            decliner_name = decliner[0].get('display_name') or decliner[0].get('username', 'Someone') if decliner else 'Someone'
            create_notification(
                recipient_profile_id=sender_id,
                event_type="friend_request_declined",
                title="Friend Request Declined",
                body=f"{decliner_name} declined your friend request.",
                actor_profile_id=receiver_id,
                entity_type="friend_request",
                entity_id=request_id,
                action_url=f"/profile/@{decliner[0].get('username') if decliner else ''}"
            )
    return result


def cancel_friend_request(request_id, sender_id):
    return _cancel_fr(sender_id, request_id)


def require_friendship_or_403(current_id, other_id, feature_name):
    if not current_id or not other_id:
        return None, False
    if current_id == other_id:
        return None, True
    if not are_friends(current_id, other_id):
        return None, False
    return None, True
