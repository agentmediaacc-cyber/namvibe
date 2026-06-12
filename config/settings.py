import os

class Config:
    APP_NAME = os.getenv("APP_NAME", "NamVibe")
    APP_DOMAIN = os.getenv("APP_DOMAIN", "namvibe.com")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    APP_BASE_URL = os.getenv("APP_BASE_URL")
    SLOW_REQUEST_MS = int(os.getenv("SLOW_REQUEST_MS", "1500"))
