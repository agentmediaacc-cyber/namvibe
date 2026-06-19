"""
Friend Service — Core friendship system for NamVibe.
Handles friend requests, friend relationships, and mutual friend calculations.
"""
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query
from services.logging_service import log_info, log_error
from services.notification_engine import create_notification
from services.redis_service import cache_get, cache_set, cache_delete

def _get_ordered_pair(id1, id2):
    return (id1, id2) if id1 < id2 else (id2, id1)

def send_friend_request(sender_id, recipient_id):
    """Sends a friend request from sender_id to recipient_id."""
    if sender_id == recipient_id:
        return {"success": False, "error": "You cannot send a friend request to yourself."}
    
    # Check if they are already friends
    if are_friends(sender_id, recipient_id):
        return {"success": False, "error": "You are already friends."}
    
    # Check for existing request
    existing = fast_query(
        "SELECT id, status FROM chain_friend_requests WHERE sender_profile_id = %s AND recipient_profile_id = %s",
        [sender_id, recipient_id]
    )
    if existing:
        if existing[0]['status'] == 'pending':
            return {"success": False, "error": "Friend request already sent."}
        # If previously declined or cancelled, we can reactivate or create new
        write_query(
            "UPDATE chain_friend_requests SET status = 'pending', updated_at = now() WHERE id = %s",
            [existing[0]['id']]
        )
        _notify_friend_request(sender_id, recipient_id)
        return {"success": True, "request_id": existing[0]['id']}

    # Check if recipient already sent a request to sender
    recip_sent = fast_query(
        "SELECT id, status FROM chain_friend_requests WHERE sender_profile_id = %s AND recipient_profile_id = %s",
        [recipient_id, sender_id]
    )
    if recip_sent and recip_sent[0]['status'] == 'pending':
        # Automatically accept and become friends
        return accept_friend_request(sender_id, recip_sent[0]['id'])

    try:
        res = write_query(
            "INSERT INTO chain_friend_requests (sender_profile_id, recipient_profile_id, status) VALUES (%s, %s, 'pending') RETURNING id",
            [sender_id, recipient_id]
        )
        if res:
            _notify_friend_request(sender_id, recipient_id)
            return {"success": True, "request_id": res[0]['id']}
        return {"success": False, "error": "Failed to send friend request."}
    except Exception as e:
        log_error("send_friend_request_failed", error=str(e))
        return {"success": False, "error": str(e)}

def _notify_friend_request(sender_id, recipient_id):
    sender = fast_query("SELECT username FROM chain_profiles WHERE id = %s", [sender_id])
    username = sender[0]['username'] if sender else "Someone"
    create_notification(
        recipient_id,
        "friend_request",
        "New Friend Request",
        f"{username} sent you a friend request.",
        actor_profile_id=sender_id,
        action_url=f"/profile/{sender_id}"
    )

def accept_friend_request(profile_id, request_id):
    """Accepts a friend request."""
    req = fast_query(
        "SELECT id, sender_profile_id, recipient_profile_id, status FROM chain_friend_requests WHERE id = %s AND recipient_profile_id = %s",
        [request_id, profile_id]
    )
    if not req:
        return {"success": False, "error": "Friend request not found."}
    
    req = req[0]
    if req['status'] != 'pending':
        return {"success": False, "error": f"Request is already {req['status']}."}
    
    try:
        # Update request status
        write_query(
            "UPDATE chain_friend_requests SET status = 'accepted', updated_at = now() WHERE id = %s",
            [request_id]
        )
        
        # Become friends
        p1, p2 = _get_ordered_pair(req['sender_profile_id'], req['recipient_profile_id'])
        write_query(
            "INSERT INTO chain_friends (profile_id_1, profile_id_2, status) VALUES (%s, %s, 'friend') ON CONFLICT DO NOTHING",
            [p1, p2]
        )
        
        # Update counters
        write_query("UPDATE chain_profiles SET friends_count = friends_count + 1 WHERE id IN (%s, %s)", [p1, p2])
        
        # Notify sender
        _notify_friend_accepted(req['recipient_profile_id'], req['sender_profile_id'])
        
        # Invalidate caches
        _invalidate_friend_cache(p1, p2)
        
        return {"success": True}
    except Exception as e:
        log_error("accept_friend_request_failed", error=str(e))
        return {"success": False, "error": str(e)}

