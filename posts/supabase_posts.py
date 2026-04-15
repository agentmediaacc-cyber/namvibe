import os
import uuid
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

def save_media_locally(file_obj, folder="posts"):
    if not file_obj:
        return ""
    ext = os.path.splitext(file_obj.name)[1] or ""
    filename = f"{uuid.uuid4().hex}{ext}"
    save_dir = os.path.join("media", folder)
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, filename)

    with open(file_path, "wb+") as out:
        for chunk in file_obj.chunks():
            out.write(chunk)

    return f"/media/{folder}/{filename}"

def create_post(post_data):
    url = f"{SUPABASE_URL}/rest/v1/posts"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    return requests.post(url, headers=headers, json=post_data, timeout=30)

def get_posts_by_user(user_id):
    url = f"{SUPABASE_URL}/rest/v1/posts"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }
    params = {
        "select": "*",
        "user_id": f"eq.{user_id}",
        "order": "created_at.desc",
    }
    return requests.get(url, headers=headers, params=params, timeout=30)

def get_public_posts(limit=20):
    url = f"{SUPABASE_URL}/rest/v1/posts"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }
    params = {
        "select": "*",
        "audience": "eq.Public",
        "status": "eq.published",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    return requests.get(url, headers=headers, params=params, timeout=30)
