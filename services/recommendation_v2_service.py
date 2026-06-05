from services.neon_service import fast_query
from services.supabase_safe import safe_select

def get_recommended_content(profile_id, limit=10):
    """
    Returns a mix of recommended content (creators, live rooms, businesses)
    based on trust scores and recent activity.
    """
    # 1. Recommended Creators (High trust score, similar interests)
    user_interests = []
    if profile_id:
        user = (safe_select("chain_profiles", columns="interests", filters={"id": profile_id}, limit=1) or [{}])[0]
        user_interests = user.get("interests") or []

    # Simplified recommendation: High trust score + is creator + not already followed
    sql = """
        SELECT id, username, avatar_url, trust_score, creator_category
        FROM chain_profiles
        WHERE is_creator = TRUE 
          AND deleted_at IS NULL
          AND trust_score >= 7.0
    """
    if profile_id:
        sql += " AND id != %s AND id NOT IN (SELECT following_profile_id FROM chain_follows WHERE follower_profile_id = %s AND deleted_at IS NULL)"
        params = (profile_id, profile_id, limit)
    else:
        params = (limit,)
        
    sql += " ORDER BY trust_score DESC, created_at DESC LIMIT %s"
    
    creators = fast_query(sql, params)
    
    # 2. Trending Live Rooms
    rooms = safe_select("chain_live_rooms", filters={"is_live": True}, limit=5, order_by="viewer_count", desc=True)
    
    # 3. Nearby Businesses
    businesses = safe_select("chain_profiles", filters={"account_type": "business"}, limit=5, order_by="trust_score", desc=True)
    
    return {
        "creators": creators,
        "live_rooms": rooms,
        "businesses": businesses
    }
