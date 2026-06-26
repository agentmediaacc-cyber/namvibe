from services.supabase_safe import safe_select, safe_update, safe_delete
from services.content_service import create_post_record, local_content

def create_post(profile_id, caption, media_file=None, link_url="", town_tag="", visibility="public",
                music_url="", music_title="", music_artist="", music_start_seconds=0, music_duration_seconds=0):
    return create_post_record(profile_id, caption, media_file, link_url=link_url, town_tag=town_tag, visibility=visibility,
                              music_url=music_url, music_title=music_title, music_artist=music_artist,
                              music_start_seconds=music_start_seconds, music_duration_seconds=music_duration_seconds)

def edit_post(post_id, profile_id, caption=None, visibility=None):
    updates = {}
    if caption is not None:
        updates["caption"] = caption
    if visibility is not None:
        updates["visibility"] = visibility
    if not updates:
        return {"ok": False, "error": "nothing_to_update"}
    updates["updated_at"] = "now()"
    ok = safe_update("chain_posts", updates, filters={"id": post_id, "profile_id": profile_id})
    if ok:
        return {"ok": True}
    local = local_content().get("posts", [])
    for post in local:
        if post.get("id") == post_id and str(post.get("profile_id")) == str(profile_id):
            if caption is not None:
                post["caption"] = caption
            if visibility is not None:
                post["visibility"] = visibility
            post["updated_at"] = "now()"
            return {"ok": True}
    return {"ok": False, "error": "not_found_or_unauthorized"}

def delete_post(post_id, profile_id):
    ok = safe_delete("chain_posts", filters={"id": post_id, "profile_id": profile_id})
    if ok:
        return {"ok": True}
    local = local_content().get("posts", [])
    for i, post in enumerate(local):
        if post.get("id") == post_id and str(post.get("profile_id")) == str(profile_id):
            local.pop(i)
            return {"ok": True}
    return {"ok": False, "error": "not_found_or_unauthorized"}

def get_posts_by_profile(profile_id, limit=20):
    rows = safe_select("chain_posts", filters={"profile_id": profile_id}, limit=limit, order_by="created_at", desc=True)
    if rows:
        return rows
    return [post for post in local_content()["posts"] if post.get("profile_id") == profile_id][:limit]