def _invalidate_friend_cache(p1, p2):
    """Clears all friend-related caches for two profiles."""
    from services.relationship_cache_service import invalidate_relationship_state
    invalidate_relationship_state(p1, p2)
    invalidate_relationship_state(p2, p1)
    for pid in [p1, p2]:
        cache_delete(f"friends_list:{pid}:20:first")
        cache_delete(f"friends:{pid}")
        # Clear mutual friends cache variants
        # In a real system we'd use a pattern, but here we clear specific known keys if possible
        # or just wait for TTL. For this audit, we focus on the primary lists.
        cache_delete(f"mutual_friends:{p1}:{p2}")
        cache_delete(f"mutual_friends:{p2}:{p1}")
        
        # Warmup
        from services.neon_service import _DB_EXECUTOR
        _DB_EXECUTOR.submit(list_friends, pid)

def _notify_friend_accepted(accepter_id, sender_id):
    accepter = fast_query("SELECT username FROM chain_profiles WHERE id = %s", [accepter_id])
    username = accepter[0]['username'] if accepter else "Someone"
    create_notification(
        sender_id,
        "friend_accepted",
        "Friend Request Accepted",
        f"{username} accepted your friend request. You are now friends!",
        actor_profile_id=accepter_id,
        action_url=f"/profile/{accepter_id}"
    )

