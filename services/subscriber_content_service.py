"""Locked gallery and subscriber content service."""
from services.neon_service import fast_query, write_query, get_cached_table_columns
from services.logging_service import log_info

def _has_column(table, column):
    cols = get_cached_table_columns(table)
    return cols is not None and column in cols

def can_access_content(viewer_id, owner_id, access_level="subscribers"):
    if viewer_id and str(viewer_id) == str(owner_id):
        return True
    if access_level == "public":
        return True
    if access_level == "followers":
        if not viewer_id:
            return False
        rows = fast_query(
            "SELECT 1 FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s LIMIT 1",
            (viewer_id, owner_id), default=[]
        )
        return bool(rows)
    if access_level in ("subscribers",):
        if not viewer_id:
            return False
        rows = fast_query(
            "SELECT 1 FROM chain_subscriptions WHERE subscriber_id = %s AND creator_id = %s AND status = 'active' LIMIT 1",
            (viewer_id, owner_id), default=[]
        )
        return bool(rows)
    return False

def get_media_access_level(media_id, profile_id=None):
    if _has_column("chain_media_uploads", "visibility"):
        rows = fast_query(
            "SELECT visibility FROM chain_media_uploads WHERE id = %s",
            (media_id,), default=[]
        )
        if rows:
            return rows[0].get("visibility", "public")
    if _has_column("chain_posts", "visibility"):
        rows = fast_query("SELECT visibility FROM chain_posts WHERE id = %s", (media_id,), default=[])
        if rows:
            return rows[0].get("visibility", "public")
    if _has_column("chain_reels", "visibility"):
        rows = fast_query("SELECT visibility FROM chain_reels WHERE id = %s", (media_id,), default=[])
        if rows:
            return rows[0].get("visibility", "public")
    rows = fast_query(
        "SELECT access_level FROM chain_subscriber_content WHERE media_id = %s",
        (media_id,), default=[]
    )
    if rows:
        return rows[0].get("access_level", "subscribers")
    return "public"

def check_media_access(viewer_id, media_id, owner_id):
    access_level = get_media_access_level(media_id, owner_id)
    can_view = can_access_content(viewer_id, owner_id, access_level)
    return {
        "can_view": can_view,
        "access_level": access_level,
        "needs_subscription": access_level == "subscribers" and not can_view,
        "needs_follow": access_level == "followers" and not can_view
    }

def set_media_access_level(media_id, profile_id, access_level):
    if access_level not in ("public", "followers", "private", "subscribers"):
        return {"ok": False, "error": "Invalid access level."}
    updated_any = False
    for table in ["chain_media_uploads", "chain_posts", "chain_reels"]:
        if _has_column(table, "visibility"):
            write_query(
                f"UPDATE {table} SET visibility = %s WHERE id = %s AND profile_id = %s",
                (access_level, media_id, profile_id)
            )
            updated_any = True
    if not updated_any:
        return {"ok": False, "error": "No content table with visibility column found; cannot set access level."}
    write_query(
        """INSERT INTO chain_subscriber_content (id, profile_id, media_id, access_level) 
           VALUES (gen_random_uuid(), %s, %s, %s)
           ON CONFLICT DO NOTHING""",
        (profile_id, media_id, access_level)
    )
    return {"ok": True}

def get_locked_content(profile_id, viewer_id=None):
    if viewer_id and str(viewer_id) == str(profile_id):
        rows = fast_query(
            "SELECT sc.*, mu.public_url, mu.media_type, mu.mime_type "
            "FROM chain_subscriber_content sc "
            "LEFT JOIN chain_media_uploads mu ON sc.media_id = mu.id "
            "WHERE sc.profile_id = %s ORDER BY sc.created_at DESC",
            (profile_id,), default=[]
        )
        return rows
    can_view = can_access_content(viewer_id, profile_id, "subscribers")
    if can_view:
        rows = fast_query(
            "SELECT sc.*, mu.public_url, mu.media_type, mu.mime_type "
            "FROM chain_subscriber_content sc "
            "LEFT JOIN chain_media_uploads mu ON sc.media_id = mu.id "
            "WHERE sc.profile_id = %s AND sc.access_level = 'subscribers' ORDER BY sc.created_at DESC",
            (profile_id,), default=[]
        )
        return rows
    rows = fast_query(
        "SELECT sc.id, sc.thumbnail_url, sc.content_type, sc.access_level "
        "FROM chain_subscriber_content sc "
        "WHERE sc.profile_id = %s AND sc.access_level = 'subscribers' ORDER BY sc.created_at DESC",
        (profile_id,), default=[]
    )
    return rows
