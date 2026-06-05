from services.supabase_safe import safe_select
from services.content_service import create_post_record, local_content

def create_post(profile_id, caption, media_file=None, link_url="", town_tag="", visibility="public"):
    """
    Creates a new post for a profile using validated local media storage and
    Neon persistence, with a fast-local fallback for test mode.
    """
    return create_post_record(profile_id, caption, media_file, link_url=link_url, town_tag=town_tag, visibility=visibility)

def get_posts_by_profile(profile_id, limit=20):
    rows = safe_select("chain_posts", filters={"profile_id": profile_id}, limit=limit, order_by="created_at", desc=True)
    if rows:
        return rows
    return [post for post in local_content()["posts"] if post.get("profile_id") == profile_id][:limit]
