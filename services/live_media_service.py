from datetime import datetime, timezone
from services.supabase_safe import safe_update, safe_select
from services.storage_service import upload_live_music, upload_live_cover

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

def update_live_room_media(room_id, profile_id, data, files):
    # Verify ownership
    room = safe_select("chain_live_rooms", filters={"id": room_id}, limit=1)
    if not room or (room[0].get('host_profile_id') != profile_id and room[0].get('profile_id') != profile_id):
        return None, "Unauthorized."

    payload = {
        "title": data.get("title", room[0].get("title")),
        "stream_mode": data.get("stream_mode", room[0].get("stream_mode", "camera")),
        "allow_camera": data.get("allow_camera") == 'on',
        "allow_microphone": data.get("allow_microphone") == 'on',
        "allow_screen_share": data.get("allow_screen_share") == 'on',
        "allow_youtube_embed": data.get("allow_youtube_embed") == 'on',
        "allow_mp3_music": data.get("allow_mp3_music") == 'on',
        "updated_at": _utcnow_iso()
    }
    
    # Handle cover upload if present
    cover_file = files.get("live_cover")
    if cover_file:
        res, err = upload_live_cover(profile_id, cover_file)
        if res:
            payload["cover_url"] = res["url"]
            payload["live_cover_upload_id"] = res["upload_id"]
            payload["cover_bucket"] = res.get("bucket")
            payload["cover_path"] = res.get("path")
            payload["cover_mime_type"] = res.get("mime_type")
            payload["cover_size_bytes"] = res.get("size_bytes")
            payload["media_bucket"] = res.get("bucket")
            payload["media_path"] = res.get("path")
            payload["mime_type"] = res.get("mime_type")
            payload["size_bytes"] = res.get("size_bytes")

    updated = safe_update("chain_live_rooms", payload, eq={"id": room_id})
    return updated[0] if updated else None, None

def attach_mp3_to_live(room_id, profile_id, file):
    if not file:
        return None, "No file provided."
        
    res, err = upload_live_music(profile_id, file)
    if not res:
        return None, f"Upload failed: {err}"
        
    payload = {
        "background_music_url": res["public_url"],
        "background_music_upload_id": res["upload_id"],
        "mp3_url": res["public_url"], # Legacy compatibility
        "updated_at": _utcnow_iso()
    }
    updated = safe_update("chain_live_rooms", payload, eq={"id": room_id})
    return updated[0] if updated else None, None

def set_youtube_embed(room_id, profile_id, youtube_url):
    from services.live_service import youtube_id
    video_id = youtube_id(youtube_url)
    if not video_id:
        return None, "Invalid YouTube URL."
        
    payload = {
        "youtube_url": youtube_url,
        "youtube_video_id": video_id,
        "youtube_embed_url": f"https://www.youtube.com/embed/{video_id}",
        "updated_at": _utcnow_iso()
    }
    updated = safe_update("chain_live_rooms", payload, eq={"id": room_id})
    return updated[0] if updated else None, None

def toggle_comments_gifts(room_id, profile_id, comments_enabled, gifts_enabled):
    payload = {
        "comments_enabled": bool(comments_enabled),
        "gifts_enabled": bool(gifts_enabled),
        "updated_at": _utcnow_iso()
    }
    updated = safe_update("chain_live_rooms", payload, eq={"id": room_id})
    return updated[0] if updated else None, None
