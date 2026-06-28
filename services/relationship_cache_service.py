"""Relationship Cache Service — batched, cached relationship state for profiles.

Eliminates repeated SELECT 1 FROM chain_friends/follows/friend_requests
by caching relationship state between viewer/target pairs with Redis.

Key: rel:state:<viewer_id>:<target_id>
TTL: 60 seconds
"""

import os
import re
from typing import Dict, List

from psycopg2 import sql
from services.neon_service import fast_query
from services.redis_service import cache_get, cache_set, cache_mget, cache_set_bulk, cache_delete


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


def _build_relationship_state(tid_s, str_viewer, friend_set, fr_sent, fr_received,
                              following_set, fol_req_sent, fol_req_received, blocked_set):
    """Build a relationship state dict for a single target."""
    if tid_s == str_viewer:
        return {
            "is_self": True, "is_friend": False,
            "friend_request_sent": False, "friend_request_received": False,
            "is_following": False, "follow_request_sent": False,
            "follow_request_received": False, "blocked": False,
            "relationship": "self",
        }
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

    return {
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


def _query_relationship_states(str_viewer, str_ids, id_set):
    """Execute 7 bulk ANY queries and return set for each relationship type."""
    friend_set = set()
    fr_sent = set()
    fr_received = set()
    following_set = set()
    fol_req_sent = set()
    fol_req_received = set()
    blocked_set = set()

    for chunk in _chunks(str_ids, 50):
        chunk_literal = chunk
        
        following_rows = fast_query(
            sql.SQL("SELECT following_profile_id FROM chain_follows "
                    "WHERE follower_profile_id = %s::uuid AND following_profile_id = ANY(%s::uuid[]) AND deleted_at IS NULL"),
            (str_viewer, chunk_literal), timeout_ms=5000, default=[]
        )
        for r in following_rows:
            oid = str(r.get("following_profile_id"))
            if oid in id_set:
                following_set.add(oid)

        friend_rows = fast_query(
            sql.SQL("SELECT CASE WHEN profile_id_1 = %s THEN profile_id_2 ELSE profile_id_1 END AS other_id "
                    "FROM chain_friends "
                    "WHERE status = 'friend' AND deleted_at IS NULL "
                    "AND ((profile_id_1 = %s::uuid AND profile_id_2 = ANY(%s::uuid[])) "
                    "     OR (profile_id_2 = %s::uuid AND profile_id_1 = ANY(%s::uuid[])))"),
            (str_viewer, str_viewer, chunk_literal, str_viewer, chunk_literal), timeout_ms=5000, default=[]
        )
        for r in friend_rows:
            oid = str(r.get("other_id"))
            if oid in id_set:
                friend_set.add(oid)

        blocked_rows = fast_query(
            sql.SQL("SELECT CASE WHEN blocker_profile_id = %s THEN blocked_profile_id ELSE blocker_profile_id END AS other_id "
                    "FROM chain_blocks "
                    "WHERE deleted_at IS NULL "
                    "AND ((blocker_profile_id = %s::uuid AND blocked_profile_id = ANY(%s::uuid[])) "
                    "     OR (blocked_profile_id = %s::uuid AND blocker_profile_id = ANY(%s::uuid[])))"),
            (str_viewer, str_viewer, chunk_literal, str_viewer, chunk_literal), timeout_ms=5000, default=[]
        )
        for r in blocked_rows:
            oid = str(r.get("other_id"))
            if oid in id_set:
                blocked_set.add(oid)

        fr_sent_rows = fast_query(
            sql.SQL("SELECT recipient_profile_id FROM chain_friend_requests "
                    "WHERE sender_profile_id = %s::uuid AND recipient_profile_id = ANY(%s::uuid[]) AND status = 'pending'"),
            (str_viewer, chunk_literal), timeout_ms=5000, default=[]
        )
        for r in fr_sent_rows:
            oid = str(r.get("recipient_profile_id"))
            if oid in id_set:
                fr_sent.add(oid)

        fr_received_rows = fast_query(
            sql.SQL("SELECT sender_profile_id FROM chain_friend_requests "
                    "WHERE recipient_profile_id = %s::uuid AND sender_profile_id = ANY(%s::uuid[]) AND status = 'pending'"),
            (str_viewer, chunk_literal), timeout_ms=5000, default=[]
        )
        for r in fr_received_rows:
            oid = str(r.get("sender_profile_id"))
            if oid in id_set:
                fr_received.add(oid)

        fol_req_sent_rows = fast_query(
            sql.SQL("SELECT target_profile_id FROM chain_follow_requests "
                    "WHERE requester_profile_id = %s::uuid AND target_profile_id = ANY(%s::uuid[]) AND status = 'pending'"),
            (str_viewer, chunk_literal), timeout_ms=5000, default=[]
        )
        for r in fol_req_sent_rows:
            oid = str(r.get("target_profile_id"))
            if oid in id_set:
                fol_req_sent.add(oid)

        fol_req_received_rows = fast_query(
            sql.SQL("SELECT requester_profile_id FROM chain_follow_requests "
                    "WHERE target_profile_id = %s::uuid AND requester_profile_id = ANY(%s::uuid[]) AND status = 'pending'"),
            (str_viewer, chunk_literal), timeout_ms=5000, default=[]
        )
        for r in fol_req_received_rows:
            oid = str(r.get("requester_profile_id"))
            if oid in id_set:
                fol_req_received.add(oid)

    return following_set, friend_set, blocked_set, fr_sent, fr_received, fol_req_sent, fol_req_received


def get_many_relationship_states(viewer_id: str, target_ids: List[str]) -> Dict[str, Dict]:
    if not viewer_id or not target_ids:
        return {}
    if not is_uuid(viewer_id):
        return {str(t): _empty_state() for t in target_ids}

    str_viewer = str(viewer_id)
    result = {}
    uncached_ids = []

    id_key_pairs = []
    for tid in target_ids:
        tid_s = str(tid)
        if not is_uuid(tid_s):
            result[tid_s] = _empty_state()
        else:
            id_key_pairs.append((tid_s, _rel_cache_key(str_viewer, tid_s)))

    if not id_key_pairs:
        return result

    test_mode = os.environ.get("CHAIN_TEST_MODE") == "1"
    if test_mode:
        uncached_ids = [tid_s for tid_s, _ in id_key_pairs]
    else:
        all_keys = [k for _, k in id_key_pairs]
        cached_map = cache_mget(all_keys)
        for tid_s, key in id_key_pairs:
            cached = cached_map.get(key)
            if isinstance(cached, dict):
                result[tid_s] = cached
            else:
                uncached_ids.append(tid_s)

    if not uncached_ids:
        return result

    str_ids = [str(i) for i in uncached_ids]
    id_set = set(str_ids)

    (following_set, friend_set, blocked_set,
     fr_sent_set, fr_received_set,
     fol_req_sent_set, fol_req_received_set) = _query_relationship_states(str_viewer, str_ids, id_set)

    cache_pending = []
    for tid_s in uncached_ids:
        state = _build_relationship_state(
            tid_s, str_viewer,
            friend_set, fr_sent_set, fr_received_set,
            following_set, fol_req_sent_set, fol_req_received_set,
            blocked_set,
        )
        result[tid_s] = state
        if not test_mode:
            cache_pending.append((_rel_cache_key(str_viewer, tid_s), state))

    if not test_mode and cache_pending:
        cache_set_bulk(cache_pending, ttl=REL_CACHE_TTL)

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