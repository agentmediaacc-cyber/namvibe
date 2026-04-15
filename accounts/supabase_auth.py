import os
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

def signup_user(email, password, full_name="", username="", phone=""):
    url = f"{SUPABASE_URL}/auth/v1/signup"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "email": email,
        "password": password,
        "data": {
            "full_name": full_name,
            "username": username,
            "phone": phone,
        }
    }
    return requests.post(url, headers=headers, json=payload, timeout=30)

def login_user(email, password):
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "email": email,
        "password": password,
    }
    return requests.post(url, headers=headers, json=payload, timeout=30)

def get_profile_by_user_id(user_id):
    url = f"{SUPABASE_URL}/rest/v1/profiles"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }
    params = {
        "select": "id,email,username,full_name,phone",
        "id": f"eq.{user_id}",
        "limit": "1",
    }
    return requests.get(url, headers=headers, params=params, timeout=30)

def _profile_lookup(field, value):
    url = f"{SUPABASE_URL}/rest/v1/profiles"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }
    params = {
        "select": field,
        field: f"eq.{value}",
        "limit": "1",
    }
    response = requests.get(url, headers=headers, params=params, timeout=30)
    if response.ok:
        data = response.json()
        return len(data) > 0
    return False

def username_exists(username):
    return _profile_lookup("username", username)

def email_exists(email):
    return _profile_lookup("email", email)

def phone_exists(phone):
    return _profile_lookup("phone", phone)
