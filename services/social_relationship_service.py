"""Unified social relationship operations for follows and friendships."""

from services.neon_service import fast_query, write_query
from services.blocking_service import is_blocked_any
from services.profile_service import get_profile_by_id
from services.relationship_cache_service import invalidate_relationship_state
from services.follow_request_service import is_private_follow_required
from services.notification_engine import create_notification


def _ok(state="none", message="OK", **extra):
    return {"ok": True, "state": state, "message": message, **extra}


def _err(message, state="none", status=400, **extra):
    return {"ok": False, "state": state, "message": message, "status": status, **extra}


def _same(a, b):
    return str(a) == str(b)


def _ordered_pair(a, b):
    a, b = str(a), str(b)
    return (a, b) if a < b else (b, a)


def _load_relationship_state(viewer_id, target_id):
    """Single CTE returning all relationship state between two profiles."""
    rows = fast_query(
        """
        WITH
          v AS (SELECT %s::uuid AS id),
          t AS (SELECT %s::uuid AS id)
        SELECT
          (SELECT 1 FROM chain_blocks b, v, t
           WHERE ((b.blocker_profile_id=v.id AND b.blocked_profile_id=t.id)
                OR (b.blocker_profile_id=t.id AND b.blocked_profile_id=v.id))
             AND b.deleted_at IS NULL LIMIT 1) AS blocked,
          (SELECT f.id FROM chain_friends f, v, t
           WHERE ((f.profile_id_1=v.id AND f.profile_id_2=t.id)
                OR (f.profile_id_1=t.id AND f.profile_id_2=v.id))
             AND f.status='friend' AND f.deleted_at IS NULL LIMIT 1) AS friend_id,
          (SELECT fr.id FROM chain_friend_requests fr, v, t
           WHERE fr.sender_profile_id=v.id AND fr.recipient_profile_id=t.id
             AND fr.status='pending' LIMIT 1) AS fr_sent_id,
          (SELECT fr.id FROM chain_friend_requests fr, v, t
           WHERE fr.sender_profile_id=t.id AND fr.recipient_profile_id=v.id
             AND fr.status='pending' LIMIT 1) AS fr_received_id,
          (SELECT f2.id FROM chain_follows f2, v, t
           WHERE f2.follower_profile_id=v.id AND f2.following_profile_id=t.id
             AND f2.deleted_at IS NULL LIMIT 1) AS follow_id,
          (SELECT fr2.id FROM chain_follow_requests fr2, v, t
           WHERE fr2.requester_profile_id=v.id AND fr2.target_profile_id=t.id
             AND fr2.status='pending' LIMIT 1) AS fol_req_sent_id,
          (SELECT fr2.id FROM chain_follow_requests fr2, v, t
           WHERE fr2.requester_profile_id=t.id AND fr2.target_profile_id=v.id
             AND fr2.status='pending' LIMIT 1) AS fol_req_received_id
        FROM v, t
        """,
        (viewer_id, target_id), default=[]
    )
    return rows[0] if rows else {}


def _active_follow(viewer_id, target_id):
    rows = fast_query(
        "SELECT id FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s AND deleted_at IS NULL LIMIT 1",
        (viewer_id, target_id), default=[]
    )
    return rows[0] if rows else None


def _pending_follow_request(requester_id, target_id):
    rows = fast_query(
        "SELECT id FROM chain_follow_requests WHERE requester_profile_id = %s AND target_profile_id = %s AND status = 'pending' LIMIT 1",
        (requester_id, target_id), default=[]
    )
    return rows[0] if rows else None


def _active_friendship(a, b):
    p1, p2 = _ordered_pair(a, b)
    rows = fast_query(
        "SELECT id FROM chain_friends WHERE profile_id_1 = %s AND profile_id_2 = %s AND status = 'friend' AND deleted_at IS NULL LIMIT 1",
        (p1, p2), default=[]
    )
    return rows[0] if rows else None


def _pending_friend_request(sender_id, recipient_id):
    rows = fast_query(
        "SELECT id FROM chain_friend_requests WHERE sender_profile_id = %s AND recipient_profile_id = %s AND status = 'pending' LIMIT 1",
        (sender_id, recipient_id), default=[]
    )
    return rows[0] if rows else None


def _invalidate(a, b):
    invalidate_relationship_state(a, b)
    invalidate_relationship_state(b, a)


