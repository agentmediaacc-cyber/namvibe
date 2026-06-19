"""Phase 87 — Final System Health Check.

Checks database, Redis, storage, sockets, fake content, routes.
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings
from services.neon_service import fast_query, get_pool_status
from services.redis_service import redis_manager
from services.blocking_service import is_blocked_any
from services.relationship_cache_service import get_relationship_state, is_uuid
from services.storage_health_service import get_storage_status
from services.production_content_guard import is_fake_content

PASS = 0
FAIL = 0
WARN = []

def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name} {detail}")
        FAIL += 1

def warn(msg):
    WARN.append(msg)
    print(f"  WARN {msg}")

def run():
    global PASS, FAIL
    warnings.filterwarnings("ignore", category=UserWarning, module="supabase")
    print("=" * 60)
    print("FINAL SYSTEM HEALTH CHECK")
    print("=" * 60)

    # 1. Database — warm up pool first (first query is slow ~8s due to pool init)
    print("\n--- Database ---")
    fast_query("SELECT 1", timeout_ms=15000, default=[])  # warm up
    try:
        row = fast_query("SELECT 1 AS ok", timeout_ms=5000, default=[])
        check("Database reachable", bool(row) and row[0].get("ok") == 1)
    except Exception as e:
        check(f"Database reachable ({e})", False)

    pool = get_pool_status()
    check("Connection pool active", pool.get("pool_ready", False) or pool.get("recent_success", False))

    # 2. Redis
    print("\n--- Redis ---")
    redis_ok = bool(redis_manager.get_client()) if hasattr(redis_manager, "get_client") else False
    if not redis_ok:
        import redis
        try:
            r = redis.from_url("redis://localhost:6379/0")
            r.ping()
            redis_ok = True
        except Exception:
            redis_ok = False
    check("Redis reachable", redis_ok)

    # 3. Blocking service
    print("\n--- Blocking Service ---")
    check("is_blocked_any works", callable(is_blocked_any))
    check("UUID guard works", not is_blocked_any("bad-uuid", "also-bad"))

    # 4. Relationship cache
    print("\n--- Relationship Cache ---")
    check("get_relationship_state works", callable(get_relationship_state))
    check("is_uuid validates UUID", is_uuid("550e8400-e29b-41d4-a716-446655440000"))
    check("is_uuid rejects invalid", not is_uuid("not-a-uuid"))

    # 5. Storage
    print("\n--- Storage ---")
    from services.storage_health_service import safe_upload_file, safe_delete_file, ensure_required_buckets
    import uuid

    ensure_required_buckets()
    storage = get_storage_status()
    supabase_info = storage.get("supabase", {})
    check("storage_connected", supabase_info.get("error") not in ("supabase_client_unavailable", "storage_check_failed"))
    missing = supabase_info.get("missing_buckets", [])
    check("buckets_present", len(missing) == 0)
    if missing:
        warn(f"missing buckets: {missing}")

    # Upload/delete probe
    test_path = f".phase88_health_{uuid.uuid4().hex[:8]}.txt"
    upload = safe_upload_file("documents", test_path, b"healthcheck", content_type="text/plain")
    if upload.get("ok"):
        safe_delete_file("documents", test_path)
        check("upload_delete_test", True)
    else:
        check(f"upload_delete_test ({upload.get('error', 'unknown')})", False)

    # 6. No fake content check
    print("\n--- Fake Content Guard ---")
    check("is_fake_content works", callable(is_fake_content))
    check("moon not fake", not is_fake_content({"username": "moon", "id": "1"}))
    check("namvibe not fake", not is_fake_content({"username": "namvibe", "id": "2"}))
    check("fake seed detected", is_fake_content({"username": "seed_user"}))

    # 7. Module imports
    print("\n--- Module Imports ---")
    modules = [
        "services.blocking_service",
        "services.relationship_cache_service",
        "services.storage_health_service",
        "services.log_rate_limit_service",
        "services.production_content_guard",
        "services.relationship_privacy_service",
        "services.social_action_policy",
    ]
    for mod_name in modules:
        try:
            __import__(mod_name)
            check(f"{mod_name} loads", True)
        except Exception as e:
            check(f"{mod_name} loads ({e})", False)

    # Summary
    print("\n" + "=" * 60)
    total = PASS + FAIL
    status = "PASS" if FAIL == 0 else "FAIL"
    print(f"FINAL SYSTEM HEALTH: {status} ({PASS}/{total} passed")
    if WARN:
        for w in WARN:
            print(f"  Warning: {w}")
    print("=" * 60)

    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
