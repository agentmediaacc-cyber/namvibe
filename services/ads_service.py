"""Phase 157 — Ads Foundation: campaign management, impression/click tracking, feed slot insertion."""

from datetime import datetime, timezone
from services.neon_service import fast_query, write_query

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
                    start_date=None, end_date=None, daily_budget=0, total_budget=0, media_id=None):
    from uuid import uuid4
    campaign_id = str(uuid4())
    now = _utcnow()
    try:
        write_query(
            """INSERT INTO chain_ad_campaigns
               (id, owner_id, media_id, title, content_url, target_url, ad_type,
                starts_at, ends_at, budget, status, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', %s)""",
            (campaign_id, profile_id, media_id, title, content_url, target_url, ad_type,
             start_date or now, end_date, total_budget or daily_budget, now)
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
    """Get ads to inject into feed ranking slots. Marked 'Sponsored'."""
    campaigns = get_active_campaigns(limit=slot_count)
    ads = []
    for c in campaigns:
        ads.append({
            "id": c["id"],
            "type": "ad",
            "ad_type": c.get("ad_type", "feed"),
            "title": c.get("title", "Sponsored"),
            "content_url": c.get("content_url", ""),
            "target_url": c.get("target_url", ""),
            "campaign_id": c["id"],
            "profile_id": c.get("owner_id") or c.get("profile_id"),
            "is_ad": True,
            "sponsored": True,
        })
        record_impression(c["id"], viewer_id)
    return ads
