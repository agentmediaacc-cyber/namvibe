"""Location privacy service - opt-in live location sharing."""
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query
from services.logging_service import log_info
import json

def get_location_settings(profile_id):
    rows = fast_query(
        "SELECT * FROM chain_location_sharing WHERE profile_id = %s",
        (profile_id,), default=[]
    )
    if not rows:
        return {"is_sharing": False, "authorized_viewers": [], "latitude": None, "longitude": None}
    r = rows[0]
    viewers = r.get("authorized_viewers")
    if isinstance(viewers, str):
        viewers = json.loads(viewers)
    return {
        "is_sharing": bool(r.get("is_sharing", False)),
        "authorized_viewers": viewers or [],
        "latitude": r.get("latitude"),
        "longitude": r.get("longitude"),
    }

def start_sharing(profile_id, latitude, longitude, authorized_viewers=None):
    authorized_viewers = authorized_viewers or []
    write_query(
        """INSERT INTO chain_location_sharing (id, profile_id, is_sharing, latitude, longitude, authorized_viewers)
           VALUES (gen_random_uuid(), %s, TRUE, %s, %s, %s::jsonb)
           ON CONFLICT (profile_id) DO UPDATE SET is_sharing = TRUE, latitude = %s, longitude = %s, 
           authorized_viewers = %s::jsonb, updated_at = now()""",
        (profile_id, latitude, longitude, json.dumps(authorized_viewers),
         latitude, longitude, json.dumps(authorized_viewers))
    )
    log_info("location_sharing_started", profile_id=profile_id)
    return {"ok": True}

def stop_sharing(profile_id):
    write_query(
        "UPDATE chain_location_sharing SET is_sharing = FALSE, updated_at = now() WHERE profile_id = %s",
        (profile_id,)
    )
    log_info("location_sharing_stopped", profile_id=profile_id)
    return {"ok": True}

def update_location(profile_id, latitude, longitude):
    write_query(
        "UPDATE chain_location_sharing SET latitude = %s, longitude = %s, updated_at = now() WHERE profile_id = %s",
        (latitude, longitude, profile_id)
    )
    return {"ok": True}

def is_authorized_viewer(profile_id, viewer_id):
    settings = get_location_settings(profile_id)
    if not settings["is_sharing"]:
        return False
    return str(viewer_id) in [str(v) for v in settings["authorized_viewers"]]