def decline_friend_request(profile_id, request_id):
    """Declines a friend request."""
    try:
        res = write_query(
            "UPDATE chain_friend_requests SET status = 'declined', updated_at = now() WHERE id = %s AND recipient_profile_id = %s AND status = 'pending'",
            [request_id, profile_id]
        )
        return {"success": True} if res else {"success": False, "error": "Request not found or not pending."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def cancel_friend_request(profile_id, request_id):
    """Cancels a friend request sent by the user."""
    try:
        res = write_query(
            "UPDATE chain_friend_requests SET status = 'cancelled', updated_at = now() WHERE id = %s AND sender_profile_id = %s AND status = 'pending'",
            [request_id, profile_id]
        )
        return {"success": True} if res else {"success": False, "error": "Request not found or not pending."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def remove_friend(profile_id, friend_id):
    """Removes a friend relationship."""
    p1, p2 = _get_ordered_pair(profile_id, friend_id)
    try:
        res = write_query(
            "DELETE FROM chain_friends WHERE profile_id_1 = %s AND profile_id_2 = %s",
            [p1, p2]
        )
        if res:
            write_query("UPDATE chain_profiles SET friends_count = GREATEST(0, friends_count - 1) WHERE id IN (%s, %s)", [p1, p2])
            _invalidate_friend_cache(p1, p2)
            return {"success": True}
        return {"success": False, "error": "Friend relationship not found."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def are_friends(profile_id, other_id):
    """Checks if two profiles are friends."""
    p1, p2 = _get_ordered_pair(profile_id, other_id)
    res = fast_query(
        "SELECT 1 FROM chain_friends WHERE profile_id_1 = %s AND profile_id_2 = %s LIMIT 1",
        [p1, p2]
    )
    return bool(res)

def list_friends(profile_id, limit=20, cursor=None):
    """Lists friends for a profile with cursor pagination and Redis caching."""
    cache_key = f"friends_list:{profile_id}:{limit}:{cursor or 'first'}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    query = """
        SELECT id, profile_id_1, profile_id_2, status, created_at 
        FROM chain_friends 
        WHERE (profile_id_1 = %s OR profile_id_2 = %s)
    """
    params = [profile_id, profile_id]
    
    if cursor:
        query += " AND created_at < %s"
        params.append(cursor)
        
    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit + 1)
    
    rows = fast_query(query, params)
    
    has_more = len(rows) > limit
    rows = rows[:limit]
    
    friend_ids = []
    for r in rows:
        fid = r['profile_id_2'] if r['profile_id_1'] == profile_id else r['profile_id_1']
        friend_ids.append(fid)
        
    if not friend_ids:
        result = {"friends": [], "has_more": False, "next_cursor": None}
        cache_set(cache_key, result, ttl=300)
        return result
        
    placeholders = ",".join(["%s"] * len(friend_ids))
    profiles = fast_query(
        f"SELECT id, username, display_name, avatar_url, is_verified, is_online FROM chain_profiles WHERE id IN ({placeholders})",
        friend_ids
    )
    
    # Maintain order and add friendship info
    pmap = {p['id']: p for p in profiles}
    ordered_friends = []
    for r in rows:
        fid = r['profile_id_2'] if r['profile_id_1'] == profile_id else r['profile_id_1']
        if fid in pmap:
            p = dict(pmap[fid])
            p['friendship_status'] = r['status']
            p['became_friends_at'] = r['created_at']
            ordered_friends.append(p)
            
    next_cursor = rows[-1]['created_at'].isoformat() if has_more else None
    
    result = {
        "friends": ordered_friends,
        "has_more": has_more,
        "next_cursor": next_cursor
    }
    cache_set(cache_key, result, ttl=300)
    return result

def list_friend_requests(profile_id, direction='received', limit=20, cursor=None):
    """Lists friend requests for a profile."""
    col = "recipient_profile_id" if direction == 'received' else "sender_profile_id"
    join_col = "sender_profile_id" if direction == 'received' else "recipient_profile_id"
    
    query = f"""
        SELECT cfr.id, cfr.sender_profile_id, cfr.recipient_profile_id, cfr.status, cfr.created_at,
               cp.username, cp.display_name, cp.avatar_url, cp.is_verified
        FROM chain_friend_requests cfr
        JOIN chain_profiles cp ON cfr.{join_col} = cp.id
        WHERE cfr.{col} = %s AND cfr.status = 'pending'
    """

    params = [profile_id]
    
    if cursor:
        query += " AND cfr.created_at < %s"
        params.append(cursor)
        
    query += " ORDER BY cfr.created_at DESC LIMIT %s"
    params.append(limit + 1)
    
    rows = fast_query(query, params)
    has_more = len(rows) > limit
    items = rows[:limit]
    
    next_cursor = items[-1]['created_at'].isoformat() if has_more and items else None
    
    return {
        "requests": items,
        "has_more": has_more,
        "next_cursor": next_cursor
    }

def get_mutual_friends(profile_id_1, profile_id_2, limit=20, offset=0):
    """Finds mutual friends between two profiles."""
    cache_key = f"mutual_friends:{profile_id_1}:{profile_id_2}"
    if offset == 0:
        cached = cache_get(cache_key)
        if cached is not None: return cached

    query = """
        WITH p1_friends AS (
            SELECT CASE WHEN profile_id_1 = %s THEN profile_id_2 ELSE profile_id_1 END as friend_id
            FROM chain_friends WHERE profile_id_1 = %s OR profile_id_2 = %s
        ),
        p2_friends AS (
            SELECT CASE WHEN profile_id_1 = %s THEN profile_id_2 ELSE profile_id_1 END as friend_id
            FROM chain_friends WHERE profile_id_1 = %s OR profile_id_2 = %s
        )
        SELECT cp.id, cp.username, cp.display_name, cp.avatar_url, cp.is_verified
        FROM p1_friends f1
        JOIN p2_friends f2 ON f1.friend_id = f2.friend_id
        JOIN chain_profiles cp ON f1.friend_id = cp.id
        LIMIT %s OFFSET %s
    """
    res = fast_query(query, [profile_id_1, profile_id_1, profile_id_1, profile_id_2, profile_id_2, profile_id_2, limit, offset])
    
    if offset == 0:
        cache_set(cache_key, res or [], ttl=600)
    return res

def suggest_friends(profile_id, limit=20):
    """Suggests friends based on mutual friends of friends (simplified)."""
    # 1. Get current friends
    # 2. Get friends of friends
    # 3. Exclude current friends and pending requests
    # For now, let's just suggest popular profiles that are not friends yet
    query = """
        SELECT id, username, display_name, avatar_url, is_verified
        FROM chain_profiles
        WHERE id != %s
          AND id NOT IN (
              SELECT profile_id_1 FROM chain_friends WHERE profile_id_2 = %s
              UNION
              SELECT profile_id_2 FROM chain_friends WHERE profile_id_1 = %s
          )
          AND id NOT IN (
              SELECT recipient_profile_id FROM chain_friend_requests WHERE sender_profile_id = %s AND status = 'pending'
              UNION
              SELECT sender_profile_id FROM chain_friend_requests WHERE recipient_profile_id = %s AND status = 'pending'
          )
        ORDER BY followers_count DESC
        LIMIT %s
    """
    res = fast_query(query, [profile_id, profile_id, profile_id, profile_id, profile_id, limit])
    return res

def set_friend_status(profile_id, friend_id, status):
    """Sets friend status (friend, close_friend, best_friend)."""
    if status not in ['friend', 'close_friend', 'best_friend']:
        return {"success": False, "error": "Invalid status."}
    p1, p2 = _get_ordered_pair(profile_id, friend_id)
    try:
        res = write_query(
            "UPDATE chain_friends SET status = %s, updated_at = now() WHERE profile_id_1 = %s AND profile_id_2 = %s",
            [status, p1, p2]
        )
        return {"success": True} if res else {"success": False, "error": "Friend relationship not found."}
    except Exception as e:
        return {"success": False, "error": str(e)}
