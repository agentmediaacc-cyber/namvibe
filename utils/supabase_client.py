import os
from functools import lru_cache
from supabase import create_client

from services.env_service import get_env, load_project_env

load_project_env()

SUPABASE_URL = get_env("SUPABASE_URL")
SUPABASE_ANON_KEY = get_env("SUPABASE_ANON_KEY") or get_env("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = get_env("SUPABASE_SERVICE_ROLE_KEY")

@lru_cache(maxsize=1)
def get_supabase():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY in .env")
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

@lru_cache(maxsize=1)
def get_supabase_admin():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
