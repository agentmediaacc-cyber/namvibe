"""Relationship Cache Service — batched, cached relationship state for profiles.

Eliminates repeated SELECT 1 FROM chain_friends/follows/friend_requests
by caching relationship state between viewer/target pairs with Redis.

Key: rel:state:<viewer_id>:<target_id>
TTL: 60 seconds
"""

import re
from typing import Dict, List

from services.blocking_service import is_blocked_any
from services.neon_service import fast_query
from services.redis_service import cache_get, cache_set, cache_delete


REL_CACHE_TTL = 60

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def is_uuid(s):
    return bool(_UUID_RE.match(str(s))) if s else False


def _empty_state():
    return {
        "is_self": False,
        "is_friend": False,
        "friend_request_sent": False,
        "friend_request_received": False,
        "is_following": False,
        "follow_request_sent": False,
        "follow_request_received": False,
        "blocked": False,
        "relationship": "none",
    }


def _rel_cache_key(viewer_id: str, target_id: str) -> str:
    return f"rel:state:{viewer_id}:{target_id}"


def get_relationship_state(viewer_id: str, target_id: str) -> Dict:
    """Get cached relationship state, building it if missing.
    
    Delegates to get_many_relationship_states() to eliminate duplicate
    query paths.
    """
    if not viewer_id or not target_id:
        return _empty_state()
    if not is_uuid(viewer_id) or not is_uuid(target_id):
        return _empty_state()
    states = get_many_relationship_states(viewer_id, [target_id])
    state = states.get(str(target_id), _empty_state())
    if state.get("is_self"):
        return state
    if is_blocked_any(viewer_id, target_id):
        return dict(state, blocked=True, relationship="blocked")
    return state


