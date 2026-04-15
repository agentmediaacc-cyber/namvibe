import os
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

def _headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

def create_live_room(payload):
    url = f"{SUPABASE_URL}/rest/v1/live_rooms"
    return requests.post(url, headers=_headers(), json=payload, timeout=30)

def list_live_rooms(limit=20, only_live=False):
    url = f"{SUPABASE_URL}/rest/v1/live_rooms"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }
    params = {
        "select": "*",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    if only_live:
        params["status"] = "eq.live"
    return requests.get(url, headers=headers, params=params, timeout=30)

def get_live_room(room_id):
    url = f"{SUPABASE_URL}/rest/v1/live_rooms"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }
    params = {
        "select": "*",
        "id": f"eq.{room_id}",
        "limit": "1",
    }
    return requests.get(url, headers=headers, params=params, timeout=30)

def update_live_room(room_id, payload):
    url = f"{SUPABASE_URL}/rest/v1/live_rooms?id=eq.{room_id}"
    return requests.patch(url, headers=_headers(), json=payload, timeout=30)

def create_live_comment(payload):
    url = f"{SUPABASE_URL}/rest/v1/live_comments"
    return requests.post(url, headers=_headers(), json=payload, timeout=30)

def list_live_comments(room_id, limit=50):
    url = f"{SUPABASE_URL}/rest/v1/live_comments"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }
    params = {
        "select": "*",
        "room_id": f"eq.{room_id}",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    return requests.get(url, headers=headers, params=params, timeout=30)

def create_live_gift(payload):
    url = f"{SUPABASE_URL}/rest/v1/live_gifts"
    return requests.post(url, headers=_headers(), json=payload, timeout=30)

def list_live_gifts(room_id, limit=30):
    url = f"{SUPABASE_URL}/rest/v1/live_gifts"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }
    params = {
        "select": "*",
        "room_id": f"eq.{room_id}",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    return requests.get(url, headers=headers, params=params, timeout=30)
