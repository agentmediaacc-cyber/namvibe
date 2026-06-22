"""Relationship Cache Service — batched, cached relationship state for profiles.

Eliminates repeated SELECT 1 FROM chain_friends/follows/friend_requests
by caching relationship state between viewer/target pairs with Redis.

Key: rel:state:<viewer_id>:<target_id>
TTL: 60 seconds
"""

import re
from typing import Dict, List

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
    return states.get(str(target_id), _empty_state())


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

    friend_set = set()
    fr_sent = set()
    fr_received = set()
    following_set = set()
    fol_req_sent = set()
    fol_req_received = set()
    blocked_set = set()

    for chunk in _chunks(str_ids, 50):
        values = ", ".join(["(%s::uuid)"] * len(chunk))
        rows = fast_query(
            f"""
            WITH targets(id) AS (VALUES {values})
            SELECT 'friend' AS kind, t.id::text AS other_id
            FROM targets t
            JOIN chain_friends f
              ON ((f.profile_id_1 = %s::uuid AND f.profile_id_2 = t.id)
                  OR (f.profile_id_2 = %s::uuid AND f.profile_id_1 = t.id))
             AND f.status = 'friend'
             AND f.deleted_at IS NULL
            UNION ALL
            SELECT 'friend_request_sent' AS kind, r.recipient_profile_id::text AS other_id
            FROM chain_friend_requests r
            JOIN targets t ON t.id = r.recipient_profile_id
            WHERE r.sender_profile_id = %s::uuid AND r.status = 'pending'
            UNION ALL
            SELECT 'friend_request_received' AS kind, r.sender_profile_id::text AS other_id
            FROM chain_friend_requests r
            JOIN targets t ON t.id = r.sender_profile_id
            WHERE r.recipient_profile_id = %s::uuid AND r.status = 'pending'
            UNION ALL
            SELECT 'following' AS kind, f.following_profile_id::text AS other_id
            FROM chain_follows f
            JOIN targets t ON t.id = f.following_profile_id
            WHERE f.follower_profile_id = %s::uuid AND f.deleted_at IS NULL
            UNION ALL
            SELECT 'follow_request_sent' AS kind, r.target_profile_id::text AS other_id
            FROM chain_follow_requests r
            JOIN targets t ON t.id = r.target_profile_id
            WHERE r.requester_profile_id = %s::uuid AND r.status = 'pending'
            UNION ALL
            SELECT 'follow_request_received' AS kind, r.requester_profile_id::text AS other_id
            FROM chain_follow_requests r
            JOIN targets t ON t.id = r.requester_profile_id
            WHERE r.target_profile_id = %s::uuid AND r.status = 'pending'
            UNION ALL
            SELECT 'blocked' AS kind,
                   CASE WHEN b.blocker_profile_id = %s::uuid THEN b.blocked_profile_id::text ELSE b.blocker_profile_id::text END AS other_id
            FROM chain_blocks b
            JOIN targets t ON t.id = CASE WHEN b.blocker_profile_id = %s::uuid THEN b.blocked_profile_id ELSE b.blocker_profile_id END
            WHERE (b.blocker_profile_id = %s::uuid OR b.blocked_profile_id = %s::uuid)
              AND b.deleted_at IS NULL
            """,
            (*chunk, str_viewer, str_viewer, str_viewer, str_viewer, str_viewer, str_viewer, str_viewer, str_viewer, str_viewer, str_viewer, str_viewer),
            timeout_ms=5000, default=[]
        )
        for r in rows:
            other = str(r.get("other_id"))
            if other not in id_set:
                continue
            kind = r.get("kind")
            if kind == "friend":
                friend_set.add(other)
            elif kind == "friend_request_sent":
                fr_sent.add(other)
            elif kind == "friend_request_received":
                fr_received.add(other)
            elif kind == "following":
                following_set.add(other)
            elif kind == "follow_request_sent":
                fol_req_sent.add(other)
            elif kind == "follow_request_received":
                fol_req_received.add(other)
            elif kind == "blocked":
                blocked_set.add(other)

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
            blocked = tid_s in blocked_set

            if blocked:
                rel = "blocked"
            elif is_friend:
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
                "blocked": blocked,
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