def get_many_relationship_states(viewer_id: str, target_ids: List[str]) -> Dict[str, Dict]:
    """Batch get relationship states for multiple targets in one round-trip per table."""
    if not viewer_id or not target_ids:
        return {}
    if not is_uuid(viewer_id):
        return {str(t): _empty_state() for t in target_ids}
    result = {}
    uncached_ids = []
    for tid in target_ids:
        tid_s = str(tid)
        if not is_uuid(tid_s):
            result[tid_s] = _empty_state()
            continue
        key = _rel_cache_key(viewer_id, tid_s)
        cached = cache_get(key)
        if isinstance(cached, dict):
            result[tid_s] = cached
        else:
            uncached_ids.append(tid_s)

    if not uncached_ids:
        return result

    str_viewer = str(viewer_id)
    str_ids = [str(i) for i in uncached_ids]
    id_set = set(str_ids)

    # Batch friends
    friend_set = set()
    for chunk in _chunks(str_ids, 50):
        placeholders = ", ".join(["%s"] * len(chunk))
        fr_rows = fast_query(
            f"SELECT profile_id_1, profile_id_2 FROM chain_friends "
            f"WHERE (profile_id_1 = %s OR profile_id_2 = %s) "
            f"AND (profile_id_1 IN ({placeholders}) OR profile_id_2 IN ({placeholders})) "
            f"AND status = 'friend'",
            (str_viewer, str_viewer, *chunk, *chunk),
            timeout_ms=5000, default=[]
        )
        for r in fr_rows:
            other = str(r["profile_id_2"]) if str(r["profile_id_1"]) == str_viewer else str(r["profile_id_1"])
            if other in id_set:
                friend_set.add(other)

    # Batch friend requests (pending)
    fr_sent = set()
    fr_received = set()
    for chunk in _chunks(str_ids, 50):
        placeholders = ", ".join(["%s"] * len(chunk))
        req_rows = fast_query(
            f"SELECT sender_profile_id, recipient_profile_id FROM chain_friend_requests "
            f"WHERE ((sender_profile_id = %s AND recipient_profile_id IN ({placeholders})) "
            f"OR (sender_profile_id IN ({placeholders}) AND recipient_profile_id = %s)) "
            f"AND status = 'pending'",
            (str_viewer, *chunk, *chunk, str_viewer),
            timeout_ms=5000, default=[]
        )
        for r in req_rows:
            other = str(r["recipient_profile_id"]) if str(r["sender_profile_id"]) == str_viewer else str(r["sender_profile_id"])
            if other not in id_set:
                continue
            if str(r["sender_profile_id"]) == str_viewer:
                fr_sent.add(other)
            else:
                fr_received.add(other)

    # Batch follows
    following_set = set()
    for chunk in _chunks(str_ids, 50):
        placeholders = ", ".join(["%s"] * len(chunk))
        fol_rows = fast_query(
            f"SELECT following_profile_id FROM chain_follows "
            f"WHERE follower_profile_id = %s AND following_profile_id IN ({placeholders})",
            (str_viewer, *chunk),
            timeout_ms=5000, default=[]
        )
        for r in fol_rows:
            following_set.add(str(r["following_profile_id"]))

    # Batch follow requests
    fol_req_sent = set()
    fol_req_received = set()
    for chunk in _chunks(str_ids, 50):
        placeholders = ", ".join(["%s"] * len(chunk))
        fol_req_rows = fast_query(
            f"SELECT requester_profile_id, target_profile_id FROM chain_follow_requests "
            f"WHERE ((requester_profile_id = %s AND target_profile_id IN ({placeholders})) "
            f"OR (requester_profile_id IN ({placeholders}) AND target_profile_id = %s)) "
            f"AND status = 'pending'",
            (str_viewer, *chunk, *chunk, str_viewer),
            timeout_ms=5000, default=[]
        )
        for r in fol_req_rows:
            other = str(r["target_profile_id"]) if str(r["requester_profile_id"]) == str_viewer else str(r["requester_profile_id"])
            if other not in id_set:
                continue
            if str(r["requester_profile_id"]) == str_viewer:
                fol_req_sent.add(other)
            else:
                fol_req_received.add(other)

    for tid in uncached_ids:
        tid_s = str(tid)
        if tid_s == str_viewer:
            state = {
                "is_self": True, "is_friend": False,
                "friend_request_sent": False, "friend_request_received": False,
                "is_following": False, "follow_request_sent": False,
                "follow_request_received": False, "blocked": False,
                "relationship": "self",
            }
        else:
            is_friend = tid_s in friend_set
            f_req_sent = tid_s in fr_sent
            f_req_rcv = tid_s in fr_received
            is_following = tid_s in following_set
            fol_req_s = tid_s in fol_req_sent
            fol_req_r = tid_s in fol_req_received

            if is_friend:
                rel = "friend"
            elif f_req_sent:
                rel = "pending_sent"
            elif f_req_rcv:
                rel = "pending_received"
            elif is_following:
                rel = "follower"
            elif fol_req_s:
                rel = "follow_request_sent"
            elif fol_req_r:
                rel = "follow_request_received"
            else:
                rel = "none"

            state = {
                "is_self": False,
                "is_friend": is_friend,
                "friend_request_sent": f_req_sent,
                "friend_request_received": f_req_rcv,
                "is_following": is_following,
                "follow_request_sent": fol_req_s,
                "follow_request_received": fol_req_r,
                "blocked": False,
                "relationship": rel,
            }

        key = _rel_cache_key(str_viewer, tid_s)
        cache_set(key, state, ttl=REL_CACHE_TTL)
        result[tid_s] = state

    return result


def invalidate_relationship_state(viewer_id: str, target_id: str):
    """Clear cached relationship state between viewer and target."""
    if viewer_id and target_id and is_uuid(viewer_id) and is_uuid(target_id):
        cache_delete(_rel_cache_key(viewer_id, target_id))


def invalidate_profile_relationships(profile_id: str):
    """Invalidate all relationship caches TO and FROM this profile.
    Note: We can't scan Redis keys with this pattern easily,
    so we rely on TTL expiry. This is a best-effort clear of known patterns.
    """
    if not profile_id:
        return
    cache_delete(f"rel:state:{profile_id}:*")
    pass


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]
