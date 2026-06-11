from services.neon_service import fast_query
from services.content_service import local_content, search_hashtags
from services.homepage_real_data_guard import filter_feed_posts, filter_profiles, public_profile_sql, public_profile_subquery


def _like(q):
    return f"%{q}%"


def _local_search(q, limit):
    lowered = q.lower().lstrip("#")
    local = local_content()
    profiles = []
    posts = [
        {**post, "excerpt": (post.get("caption") or post.get("body") or "")[:180]}
        for post in local["posts"]
        if lowered in (post.get("caption") or post.get("body") or post.get("town_tag") or "").lower()
        or lowered in " ".join(f"#{tag}" for tag in local["hashtags"]).lower()
    ][:limit]
    reels = [
        reel for reel in local["reels"]
        if lowered in (reel.get("caption") or reel.get("music_title") or "").lower()
    ][:limit]
    return profiles, posts, reels

def record_search(profile_id, query):
    """Records a search query for history and trending analytics."""
    if not profile_id or not query:
        return

    import uuid
    from flask import session, has_request_context

    resolved_profile_id = profile_id

    try:
        uuid.UUID(str(resolved_profile_id))
    except Exception:
        resolved_profile_id = None
        if has_request_context():
            resolved_profile_id = session.get("profile_id")

    try:
        uuid.UUID(str(resolved_profile_id))
    except Exception:
        return

    sql = "INSERT INTO chain_search_history (profile_id, query) VALUES (%s, %s)"
    from services.neon_service import write_query
    write_query(sql, (str(resolved_profile_id), query.strip()))

def get_recent_searches(profile_id, limit=5):
    """Returns recent searches for a user."""
    if not profile_id:
        return []

    import uuid
    from flask import session, has_request_context

    resolved_profile_id = profile_id

    try:
        uuid.UUID(str(resolved_profile_id))
    except Exception:
        resolved_profile_id = None
        if has_request_context():
            resolved_profile_id = session.get("profile_id")

    try:
        uuid.UUID(str(resolved_profile_id))
    except Exception:
        return []

    sql = """
        SELECT query
        FROM (
            SELECT query, MAX(created_at) AS last_used
            FROM chain_search_history
            WHERE profile_id = %s
            GROUP BY query
        ) recent
        ORDER BY last_used DESC
        LIMIT %s
    """
    return fast_query(sql, (str(resolved_profile_id), limit), default=[])

def get_trending_searches(limit=5):
    """Returns popular searches in the last 24 hours"""
    sql = """
        SELECT query, COUNT(*) as frequency
        FROM chain_search_history
        WHERE created_at > now() - interval '24 hours'
        GROUP BY query
        ORDER BY frequency DESC
        LIMIT %s
    """
    return fast_query(sql, (limit,))

def get_suggested_searches(limit=5):
    """Returns suggested searches based on popular creators and hashtags"""
    # Placeholder for real suggestion logic
    sql = f"SELECT username as query FROM chain_profiles WHERE is_creator = TRUE AND is_verified = TRUE AND {public_profile_sql('chain_profiles')} ORDER BY followers_count DESC LIMIT %s"
    return fast_query(sql, (limit,))

def smart_search(query, profile_id=None, limit=20):
    q = (query or "").strip()
    if not q:
        return {
            "query": q, "has_query": False, "profiles": [], "live_rooms": [], "posts": [], 
            "hashtags": [], "reels": [], "total_results": 0,
            "recent": [],
            "trending": [],
            "suggested": []
        }

    # Caching search results
    from services.redis_service import cache_get, cache_set
    cache_key = f"search_v2:{q}:{limit}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    # Skip blocking search-history writes during page render.
    # TODO: move this to a background job.
    pass
    
    results = {
        "query": q,
        "has_query": True,
        "profiles": [],
        "live_rooms": [],
        "posts": [],
        "hashtags": [],
        "reels": [],
        "recent": [],
        "trending": [],
        "suggested": [],
        "total_results": 0,
    }

    profiles = fast_query(
        f"""
        SELECT id, username, full_name, display_name, avatar_url, bio, current_location
        FROM chain_profiles
        WHERE deleted_at IS NULL
        AND COALESCE(is_public, TRUE) = TRUE
        AND {public_profile_sql("chain_profiles")}
        AND (username ILIKE %s OR full_name ILIKE %s OR display_name ILIKE %s OR current_location ILIKE %s)
        ORDER BY created_at DESC NULLS LAST LIMIT %s
        """,
        (_like(q), _like(q), _like(q), _like(q), limit),
        timeout_ms=1500,
        default=[],
    )
    posts = fast_query(
        f"""
        SELECT id, profile_id, body, caption, media_url, video_url, link_url, town_tag, created_at
        FROM chain_posts
        WHERE deleted_at IS NULL AND visibility = 'public'
        AND profile_id IN ({public_profile_subquery()})
        AND (caption ILIKE %s OR body ILIKE %s OR town_tag ILIKE %s)
        ORDER BY created_at DESC NULLS LAST LIMIT %s
        """,
        (_like(q), _like(q), _like(q), limit),
        timeout_ms=1500,
        default=[],
    )
    live_rooms = fast_query(
        """
        SELECT id, title, category, status, viewer_count
        FROM chain_live_rooms
        WHERE deleted_at IS NULL AND (title ILIKE %s OR category ILIKE %s)
        ORDER BY created_at DESC NULLS LAST LIMIT %s
        """,
        (_like(q), _like(q), limit),
        timeout_ms=1500,
        default=[],
    )
    reels = fast_query(
        f"""
        SELECT id, profile_id, caption, video_url, media_url, music_title, created_at
        FROM chain_reels
        WHERE deleted_at IS NULL AND visibility = 'public'
        AND profile_id IN ({public_profile_subquery()})
        AND (caption ILIKE %s OR music_title ILIKE %s)
        ORDER BY created_at DESC NULLS LAST LIMIT %s
        """,
        (_like(q), _like(q), limit),
        timeout_ms=1500,
        default=[],
    )
    local_profiles, local_posts, local_reels = _local_search(q, limit)
    results["profiles"] = filter_profiles(profiles or local_profiles)
    results["posts"] = [
        {**post, "excerpt": (post.get("caption") or post.get("body") or "")[:180]}
        for post in filter_feed_posts(posts or local_posts)
    ]
    results["live_rooms"] = live_rooms
    results["reels"] = filter_feed_posts(reels or local_reels)
    results["hashtags"] = search_hashtags(q)
    results["total_results"] = sum(len(results[key]) for key in ("profiles", "live_rooms", "posts", "hashtags", "reels"))
    
    # Cache for 5 minutes
    from services.redis_service import cache_set
    cache_set(f"search_v2:{q}:{limit}", results, ttl=300)
    
    return results

def search_chain(query, limit=20):
    return smart_search(query, limit)

def instant_search_dropdown(query):
    """Simplified search for dropdown results"""
    results = smart_search(query, limit=5)
    
    dropdown = []
    for p in results['profiles']:
        dropdown.append({"title": p['full_name'], "subtitle": f"@{p['username']}", "type": "profile", "image": p.get('avatar_url'), "url": f"/profile/@{p['username']}"})
    
    for r in results['live_rooms']:
        dropdown.append({"title": r['title'], "subtitle": f"Live in {r['category']}", "type": "live", "image": r.get('cover_url'), "url": f"/live/room/{r['id']}"})
        
    return dropdown[:10]