def _refresh_follow_counts(follower_id, following_id):
    rows = fast_query(
        """
        SELECT
          COUNT(*) FILTER (WHERE following_profile_id = %s) AS followers_count,
          COUNT(*) FILTER (WHERE follower_profile_id = %s) AS following_count
        FROM chain_follows
        WHERE (following_profile_id = %s OR follower_profile_id = %s)
          AND deleted_at IS NULL
        """,
        (following_id, follower_id, following_id, follower_id), default=[{"followers_count": 0, "following_count": 0}]
    )
    followers_count = rows[0]["followers_count"] if rows else 0
    following_count = rows[0]["following_count"] if rows else 0
    write_query("UPDATE chain_profiles SET followers_count = %s WHERE id = %s", (followers_count, following_id))
    write_query("UPDATE chain_profiles SET following_count = %s WHERE id = %s", (following_count, follower_id))


def relationship_summary(viewer_id, target_id=None):
    if target_id:
        return _relationship_for(viewer_id, target_id)
    incoming = list_friend_requests(viewer_id).get("incoming", [])
    outgoing = list_friend_requests(viewer_id).get("outgoing", [])
    friends = list_friends(viewer_id).get("friends", [])
    return _ok(
        state="summary",
        message="Relationship summary loaded.",
        incoming_friend_requests=incoming,
        outgoing_friend_requests=outgoing,
        friends=friends,
    )


def _relationship_for(viewer_id, target_id):
    if not viewer_id:
        return _err("Authentication required.", status=401)
    if _same(viewer_id, target_id):
        return _ok("self", "This is your profile.")
    state = _load_relationship_state(viewer_id, target_id)
    if state.get("blocked"):
        return _ok("blocked", "This relationship is blocked.")
    if state.get("friend_id"):
        return _ok("friends", "You are friends.")
    if state.get("fr_sent_id"):
        return _ok("friend_requested", "Friend request sent.", request_id=state["fr_sent_id"])
    if state.get("fr_received_id"):
        return _ok("friend_request_received", "Friend request received.", request_id=state["fr_received_id"])
    if state.get("follow_id"):
        return _ok("following", "You are following this profile.")
    if state.get("fol_req_sent_id"):
        return _ok("requested", "Follow request sent.", request_id=state["fol_req_sent_id"])
    if state.get("fol_req_received_id"):
        return _ok("follow_request_received", "Follow request received.", request_id=state["fol_req_received_id"])
    return _ok("none", "No relationship.")


def follow(viewer_id, target_id):
    if not viewer_id:
        return _err("Authentication required.", status=401)
    if _same(viewer_id, target_id):
        return _err("You cannot follow yourself.", state="self")
    target = get_profile_by_id(target_id)
    if not target:
        return _err("Profile not found.", status=404)

    state = _load_relationship_state(viewer_id, target_id)
    if state.get("blocked"):
        return _err("Blocked users cannot follow each other.", state="blocked", status=403)
    if state.get("follow_id"):
        return _ok("following", "Already following.")

    visibility = target.get("profile_visibility", "public")
    is_private = visibility == "private" and not state.get("friend_id")

    if is_private:
        if state.get("fol_req_sent_id"):
            return _ok("requested", "Follow request already sent.", request_id=state["fol_req_sent_id"])
        rows = write_query(
            """
            INSERT INTO chain_follow_requests (requester_profile_id, target_profile_id, status, created_at)
            VALUES (%s, %s, 'pending', now())
            RETURNING id
            """,
            (viewer_id, target_id)
        )
        _invalidate(viewer_id, target_id)
        return _ok("requested", "Follow request sent.", request_id=rows[0]["id"] if rows else None)

    restored = write_query(
        """
        UPDATE chain_follows SET deleted_at = NULL, created_at = now()
        WHERE follower_profile_id = %s AND following_profile_id = %s AND deleted_at IS NOT NULL
        RETURNING id
        """,
        (viewer_id, target_id)
    )
    if not restored:
        write_query(
            "INSERT INTO chain_follows (follower_profile_id, following_profile_id, created_at) VALUES (%s, %s, now())",
            (viewer_id, target_id)
        )
    _refresh_follow_counts(viewer_id, target_id)
    _invalidate(viewer_id, target_id)
    return _ok("following", "Now following.")


