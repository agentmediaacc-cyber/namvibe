from services.neon_service import fast_query
from services.redis_service import cache_get, cache_set

def get_creator_stats(profile_id):
    """Retrieves high-level analytics for a creator."""
    cache_key = f"creator_stats_{profile_id}"
    cached = cache_get(cache_key)
    if cached: return cached

    # 1. Profile Growth (Placeholder)
    # 2. Reel Views
    sql_reels = "SELECT SUM(views_count) as total_views, SUM(likes_count) as total_likes FROM chain_reels WHERE profile_id = %s AND deleted_at IS NULL"
    reels_res = fast_query(sql_reels, (profile_id,))
    
    # 3. Live Earnings
    sql_earnings = "SELECT SUM(amount) as total_coins FROM chain_wallet_transactions WHERE profile_id = %s AND tx_type = 'gift_received' AND status = 'completed'"
    earnings_res = fast_query(sql_earnings, (profile_id,))

    stats = {
        "total_reel_views": reels_res[0]['total_views'] if reels_res else 0,
        "total_reel_likes": reels_res[0]['total_likes'] if reels_res else 0,
        "total_live_earnings": float(earnings_res[0]['total_coins'] or 0) if earnings_res else 0,
        "followers_count": 0, # To be implemented with follows table
        "engagement_rate": 0
    }
    
    # Calculate simple engagement rate
    if stats['total_reel_views'] > 0:
        stats['engagement_rate'] = round((stats['total_reel_likes'] / stats['total_reel_views']) * 100, 2)

    cache_set(cache_key, stats, ttl=600) # Cache for 10 min
    return stats

def get_daily_views(profile_id, days=7):
    """Retrieves daily view counts for the last X days."""
    sql = """
        SELECT date_trunc('day', created_at) as day, count(*) as count
        FROM chain_analytics_events
        WHERE entity_id IN (SELECT id FROM chain_reels WHERE profile_id = %s)
        AND event_type = 'reel_view'
        AND created_at > now() - interval '%s days'
        GROUP BY day
        ORDER BY day ASC
    """
    # This requires analytics_events table to be populated
    return fast_query(sql, (profile_id, days))
