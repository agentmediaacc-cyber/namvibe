import os
from datetime import timedelta

from services.env_service import get_env, load_project_env

load_project_env()

class Config:
    APP_NAME = get_env("APP_NAME", "NamVibe")
    APP_DOMAIN = get_env("APP_DOMAIN", "namvibe.com")
    SECRET_KEY = get_env("SECRET_KEY")
    if not SECRET_KEY:
        if get_env("FLASK_ENV") == "production" or get_env("ENV") == "production":
            raise RuntimeError("SECRET_KEY environment variable is required in production.")
        SECRET_KEY = "GENERATE_A_STRONG_RANDOM_VALUE"
    SUPABASE_URL = get_env("SUPABASE_URL")
    SUPABASE_ANON_KEY = get_env("SUPABASE_ANON_KEY") or get_env("SUPABASE_KEY")
    SUPABASE_SERVICE_ROLE_KEY = get_env("SUPABASE_SERVICE_ROLE_KEY")
    APP_BASE_URL = get_env("APP_BASE_URL")
    SLOW_REQUEST_MS = int(get_env("SLOW_REQUEST_MS", "1500") or "1500")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_DOMAIN = None
    SESSION_COOKIE_SECURE = get_env("FLASK_ENV") == "production" or get_env("ENV") == "production"
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