def unfollow(viewer_id, target_id):
    if not viewer_id:
        return _err("Authentication required.", status=401)
    if _same(viewer_id, target_id):
        return _err("You cannot unfollow yourself.", state="self")
    write_query(
        "UPDATE chain_follows SET deleted_at = now() WHERE follower_profile_id = %s AND following_profile_id = %s AND deleted_at IS NULL",
        (viewer_id, target_id)
    )
    write_query(
        "UPDATE chain_follow_requests SET status = 'cancelled', responded_at = now() WHERE requester_profile_id = %s AND target_profile_id = %s AND status = 'pending'",
        (viewer_id, target_id)
    )
    _refresh_follow_counts(viewer_id, target_id)
    _invalidate(viewer_id, target_id)
    return _ok("none", "Unfollowed.")


def send_friend_request(viewer_id, target_id):
    if not viewer_id:
        return _err("Authentication required.", status=401)
    if _same(viewer_id, target_id):
        return _err("You cannot send a friend request to yourself.", state="self")
    if not get_profile_by_id(target_id):
        return _err("Profile not found.", status=404)

    state = _load_relationship_state(viewer_id, target_id)
    if state.get("blocked"):
        return _err("Blocked users cannot send friend requests.", state="blocked", status=403)
    if state.get("friend_id"):
        return _ok("friends", "Already friends.")

    if state.get("fr_received_id"):
        return accept_friend_request(viewer_id, state["fr_received_id"])

    if state.get("fr_sent_id"):
        return _ok("friend_requested", "Friend request already sent.", request_id=state["fr_sent_id"])

    rows = write_query(
        """
        INSERT INTO chain_friend_requests (sender_profile_id, recipient_profile_id, status, created_at)
        VALUES (%s, %s, 'pending', now())
        RETURNING id
        """,
        (viewer_id, target_id)
    )
    _invalidate(viewer_id, target_id)
    request_id = rows[0]["id"] if rows else None
    # Notify recipient
    try:
        _prof = fast_query("SELECT username FROM chain_profiles WHERE id = %s", (viewer_id,), default=[])
        _uname = _prof[0]["username"] if _prof else "Someone"
        create_notification(
            recipient_profile_id=target_id,
            event_type="friend_request",
            title="New Friend Request",
            body=f"{_uname} sent you a friend request.",
            actor_profile_id=viewer_id,
            entity_type="friend_request",
            entity_id=request_id,
            action_url="/social/friend-requests",
        )
    except Exception:
        pass
    return _ok("friend_requested", "Friend request sent.", request_id=request_id)


def accept_friend_request(viewer_id, request_id):
    rows = fast_query(
        """
        SELECT id, sender_profile_id, recipient_profile_id
        FROM chain_friend_requests
        WHERE id = %s AND status = 'pending'
        LIMIT 1
        """,
        (request_id,), default=[]
    )
    if not rows:
        return _err("Friend request not found.", status=404)
    req = rows[0]
    if not _same(viewer_id, req["recipient_profile_id"]):
        return _err("You cannot accept this friend request.", status=403)
    if is_blocked_any(req["sender_profile_id"], req["recipient_profile_id"]):
        return _err("Blocked users cannot become friends.", state="blocked", status=403)

    p1, p2 = _ordered_pair(req["sender_profile_id"], req["recipient_profile_id"])
    write_query(
        "UPDATE chain_friend_requests SET status = 'accepted', responded_at = now() WHERE id = %s",
        (request_id,)
    )
    restored = write_query(
        """
        UPDATE chain_friends SET deleted_at = NULL, status = 'friend', created_at = now()
        WHERE profile_id_1 = %s AND profile_id_2 = %s AND deleted_at IS NOT NULL
        RETURNING id
        """,
        (p1, p2)
    )
    if not restored:
        write_query(
            "INSERT INTO chain_friends (profile_id_1, profile_id_2, status, created_at) VALUES (%s, %s, 'friend', now()) ON CONFLICT DO NOTHING",
            (p1, p2)
        )
    write_query(
        """
        UPDATE chain_friend_requests SET status = 'accepted', responded_at = now()
        WHERE sender_profile_id = %s AND recipient_profile_id = %s AND status = 'pending'
        """,
        (req["recipient_profile_id"], req["sender_profile_id"])
    )
    _invalidate(req["sender_profile_id"], req["recipient_profile_id"])
    # Notify the original sender
    try:
        _prof = fast_query("SELECT username FROM chain_profiles WHERE id = %s", (req["recipient_profile_id"],), default=[])
        _uname = _prof[0]["username"] if _prof else "Someone"
        create_notification(
            recipient_profile_id=req["sender_profile_id"],
            event_type="friend_accepted",
            title="Friend Request Accepted",
            body=f"{_uname} accepted your friend request. You are now friends!",
            actor_profile_id=req["recipient_profile_id"],
            entity_type="friend_request",
            entity_id=request_id,
            action_url=f"/profile/@{_uname}",
        )
    except Exception:
        pass
    return _ok("friends", "Friend request accepted.", request_id=request_id)


