"""Profile and content sharing service."""
from services.neon_service import fast_query
from services.logging_service import log_info

SHARE_TYPES = {"profile", "business_page", "creator_page", "album", "post", "reel"}

def get_share_data(entity_type, entity_id):
    if entity_type not in SHARE_TYPES:
        return None
    if entity_type == "profile":
        rows = fast_query(
            "SELECT id, username, display_name, avatar_url, bio, is_verified FROM chain_profiles WHERE id = %s",
            (entity_id,), default=[]
        )
        if not rows:
            return None
        p = rows[0]
        return {
            "type": "profile",
            "title": p.get("display_name") or p.get("username"),
            "description": p.get("bio", ""),
            "image": p.get("avatar_url"),
            "url": f"/profile/@{p['username']}",
            "username": p["username"]
        }
    if entity_type == "post":
        rows = fast_query(
            """SELECT p.id, p.body, p.caption, p.media_url, p.created_at,
               pr.username, pr.display_name
               FROM chain_posts p JOIN chain_profiles pr ON p.profile_id = pr.id
               WHERE p.id = %s""",
            (entity_id,), default=[]
        )
        if not rows:
            return None
        r = rows[0]
        return {
            "type": "post",
            "title": f"Post by {r.get('display_name') or r.get('username')}",
            "description": (r.get("caption") or r.get("body") or "")[:200],
            "image": r.get("media_url"),
            "url": f"/post/{r['id']}",
            "username": r["username"]
        }
    if entity_type == "reel":
        rows = fast_query(
            """SELECT r.id, r.caption, r.thumbnail_url, r.video_url,
               pr.username, pr.display_name
               FROM chain_reels r JOIN chain_profiles pr ON r.profile_id = pr.id
               WHERE r.id = %s""",
            (entity_id,), default=[]
        )
        if not rows:
            return None
        r = rows[0]
        return {
            "type": "reel",
            "title": f"Reel by {r.get('display_name') or r.get('username')}",
            "description": (r.get("caption") or "")[:200],
            "image": r.get("thumbnail_url") or r.get("video_url"),
            "url": f"/reels/{r['id']}",
            "username": r["username"]
        }
    if entity_type in ("album", "business_page", "creator_page"):
        return {
            "type": entity_type,
            "title": entity_type.replace("_", " ").title(),
            "description": "",
            "image": None,
            "url": f"/{entity_type}/{entity_id}"
        }
    return None
