"""Trending hashtags and locations."""

from services.neon_service import fast_query, write_query


def get_trending_hashtags(limit=20):
    rows = fast_query(
        """SELECT hashtag, usage_count, engagement_score, last_used_at
           FROM chain_hashtag_stats
           ORDER BY engagement_score DESC, usage_count DESC
           LIMIT %s""",
        (limit,), default=[],
    )
    return [
        {
            "hashtag": r["hashtag"],
            "usage_count": r.get("usage_count", 0) or 0,
            "engagement_score": r.get("engagement_score", 0) or 0,
            "last_used_at": r["last_used_at"].isoformat() if r.get("last_used_at") else None,
        }
        for r in rows
    ]


def get_trending_locations(limit=20):
    namibia_towns = [
        "Windhoek", "Swakopmund", "Walvis Bay", "Rundu", "Ongwediva",
        "Katima Mulilo", "Keetmanshoop", "Oshakati", "Otjiwarongo", "Tsumeb",
        "Grootfontein", "Mariental", "Rehoboth", "Lüderitz", "Outapi",
    ]

    rows = fast_query(
        """SELECT location, COUNT(*) AS profile_count
           FROM chain_profiles
           WHERE location IS NOT NULL
             AND location != ''
             AND deleted_at IS NULL
           GROUP BY location
           ORDER BY profile_count DESC LIMIT 30""",
        default=[],
    )

    location_counts = {}
    for r in rows:
        loc = (r["location"] or "").strip().lower()
        if loc:
            location_counts[loc] = r["profile_count"]

    result = []
    seen = set()
    for town in namibia_towns:
        key = town.lower()
        count = location_counts.get(key, 0)
        if count > 0:
            result.append({"location": town, "profile_count": count})
            seen.add(key)

    for loc, count in sorted(location_counts.items(), key=lambda x: -x[1]):
        if loc not in seen and len(result) < limit:
            result.append({"location": loc.title(), "profile_count": count})
            seen.add(loc)

    return result[:limit]


def track_hashtag_usage(hashtag, content_type="post", location=None):
    hashtag = hashtag.strip().lower()
    if not hashtag:
        return
    try:
        existing = fast_query(
            "SELECT id, usage_count FROM chain_hashtag_stats WHERE hashtag = %s AND content_type = %s",
            (hashtag, content_type), default=[],
        )
        if existing:
            write_query(
                """UPDATE chain_hashtag_stats
                   SET usage_count = usage_count + 1, last_used_at = now(), updated_at = now()
                   WHERE id = %s""",
                (existing[0]["id"],),
            )
        else:
            write_query(
                """INSERT INTO chain_hashtag_stats (hashtag, content_type, usage_count, location, last_used_at)
                   VALUES (%s, %s, 1, %s, now())""",
                (hashtag, content_type, location),
            )
    except Exception:
        pass


def extract_and_track_hashtags(caption, content_type="post", location=None):
    if not caption:
        return
    import re
    tags = re.findall(r"#(\w+)", caption)
    for tag in tags[:10]:
        track_hashtag_usage(tag, content_type, location)

def get_trending_items(item_type="hashtag", limit=20, *args, **kwargs):
    """Backward-compatible trending helper used by feed_service."""
    try:
        if item_type in ("hashtag", "hashtags"):
            return get_trending_hashtags(limit=limit)
        if item_type in ("location", "locations"):
            return get_trending_locations(limit=limit)
        if item_type in ("live", "live_room", "live_rooms"):
            from services.recommendation_service import get_trending
            data = get_trending(window_hours=6, limit=limit, content_type="live")
            return data.get("live", [])
        if item_type in ("post", "posts"):
            from services.recommendation_service import get_trending
            data = get_trending(window_hours=24, limit=limit, content_type="posts")
            return data.get("posts", [])
        if item_type in ("reel", "reels"):
            from services.recommendation_service import get_trending
            data = get_trending(window_hours=24, limit=limit, content_type="reels")
            return data.get("reels", [])
        if item_type in ("creator", "creators"):
            from services.recommendation_service import get_trending
            data = get_trending(window_hours=168, limit=limit, content_type="creators")
            return data.get("creators", [])
        return []
    except Exception:
        return []


def get_trending_with_windows(limit=10):
    """Return trending for 1h, 6h, 24h, 7d rolling windows."""
    from services.recommendation_service import get_trending_windows
    return get_trending_windows(limit=limit)