def decline_friend_request(viewer_id, request_id):
    res = write_query(
        """
        UPDATE chain_friend_requests SET status = 'declined', responded_at = now()
        WHERE id = %s AND recipient_profile_id = %s AND status = 'pending'
        """,
        (request_id, viewer_id)
    )
    if not res or res.get("rowcount", 0) < 1:
        return _err("Friend request not found.", status=404)
    return _ok("none", "Friend request declined.", request_id=request_id)


def cancel_friend_request(viewer_id, request_id):
    rows = fast_query(
        "SELECT recipient_profile_id FROM chain_friend_requests WHERE id = %s AND sender_profile_id = %s AND status = 'pending' LIMIT 1",
        (request_id, viewer_id), default=[]
    )
    if not rows:
        return _err("Friend request not found.", status=404)
    write_query(
        "UPDATE chain_friend_requests SET status = 'cancelled', responded_at = now() WHERE id = %s",
        (request_id,)
    )
    _invalidate(viewer_id, rows[0]["recipient_profile_id"])
    return _ok("none", "Friend request cancelled.", request_id=request_id)


def unfriend(viewer_id, target_id):
    p1, p2 = _ordered_pair(viewer_id, target_id)
    write_query(
        "UPDATE chain_friends SET deleted_at = now() WHERE profile_id_1 = %s AND profile_id_2 = %s AND deleted_at IS NULL",
        (p1, p2)
    )
    _invalidate(viewer_id, target_id)
    return _ok("none", "Unfriended.")


def list_friend_requests(viewer_id):
    incoming = fast_query(
        """
        SELECT r.id, r.sender_profile_id, r.recipient_profile_id, r.status, r.created_at,
               p.username, p.display_name, p.full_name, p.avatar_url, p.is_verified
        FROM chain_friend_requests r
        JOIN chain_profiles p ON p.id = r.sender_profile_id
        WHERE r.recipient_profile_id = %s AND r.status = 'pending' AND p.deleted_at IS NULL
        ORDER BY r.created_at DESC
        LIMIT 100
        """,
        (viewer_id,), default=[]
    )
    outgoing = fast_query(
        """
        SELECT r.id, r.sender_profile_id, r.recipient_profile_id, r.status, r.created_at,
               p.username, p.display_name, p.full_name, p.avatar_url, p.is_verified
        FROM chain_friend_requests r
        JOIN chain_profiles p ON p.id = r.recipient_profile_id
        WHERE r.sender_profile_id = %s AND r.status = 'pending' AND p.deleted_at IS NULL
        ORDER BY r.created_at DESC
        LIMIT 100
        """,
        (viewer_id,), default=[]
    )
    return _ok("none", "Friend requests loaded.", incoming=incoming, outgoing=outgoing)


def list_friends(viewer_id):
    friends = fast_query(
        """
        SELECT f.id AS friendship_id, f.created_at,
               p.id, p.username, p.display_name, p.full_name, p.avatar_url, p.is_verified
        FROM chain_friends f
        JOIN chain_profiles p ON p.id = CASE WHEN f.profile_id_1 = %s THEN f.profile_id_2 ELSE f.profile_id_1 END
        WHERE (f.profile_id_1 = %s OR f.profile_id_2 = %s)
          AND f.status = 'friend'
          AND f.deleted_at IS NULL
          AND p.deleted_at IS NULL
        ORDER BY f.created_at DESC
        LIMIT 100
        """,
        (viewer_id, viewer_id, viewer_id), default=[]
    )
    return _ok("friends", "Friends loaded.", friends=friends)
