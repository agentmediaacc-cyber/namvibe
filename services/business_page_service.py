"""Business page and advertising service."""
import uuid
import json
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query
from services.logging_service import log_info

def get_business_profile(profile_id):
    rows = fast_query(
        "SELECT id, username, display_name, full_name, avatar_url, cover_url, bio, "
        "business_name, business_category, business_description, business_website, "
        "business_services, business_products, location, town, country, phone, email, "
        "show_phone_publicly, show_email_publicly, is_verified, followers_count "
        "FROM chain_profiles WHERE id = %s AND (profile_type = 'business' OR business_name IS NOT NULL)",
        (profile_id,), default=[]
    )
    if not rows:
        return None
    p = rows[0]
    hours = fast_query(
        "SELECT hours FROM chain_business_hours WHERE profile_id = %s",
        (profile_id,), default=[]
    )
    p["opening_hours"] = hours[0]["hours"] if hours else {}
    p["services"] = p.get("business_services") or []
    p["products"] = p.get("business_products") or []
    return p

def update_business_profile(profile_id, **kwargs):
    allowed = {"business_name", "business_category", "business_description",
               "business_website", "business_services", "business_products",
               "show_phone_publicly", "show_email_publicly"}
    safe = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if safe:
        sets = ", ".join(f'"{k}" = %s' for k in safe)
        vals = list(safe.values()) + [profile_id]
        write_query(f"UPDATE chain_profiles SET {sets} WHERE id = %s", vals)
    if "opening_hours" in kwargs:
        write_query(
            "INSERT INTO chain_business_hours (id, profile_id, hours) VALUES (gen_random_uuid(), %s, %s::jsonb) "
            "ON CONFLICT (profile_id) DO UPDATE SET hours = %s::jsonb, updated_at = now()",
            (profile_id, kwargs["opening_hours"], kwargs["opening_hours"])
        )
    return {"ok": True}

def create_campaign(profile_id, name, objective="reach", media_url=None, media_type="image",
                    target_audience=None, budget=0, start_date=None, end_date=None):
    if objective not in ("reach", "website_clicks", "profile_visits", "followers"):
        return {"ok": False, "error": "Invalid objective."}
    cid = str(uuid.uuid4())
    try:
        write_query(
            """INSERT INTO chain_ad_campaigns 
               (id, profile_id, name, objective, media_url, media_type, target_audience, budget, start_date, end_date, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, 'pending')""",
            (cid, profile_id, name, objective, media_url, media_type,
             json.dumps(target_audience or {}), budget, start_date, end_date)
        )
        return {"ok": True, "campaign_id": cid}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_campaigns(profile_id, limit=20):
    rows = fast_query(
        "SELECT * FROM chain_ad_campaigns WHERE profile_id = %s ORDER BY created_at DESC LIMIT %s",
        (profile_id, limit), default=[]
    )
    return rows

def get_all_campaigns(limit=50):
    rows = fast_query(
        """SELECT c.*, p.username, p.display_name, p.avatar_url 
           FROM chain_ad_campaigns c JOIN chain_profiles p ON c.profile_id = p.id 
           ORDER BY c.created_at DESC LIMIT %s""",
        (limit,), default=[]
    )
    return rows

def approve_campaign(campaign_id):
    write_query("UPDATE chain_ad_campaigns SET status = 'active', is_sponsored = TRUE WHERE id = %s", (campaign_id,))
    return {"ok": True}

def reject_campaign(campaign_id):
    write_query("UPDATE chain_ad_campaigns SET status = 'rejected' WHERE id = %s", (campaign_id,))
    return {"ok": True}

def pause_campaign(campaign_id, profile_id):
    write_query("UPDATE chain_ad_campaigns SET status = 'paused' WHERE id = %s AND profile_id = %s",
               (campaign_id, profile_id))
    return {"ok": True}

def track_campaign_metric(campaign_id, metric="impressions", count=1):
    col = metric if metric in ("impressions", "clicks", "reach", "engagement") else "impressions"
    write_query(f"UPDATE chain_ad_campaigns SET {col} = COALESCE({col}, 0) + %s WHERE id = %s", (count, campaign_id))
