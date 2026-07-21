"""
Social Service — Network management (Followers/Following) and other social interactions.
"""
from services.neon_service import fast_query, write_query, _DB_EXECUTOR
from services.logging_service import log_info, log_error
from services.redis_service import cache_get, cache_set, cache_delete

def _invalidate_social_cache(profile_id):
    """Clears and warms up social list caches for a profile."""
    cache_delete(f"followers_list:{profile_id}:20:first")
    cache_delete(f"following_list:{profile_id}:20:first")
    cache_delete(f"social_counts:{profile_id}")
    # Warmup
    _DB_EXECUTOR.submit(list_followers, profile_id)
    _DB_EXECUTOR.submit(list_following, profile_id)
    _DB_EXECUTOR.submit(get_social_counts, profile_id)

def get_social_counts(profile_id):
    """Retrieves followers, following, and friends counts with caching."""
    cache_key = f"social_counts:{profile_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    query = """
        SELECT 
            (SELECT COUNT(*) FROM chain_follows WHERE following_profile_id = %s) as followers,
            (SELECT COUNT(*) FROM chain_follows WHERE follower_profile_id = %s) as following,
            (SELECT COUNT(*) FROM chain_friends WHERE profile_id_1 = %s OR profile_id_2 = %s) as friends
    """
    res = fast_query(query, [profile_id, profile_id, profile_id, profile_id])
    counts = res[0] if res else {"followers": 0, "following": 0, "friends": 0}
    
    cache_set(cache_key, counts, ttl=900) # 15 minutes
    return counts

def list_followers(profile_id, limit=20, cursor=None):
    """Lists followers for a profile with cursor pagination and Redis caching."""
    cache_key = f"followers_list:{profile_id}:{limit}:{cursor or 'first'}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    query = """
        SELECT cf.created_at, cp.id, cp.username, cp.display_name, cp.avatar_url, cp.is_verified, cp.is_online
        FROM chain_follows cf
        JOIN chain_profiles cp ON cf.follower_profile_id = cp.id
        WHERE cf.following_profile_id = %s
    """
    params = [profile_id]
    
    if cursor:
        query += " AND cf.created_at < %s"
        params.append(cursor)
        
    query += " ORDER BY cf.created_at DESC, cp.id DESC LIMIT %s"
    params.append(limit + 1)
    
    rows = fast_query(query, params)
    has_more = len(rows) > limit
    items = rows[:limit]
    
    next_cursor = items[-1]['created_at'].isoformat() if has_more and items else None
    
    seen = set()
    unique_items = []
    for item in items:
        pid = str(item.get("id") or "")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        unique_items.append(item)
    result = {"followers": unique_items, "has_more": has_more, "next_cursor": next_cursor}
    cache_set(cache_key, result, ttl=300)
    return result

def list_following(profile_id, limit=20, cursor=None):
    """Lists following for a profile with cursor pagination and Redis caching."""
    cache_key = f"following_list:{profile_id}:{limit}:{cursor or 'first'}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    query = """
        SELECT cf.created_at, cp.id, cp.username, cp.display_name, cp.avatar_url, cp.is_verified, cp.is_online
        FROM chain_follows cf
        JOIN chain_profiles cp ON cf.following_profile_id = cp.id
        WHERE cf.follower_profile_id = %s
    """
    params = [profile_id]
    
    if cursor:
        query += " AND cf.created_at < %s"
        params.append(cursor)
        
    query += " ORDER BY cf.created_at DESC, cp.id DESC LIMIT %s"
    params.append(limit + 1)
    
    rows = fast_query(query, params)
    has_more = len(rows) > limit
    items = rows[:limit]
    
    next_cursor = items[-1]['created_at'].isoformat() if has_more and items else None
    
    seen = set()
    unique_items = []
    for item in items:
        pid = str(item.get("id") or "")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        unique_items.append(item)
    result = {"following": unique_items, "has_more": has_more, "next_cursor": next_cursor}
    cache_set(cache_key, result, ttl=300)
    return result
