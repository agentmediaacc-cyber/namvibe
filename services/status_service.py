from datetime import datetime, timezone, timedelta
import uuid
from services.neon_service import fast_query, write_query
from services.storage_service import upload_status_media
from services.socketio_service import emit_to_profile
from services.content_service import invalidate_content_caches, local_content, local_fallback_allowed

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def create_status(profile_id, caption, media_file=None, visibility="public", media_type="image"):
    media_url = None
    storage_bucket = None
    storage_path = None
    
    if media_file:
        res, error = upload_status_media(media_file, profile_id)
        if res:
            media_url = res.get("public_url")
            storage_bucket = res.get("bucket")
            storage_path = res.get("file_path")
            
    status_id = str(uuid.uuid4())
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    
    sql = """
        INSERT INTO chain_status_posts (id, profile_id, caption, media_url, media_type, storage_bucket, storage_path, visibility, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    try:
        write_query(sql, (status_id, profile_id, caption, media_url, media_type, storage_bucket, storage_path, visibility, expires_at))
        record = {
            "id": status_id,
            "profile_id": profile_id,
            "caption": caption,
            "media_url": media_url,
            "media_type": media_type,
            "visibility": visibility,
            "expires_at": expires_at
        }
        invalidate_content_caches()
        return record
    except Exception as e:
        print(f"[status_service] Error creating status: {e}")
        if local_fallback_allowed():
            record = {
                "id": status_id,
                "profile_id": profile_id,
                "caption": caption,
                "media_url": media_url,
                "media_type": media_type,
                "visibility": visibility,
                "expires_at": expires_at,
                "created_at": _utcnow_iso(),
            }
            local_content()["stories"].insert(0, record)
            invalidate_content_caches()
            return record
        return None

def record_view(status_id, viewer_profile_id):
    sql = "INSERT INTO chain_status_viewers (status_id, viewer_profile_id) VALUES (%s, %s) ON CONFLICT DO NOTHING"
    write_query(sql, (status_id, viewer_profile_id))
    
    # Notify status owner
    status = get_status(status_id)
    if status and str(status['profile_id']) != str(viewer_profile_id):
        emit_to_profile(status['profile_id'], "status:viewed", {
            "status_id": status_id,
            "viewer_id": viewer_profile_id
        })
    return True

def list_viewers(status_id):
    sql = """
        SELECT v.*, p.username, p.avatar_url, p.full_name
        FROM chain_status_viewers v
        JOIN chain_profiles p ON v.viewer_profile_id = p.id
        WHERE v.status_id = %s
        ORDER BY v.viewed_at DESC
    """
    return fast_query(sql, (status_id,))

def list_active_statuses(profile_id=None, viewer_profile_id=None):
    now = _utcnow_iso()
    
    # Base query for all active statuses
    sql = """
        SELECT s.*, p.username, p.avatar_url,
               (SELECT COUNT(*) FROM chain_status_viewers WHERE status_id = s.id) as viewer_count
        FROM chain_status_posts s
        JOIN chain_profiles p ON s.profile_id = p.id
        WHERE s.expires_at > %s AND s.deleted_at IS NULL
    """
    params = [now]
    
    if profile_id:
        # Looking at a specific profile's statuses
        sql += " AND s.profile_id = %s"
        params.append(profile_id)
        
        if viewer_profile_id and str(profile_id) != str(viewer_profile_id):
            # Check visibility for the viewer
            sql += """ AND (
                s.visibility = 'public'
                OR (s.visibility = 'contacts' AND EXISTS (
                    SELECT 1 FROM chain_follows f1 
                    JOIN chain_follows f2 ON f1.follower_profile_id = f2.following_profile_id 
                    AND f1.following_profile_id = f2.follower_profile_id
                    WHERE f1.follower_profile_id = s.profile_id AND f1.following_profile_id = %s
                ))
                OR (s.visibility = 'close_friends' AND EXISTS (
                    SELECT 1 FROM chain_close_friends 
                    WHERE profile_id = s.profile_id AND friend_profile_id = %s
                ))
            )"""
            params.extend([viewer_profile_id, viewer_profile_id])
    else:
        # Feed view - statuses from people viewer follows or public
        if viewer_profile_id:
            sql += """ AND (
                s.profile_id = %s
                OR s.visibility = 'public'
                OR (s.profile_id IN (SELECT following_profile_id FROM chain_follows WHERE follower_profile_id = %s) AND (
                    s.visibility = 'public'
                    OR (s.visibility = 'contacts' AND EXISTS (
                        SELECT 1 FROM chain_follows f 
                        WHERE f.follower_profile_id = s.profile_id AND f.following_profile_id = %s
                    ))
                    OR (s.visibility = 'close_friends' AND EXISTS (
                        SELECT 1 FROM chain_close_friends 
                        WHERE profile_id = s.profile_id AND friend_profile_id = %s
                    ))
                ))
            )"""
            params.extend([viewer_profile_id, viewer_profile_id, viewer_profile_id, viewer_profile_id])
        else:
            sql += " AND s.visibility = 'public'"
        
    sql += " ORDER BY s.created_at DESC LIMIT 50"
    return fast_query(sql, tuple(params))

def get_status(status_id):
    rows = fast_query("SELECT * FROM chain_status_posts WHERE id = %s", (status_id,))
    if rows:
        return rows[0]
    for story in local_content()["stories"]:
        if story.get("id") == status_id:
            return story
    return None

def delete_status(status_id, profile_id):
    sql = "UPDATE chain_status_posts SET deleted_at = now() WHERE id = %s AND profile_id = %s"
    write_query(sql, (status_id, profile_id))
    # Also handle local content removal if it was a local story
    local_content()["stories"][:] = [story for story in local_content()["stories"] if not (story.get("id") == status_id and story.get("profile_id") == profile_id)]
    invalidate_content_caches()
    return True

def expire_old_statuses():
    sql = "UPDATE chain_status_posts SET deleted_at = now() WHERE expires_at < now() AND deleted_at IS NULL"
    write_query(sql)
