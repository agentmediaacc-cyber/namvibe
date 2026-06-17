"""Explore page routes — trending, videos, creators, businesses, hashtags, regions."""
from flask import Blueprint, render_template, request, jsonify
from services.profile_service import get_current_profile
from services.neon_service import fast_query
from datetime import datetime, timezone

explore_bp = Blueprint("explore", __name__, url_prefix="/explore")

def _time_ago(dt):
    if not dt: return ""
    try:
        d = datetime.fromisoformat(str(dt).replace("Z", "+00:00"))
        diff = (datetime.now(timezone.utc) - d).total_seconds()
        if diff < 60: return "just now"
        if diff < 3600: return f"{int(diff//60)}m"
        if diff < 86400: return f"{int(diff//3600)}h"
        return f"{int(diff//86400)}d"
    except: return ""

def _get_trending(limit=15):
    return fast_query("""
        SELECT po.*, p.username, p.avatar_url, p.is_verified,
               COALESCE(po.likes_count,0) AS likes_count,
               COALESCE(po.comments_count,0) AS comments_count,
               COALESCE(po.shares_count,0) AS shares_count
        FROM chain_posts po
        JOIN chain_profiles p ON p.id = po.profile_id
        WHERE po.deleted_at IS NULL AND COALESCE(po.visibility,'public') = 'public'
        ORDER BY (COALESCE(po.likes_count,0) + COALESCE(po.comments_count,0)*2 + COALESCE(po.shares_count,0)*3) DESC
        LIMIT %s
    """, (limit,), timeout_ms=3000, default=[]) or []

def _get_videos(limit=12):
    return fast_query("""
        SELECT r.*, p.username, p.avatar_url
        FROM chain_reels r
        JOIN chain_profiles p ON r.profile_id = p.id
        WHERE r.status = 'published' AND r.visibility = 'public'
          AND r.processing_status = 'ready' AND r.deleted_at IS NULL
        ORDER BY COALESCE(r.views_count,0) DESC
        LIMIT %s
    """, (limit,), timeout_ms=3000, default=[]) or []

def _get_creators(limit=12):
    return fast_query("""
        SELECT p.id, p.username, p.avatar_url, p.bio, p.is_verified, p.followers_count
        FROM chain_profiles p
        WHERE p.deleted_at IS NULL
          AND (p.is_creator = TRUE OR p.is_verified = TRUE)
          AND p.id NOT IN (SELECT id FROM chain_profiles WHERE is_test = TRUE OR username ILIKE '%test%' OR username ILIKE '%debug%')
        ORDER BY p.followers_count DESC NULLS LAST
        LIMIT %s
    """, (limit,), timeout_ms=3000, default=[]) or []

def _get_businesses(limit=12):
    return fast_query("""
        SELECT p.id, p.username, p.full_name, p.avatar_url, p.bio, p.is_verified, p.followers_count
        FROM chain_profiles p
        WHERE p.deleted_at IS NULL AND p.is_creator = TRUE
          AND p.username NOT ILIKE '%test%' AND p.username NOT ILIKE '%debug%'
        ORDER BY p.followers_count DESC NULLS LAST
        LIMIT %s
    """, (limit,), timeout_ms=3000, default=[]) or []

def _get_hashtags(limit=15):
    rows = fast_query("""
        SELECT regexp_matches(LOWER(COALESCE(po.caption,'') || ' ' || COALESCE(po.body,'')), '#([a-z0-9_]+)', 'g') AS tag
        FROM chain_posts po
        WHERE po.deleted_at IS NULL
    """, timeout_ms=5000, default=[])
    counts = {}
    for row in rows:
        t = row.get("tag")
        if t and isinstance(t, list):
            tag = t[0].lower()
            if tag not in ("test", "debug", "chainlive", "chain", "namvibe"):
                counts[tag] = counts.get(tag, 0) + 1
    sorted_tags = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [{"tag": t, "count": c} for t, c in sorted_tags]

def _get_regions():
    return fast_query("SELECT * FROM chain_regions ORDER BY name ASC", timeout_ms=3000, default=[]) or []

@explore_bp.route("")
@explore_bp.route("/")
def index():
    profile = get_current_profile()
    tab = request.args.get("tab", "trending")
    region_slug = request.args.get("region")
    query = request.args.get("q", "")

    trending = _get_trending() if tab == "trending" else []
    videos = _get_videos()
    creators = _get_creators()
    businesses = _get_businesses()
    hashtags = _get_hashtags()
    regions = _get_regions()

    active_region = None
    if region_slug:
        for r in regions:
            if r.get("slug") == region_slug:
                active_region = region_slug
                if tab == "trending":
                    trending = [p for p in trending if p.get("author_region", "").lower() == r.get("name", "").lower()]
                break

    return render_template("explore.html",
        profile=profile, current=profile,
        tab=tab, query=query,
        trending=trending, videos=videos, creators=creators,
        businesses=businesses, hashtags=hashtags,
        regions=regions, active_region=active_region,
        time_ago=_time_ago
    )
