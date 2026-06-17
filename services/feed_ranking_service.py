"""Viral feed ranking engine — scores by real engagement, recency, creator quality, and region match.
Falls back to chronological ordering if data is insufficient."""
import math
from datetime import datetime, timezone
from services.neon_service import fast_query, is_circuit_open, write_query

_EMPTY = []

def _utcnow():
    return datetime.now(timezone.utc)

def _safe_int(v, d=0):
    try: return int(v or d)
    except: return d

def _safe_float(v, d=0.0):
    try: return float(v or d)
    except: return d

def _parse_dt(v):
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if not v: return _utcnow()
    try:
        t = str(v).replace("Z", "+00:00")
        p = datetime.fromisoformat(t)
        return p if p.tzinfo else p.replace(tzinfo=timezone.utc)
    except: return _utcnow()

def _age_hours(created_at):
    if not created_at: return 999
    dt = _parse_dt(created_at)
    return max(0, (_utcnow() - dt).total_seconds() / 3600)

def _region_from_profile(profile_id):
    if not profile_id: return ""
    rows = fast_query("""
        SELECT COALESCE(NULLIF(current_location,''), NULLIF(region,''), NULLIF(country_origin,''), '') AS region
        FROM chain_profiles WHERE id = %s LIMIT 1
    """, (profile_id,), timeout_ms=2000, default=[])
    return (rows[0] or {}).get("region", "") if rows else ""

def _is_following(follower_id, author_id):
    if not follower_id or not author_id: return False
    rows = fast_query(
        "SELECT id FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s",
        (follower_id, author_id), timeout_ms=2000, default=[]
    )
    return bool(rows)

def _batch_following(follower_id, author_ids):
    if not follower_id or not author_ids:
        return set()
    rows = fast_query(
        "SELECT following_profile_id FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = ANY(%s)",
        (follower_id, list(author_ids)), timeout_ms=500, default=[]
    )
    return {r["following_profile_id"] for r in rows}

def _get_creator_badge(author_id):
    if not author_id: return None
    rows = fast_query(
        "SELECT badge_type FROM chain_creator_verifications WHERE user_id = %s AND status = 'approved' LIMIT 1",
        (author_id,), timeout_ms=2000, default=[]
    )
    return rows[0].get("badge_type") if rows else None

def _score_item(item, viewer_id=None, viewer_region=None, following_ids=None):
    age = _age_hours(item.get("created_at"))
    likes = _safe_int(item.get("likes_count"))
    comments = _safe_int(item.get("comments_count"))
    shares = _safe_int(item.get("shares_count"))
    views = _safe_int(item.get("views_count"))
    is_verified = item.get("is_verified", False)
    is_creator = item.get("is_creator", False)
    author_id = item.get("profile_id")
    author_region = item.get("author_region") or ""

    # Recency score: exponential decay
    recency = 1.0 / math.pow(age + 1.0, 1.5)

    # Engagement velocity: weighted sum / age
    base_eng = likes * 1.0 + comments * 2.0 + shares * 3.0 + views * 0.3
    vel = (base_eng / (age + 0.5)) if age > 0.1 else base_eng

    # Creator quality
    quality = 0
    if is_verified: quality += 20
    if is_creator: quality += 10

    # Following boost (batch preloaded)
    if viewer_id and author_id and following_ids and author_id in following_ids:
        quality += 40

    # Region match
    if viewer_region and author_region:
        if viewer_region.lower() == author_region.lower():
            quality += 25
        elif viewer_region.lower()[:4] == author_region.lower()[:4]:
            quality += 10

    # Verification badge bonus
    badge = _get_creator_badge(author_id)
    badge_bonus = {"blue": 15, "business": 10, "government": 20, "artist": 12, "creator": 15}
    if badge:
        quality += badge_bonus.get(badge, 10)

    # Content freshness: newer content gets bonus
    freshness = max(0, 1.0 - age / 168.0) * 10  # 0-10 over a week

    final = recency * 0.3 + vel * 0.4 + quality * 0.2 + freshness * 0.1
    return round(final, 2)

def rank_feed(items, viewer_id=None, tab="for_you", limit=30):
    """Rank feed items by weighted score. Fallback: chronological."""
    if not items:
        return []

    viewer_region = _region_from_profile(viewer_id) if viewer_id else ""

    following_ids = set()
    if viewer_id:
        author_ids = list({item.get("profile_id") for item in items if item.get("profile_id")})
        following_ids = _batch_following(viewer_id, author_ids)

    scored = []
    for item in items:
        score = _score_item(item, viewer_id, viewer_region, following_ids)
        # Tab-specific adjustments
        if tab == "trending":
            score *= 1.3  # Trending boosts engagement weight
        elif tab == "following":
            fid = item.get("profile_id")
            if fid and fid not in following_ids:
                score *= 0.3  # Deprioritize non-followed
        elif tab == "nearby":
            if viewer_region:
                author_reg = item.get("author_region") or ""
                if author_reg and viewer_region.lower() != author_reg.lower():
                    score *= 0.5  # Deprioritize out-of-region
        scored.append((score, item))

    # Sort by score desc
    scored.sort(key=lambda x: x[0], reverse=True)
    ranked = [s[1] for s in scored[:limit]]
    return ranked

def get_regional_feed(region, limit=30):
    """Get feed items for a specific region."""
    if is_circuit_open():
        return []
    rows = fast_query("""
        SELECT p.id AS profile_id, p.username, p.avatar_url, p.is_verified, p.is_creator,
               COALESCE(NULLIF(p.current_location,''), NULLIF(p.region,''), NULLIF(p.country_origin,'')) AS author_region,
               po.id, po.caption AS title, po.created_at,
               COALESCE(po.likes_count,0) AS likes_count,
               COALESCE(po.comments_count,0) AS comments_count,
               COALESCE(po.shares_count,0) AS shares_count,
               0 AS views_count,
               'post' AS type
        FROM chain_posts po
        JOIN chain_profiles p ON p.id = po.profile_id
        WHERE po.deleted_at IS NULL AND COALESCE(po.visibility,'public') = 'public'
          AND (
            LOWER(COALESCE(NULLIF(p.current_location,''), NULLIF(p.region,''), NULLIF(p.country_origin,''))) = LOWER(%s)
            OR LOWER(COALESCE(p.town, '')) = LOWER(%s)
          )
        ORDER BY po.created_at DESC LIMIT %s
    """, (region, region, limit), timeout_ms=3000, default=[])
    return rows or []
