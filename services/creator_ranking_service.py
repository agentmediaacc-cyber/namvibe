"""Creator ranking: trending creators based on engagement, activity, trust."""

from services.neon_service import fast_query


def get_trending_creators(limit=20, offset=0):
    rows = fast_query(
        """SELECT p.id, p.display_name, p.username, p.avatar_url, p.bio,
                  p.follower_count, p.following_count, p.engagement_score,
                  p.verified, p.location,
                  COALESCE(p.follower_count, 0) +
                  COALESCE(p.engagement_score, 0) * 10 +
                  CASE WHEN p.verified THEN 50 ELSE 0 END -
                  COALESCE(p.report_count, 0) * 20 AS rank_score
           FROM chain_profiles p
           WHERE p.deleted_at IS NULL
             AND p.is_private = FALSE
           ORDER BY rank_score DESC
           LIMIT %s OFFSET %s""",
        (limit, offset), default=[],
    )
    return [
        {
            "id": str(r["id"]),
            "display_name": r.get("display_name", ""),
            "username": r.get("username", ""),
            "avatar_url": r.get("avatar_url", ""),
            "bio": r.get("bio", ""),
            "follower_count": r.get("follower_count", 0) or 0,
            "following_count": r.get("following_count", 0) or 0,
            "engagement_score": r.get("engagement_score", 0) or 0,
            "verified": bool(r.get("verified")),
            "location": r.get("location", ""),
            "rank_score": r.get("rank_score", 0) or 0,
        }
        for r in rows
    ]


def get_creator_detail(profile_id):
    row = fast_query(
        """SELECT p.id, p.display_name, p.username, p.avatar_url, p.bio,
                  p.follower_count, p.following_count, p.engagement_score,
                  p.verified, p.location, p.report_count,
                   (SELECT COUNT(*) FROM chain_posts WHERE profile_id = p.id AND deleted_at IS NULL) AS post_count,
                   (SELECT COUNT(*) FROM chain_reels WHERE profile_id = p.id AND deleted_at IS NULL) AS reel_count,
                  (SELECT COUNT(*) FROM chain_status_posts WHERE profile_id = p.id AND expires_at > now() AND deleted_at IS NULL) AS active_stories
           FROM chain_profiles p
           WHERE p.id = %s AND p.deleted_at IS NULL""",
        (profile_id,), default=[],
    )
    if not row:
        return None
    r = row[0]
    return {
        "id": str(r["id"]),
        "display_name": r.get("display_name", ""),
        "username": r.get("username", ""),
        "avatar_url": r.get("avatar_url", ""),
        "bio": r.get("bio", ""),
        "follower_count": r.get("follower_count", 0) or 0,
        "following_count": r.get("following_count", 0) or 0,
        "engagement_score": r.get("engagement_score", 0) or 0,
        "verified": bool(r.get("verified")),
        "location": r.get("location", ""),
        "report_count": r.get("report_count", 0) or 0,
        "post_count": r.get("post_count", 0) or 0,
        "reel_count": r.get("reel_count", 0) or 0,
        "active_stories": r.get("active_stories", 0) or 0,
    }
