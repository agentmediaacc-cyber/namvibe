import os
import sys

def check_env():
    print("[check] Environment variables...")
    required = ["DATABASE_URL", "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"]
    missing = [r for r in required if not os.getenv(r)]
    if missing:
        print(f"  FAILED: Missing {missing}")
        return False
    print("  OK")
    return True

def check_files():
    print("[check] Critical files...")
    required = ["Procfile", "requirements.txt", "app.py"]
    missing = [r for r in required if not os.path.exists(r)]
    if missing:
        print(f"  FAILED: Missing {missing}")
        return False
    print("  OK")
    return True

def check_procfile():
    print("[check] Procfile content...")
    if not os.path.exists("Procfile"): return False
    with open("Procfile", "r") as f:
        content = f.read()
        if "gunicorn app:app" not in content:
            print("  FAILED: Procfile might be incorrect")
            return False
    print("  OK")
    return True

def check_engines():
    print("[check] Engine services...")
    required = [
        "services/notification_engine.py",
        "services/reels_engine.py",
        "services/messaging_engine.py",
        "services/wallet_engine.py",
        "services/moderation_engine.py",
        "services/presence_engine.py",
        "services/feed_engine.py",
        "services/verification_engine.py",
        "services/job_engine.py",
        "services/redis_service.py",
        "services/socketio_service.py",
        "services/queue_service.py",
        "services/media_pipeline.py",
        "services/rate_limit_service.py",
        "services/observability_service.py"
    ]
    missing = [r for r in required if not os.path.exists(r)]
    if missing:
        print(f"  FAILED: Missing {missing}")
        return False
    print("  OK")
    return True

def check_routes():
    print("[check] API routes...")
    required = [
        "api_routes/notification_routes.py",
        "api_routes/reels_routes.py",
        "api_routes/message_routes.py",
        "api_routes/wallet_routes.py",
        "api_routes/moderation_routes.py",
        "api_routes/presence_routes.py",
        "api_routes/feed_routes.py",
        "api_routes/verification_routes.py"
    ]
    missing = [r for r in required if not os.path.exists(r)]
    if missing:
        print(f"  FAILED: Missing {missing}")
        return False
    print("  OK")
    return True

def check_redis():
    print("[check] Redis connection (optional fallback)...")
    from services.redis_service import redis_available, get_redis_health
    if redis_available():
        health = get_redis_health()
        print(f"  OK: Redis {health.get('version')} connected")
    else:
        print("  WARNING: Redis unavailable, using in-memory fallbacks")
    return True

if __name__ == "__main__":
    ok = all([check_env(), check_files(), check_procfile(), check_engines(), check_routes(), check_redis()])
    if not ok:
        print("\n❌ Pre-deploy check FAILED")
        sys.exit(1)
    print("\n✅ Pre-deploy check PASSED")
