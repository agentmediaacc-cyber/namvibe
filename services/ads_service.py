"""Phase 157 — Ads Foundation: campaign management, impression/click tracking, feed slot insertion."""

import time
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query

# In-memory dedup: track ad IDs served per viewer in the last N seconds
_AD_SERVE_CACHE = {}
_AD_DEDUP_TTL = 60  # seconds

def _dedup_key(viewer_id):
    bucket = int(time.time() / _AD_DEDUP_TTL)
    return f"ad:{viewer_id}:{bucket}"

def _is_ad_served(ad_id, viewer_id):
    key = _dedup_key(viewer_id)
    served = _AD_SERVE_CACHE.get(key, set())
    return ad_id in served

def _mark_ad_served(ad_id, viewer_id):
    key = _dedup_key(viewer_id)
    if key not in _AD_SERVE_CACHE:
        if len(_AD_SERVE_CACHE) > 1000:
            _AD_SERVE_CACHE.clear()
        _AD_SERVE_CACHE[key] = set()
    _AD_SERVE_CACHE[key].add(ad_id)

def _utcnow():
    return datetime.now(timezone.utc)

def get_active_campaigns(limit=10):
    """Get active ad campaigns eligible for serving."""
    now = _utcnow()
    return fast_query(
        """SELECT * FROM chain_ad_campaigns
           WHERE status = 'active' AND starts_at <= %s AND (ends_at IS NULL OR ends_at > %s)
           ORDER BY created_at DESC LIMIT %s""",
        (now, now, limit),
        timeout_ms=3000,
        default=[]
    )

def get_campaign(campaign_id):
    rows = fast_query("SELECT * FROM chain_ad_campaigns WHERE id = %s", (campaign_id,), timeout_ms=2000, default=[])
    return rows[0] if rows else None

def create_campaign(profile_id, title, content_url, target_url, ad_type="feed",
                    start_date=None, end_date=None, daily_budget=0, total_budget=0,
                    media_id=None, objective=None, media_type="image"):
    from uuid import uuid4
    campaign_id = str(uuid4())
    now = _utcnow()
    try:
        write_query(
            """INSERT INTO chain_ad_campaigns
               (id, owner_id, media_id, title, content_url, target_url, ad_type,
                starts_at, ends_at, budget, status, created_at, objective, media_type)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s, %s, %s)""",
            (campaign_id, profile_id, media_id, title, content_url, target_url, ad_type,
             start_date or now, end_date, total_budget or daily_budget, now,
             objective or ad_type, media_type)
        )
        return {"ok": True, "campaign_id": campaign_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def record_impression(campaign_id, profile_id=None):
    try:
        write_query(
            "INSERT INTO chain_ad_impressions (campaign_id, profile_id) VALUES (%s, %s)",
            (campaign_id, profile_id)
        )
        return True
    except Exception:
        return False

def record_click(campaign_id, profile_id=None):
    try:
        write_query(
            "INSERT INTO chain_ad_clicks (campaign_id, profile_id) VALUES (%s, %s)",
            (campaign_id, profile_id)
        )
        return True
    except Exception:
        return False

def get_campaign_stats(campaign_id):
    impressions = fast_query(
        "SELECT COUNT(*) as count FROM chain_ad_impressions WHERE campaign_id = %s",
        (campaign_id,), timeout_ms=2000, default=[{"count": 0}]
    )[0]["count"]
    clicks = fast_query(
        "SELECT COUNT(*) as count FROM chain_ad_clicks WHERE campaign_id = %s",
        (campaign_id,), timeout_ms=2000, default=[{"count": 0}]
    )[0]["count"]
    return {"impressions": impressions, "clicks": clicks}

def get_ads_for_feed(viewer_id=None, slot_count=2):
    """Get ads to inject into feed ranking slots. Dedup'd per viewer per 60s window."""
    campaigns = get_active_campaigns(limit=slot_count * 3)
    ads = []
    for c in campaigns:
        if _is_ad_served(c["id"], viewer_id):
            continue
        _mark_ad_served(c["id"], viewer_id)
        ads.append({
            "id": c["id"],
            "type": "ad",
            "ad_type": c.get("ad_type", "feed"),
            "title": c.get("title", "Sponsored"),
            "body": c.get("objective", "Promoted content"),
            "objective": c.get("objective"),
            "media_type": c.get("media_type", "image"),
            "content_url": c.get("content_url", ""),
            "target_url": c.get("target_url", ""),
            "campaign_id": c["id"],
            "profile_id": c.get("owner_id") or c.get("profile_id"),
            "is_ad": True,
            "sponsored": True,
        })
        if len(ads) >= slot_count:
            break
    for ad in ads:
        record_impression(ad["campaign_id"], viewer_id)
    return ads
