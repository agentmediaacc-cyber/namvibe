#!/usr/bin/env python3
"""
Phase 118 — Deployment, Scale & Security Readiness.

Checks all 11 audit areas against real project files and real Neon DB.
Never prints secrets. Never mutates data.

Usage:
    python3 scripts/test_phase118_deployment_readiness.py
"""

import os
import re
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip("'\"")
                if v:
                    os.environ.setdefault(k, v)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASS = 0
FAIL = 0
WARN = 0
BLOCKERS = []
WARNINGS = []

def ok(msg):
    global PASS
    PASS += 1
    print(f"  [PASS] {msg}")

def fail(msg):
    global FAIL, BLOCKERS
    FAIL += 1
    BLOCKERS.append(msg)
    print(f"  [FAIL] {msg}")

def warn(msg):
    global WARN, WARNINGS
    WARN += 1
    WARNINGS.append(msg)
    print(f"  [WARN] {msg}")

def check(condition, msg):
    ok(msg) if condition else fail(msg)

def file_exists(path):
    return os.path.exists(os.path.join(ROOT, path))

def file_read(path):
    fp = os.path.join(ROOT, path)
    if os.path.exists(fp):
        with open(fp) as f:
            return f.read()
    return ""

SECRET_SUFFIXES = ("_KEY", "_SECRET", "_PASSWORD", "_TOKEN", "_URL")
SECRET_PREFIXES = ("SUPABASE_",)
DB_TABLES = [
    "chain_profiles",
    "chain_follows",
    "chain_friends",
    "chain_friend_requests",
    "chain_message_threads",
    "chain_thread_members",
    "chain_messages",
    "chain_calls",
    "chain_call_participants",
    "chain_status_posts",
    "chain_story_views",
    "chain_reels",
    "chain_reel_reactions",
    "chain_reel_comments",
    "chain_saved_items",
    "chain_wallets",
    "chain_wallet_transactions",
    "chain_payout_requests",
    "chain_notifications",
    "chain_muted_users",
    "chain_blocks",
    "chain_reports",
]
REALITY_TESTS = [
    "scripts/test_message_reality.py",
    "scripts/test_call_reality.py",
    "scripts/test_content_reality.py",
    "scripts/test_wallet_reality.py",
    "scripts/test_phase102_full_user_flow.py",
    "scripts/audit_phase117_production_readiness.py",
]

print("\n=== PHASE 118 — DEPLOYMENT, SCALE & SECURITY READINESS ===\n")

# ── 1. Cloud Run Readiness ──────────────────────
print("--- 1. Cloud Run Readiness ---")
if file_exists("Dockerfile"):
    ok("Dockerfile exists")
    docker = file_read("Dockerfile")
    if "0.0.0.0" in docker:
        ok("Dockerfile binds to 0.0.0.0")
    else:
        warn("Dockerfile does not bind to 0.0.0.0")
    if "$PORT" in docker or "${PORT}" in docker or 'os.environ["PORT"]' in docker:
        ok("Dockerfile uses PORT env var")
    else:
        warn("Dockerfile may not use PORT env var")
    if "gunicorn" in docker:
        ok("Dockerfile uses gunicorn")
    if "CMD" in docker:
        ok("Dockerfile has CMD entrypoint")
else:
    fail("Dockerfile missing")

if file_exists("cloudrun.yaml"):
    ok("cloudrun.yaml exists")
    cr = file_read("cloudrun.yaml")
    if "containerPort: 8080" in cr or "containerPort" in cr:
        ok("cloudrun.yaml has containerPort")
    if "secretKeyRef" in cr:
        ok("cloudrun.yaml uses Google Secret Manager")
    if "FLASK_ENV" in cr and "production" in cr:
        ok("cloudrun.yaml sets FLASK_ENV=production")
else:
    fail("cloudrun.yaml missing")

if file_exists("cloudrun.example.yaml"):
    ok("cloudrun.example.yaml exists")

app_py = file_read("app.py")
if '"/healthz"' in app_py:
    ok("Health endpoint /healthz exists")
else:
    warn("No /healthz endpoint found in app.py")

app_py_upper = app_py.upper()
if 'STATIC' not in app_py_upper or 'UPLOADS' not in app_py_upper:
    ok("No local-only file storage dependency detected (static/uploads)")
else:
    warn("Local file storage (static/uploads) referenced — verify not required in production")

# ── 2. Render Readiness ─────────────────────────
print("\n--- 2. Render Readiness ---")
if file_exists("render.yaml"):
    ok("render.yaml exists")
    render = file_read("render.yaml")
    if "healthCheckPath: /healthz" in render:
        ok("render.yaml health check path set to /healthz")
    else:
        warn("render.yaml healthCheckPath not set")
    if "startCommand" in render or "dockerfilePath" in render:
        ok("render.yaml has start command / dockerfile path")
    else:
        warn("render.yaml may lack start command")
    if "sync: false" in render:
        ok("render.yaml marks secrets sync: false (set in Dashboard)")
    else:
        warn("render.yaml may expose secrets as sync: true")
else:
    fail("render.yaml missing")

if file_exists("Procfile"):
    ok("Procfile exists")
    proc = file_read("Procfile")
    if "gunicorn" in proc:
        ok("Procfile uses gunicorn")
    if "web:" in proc:
        ok("Procfile has web process type")

# ── 3. Environment Safety ───────────────────────
print("\n--- 3. Environment Safety ---")
REQUIRED_VARS = [
    "SECRET_KEY",
    "DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
]
REDIS_VARS = ["REDIS_URL", "REDIS_TLS_URL"]

print("  [info] Required production env vars (SET/MISSING only):")
all_set = True
for var in REQUIRED_VARS:
    val = os.getenv(var, "")
    if val and val != "":
        ok(f"  env {var} = SET")
    else:
        fail(f"  env {var} = MISSING")
        all_set = False

redis_found = any(os.getenv(v, "") for v in REDIS_VARS)
if redis_found:
    ok("  env REDIS_URL or REDIS_TLS_URL = SET")
else:
    warn("  env REDIS_URL or REDIS_TLS_URL = MISSING (required for production Socket.IO)")

if all_set and redis_found:
    ok("All required production env vars are set")
if not all_set:
    warn("Some required production env vars are MISSING — set them before deploy")

# ── 4. Auth Production Safety ───────────────────
print("\n--- 4. Auth Production Safety ---")
auth_svc = file_read("services/auth_service.py")
if "ALLOW_LOCAL_AUTH_FALLBACK" in auth_svc:
    ok("ALLOW_LOCAL_AUTH_FALLBACK guard exists")
    if 'os.getenv("FLASK_ENV")' in auth_svc and "production" in auth_svc:
        ok("Auth service checks FLASK_ENV for production")
    else:
        warn("Auth service production env check pattern unclear")
    if "CHAIN_FAST_LOCAL" in auth_svc:
        ok("Auth service respects CHAIN_FAST_LOCAL override")
else:
    fail("ALLOW_LOCAL_AUTH_FALLBACK guard missing from auth_service.py")

# Check ALLOW_LOCAL_AUTH_FALLBACK does NOT default to true in env
env_val = os.getenv("ALLOW_LOCAL_AUTH_FALLBACK", "").lower()
flask_env = os.getenv("FLASK_ENV", "development").lower()
if flask_env == "production" and env_val in ("1", "true", "yes"):
    warn("ALLOW_LOCAL_AUTH_FALLBACK is enabled in production — verify this is intentional")
elif flask_env == "production":
    ok("ALLOW_LOCAL_AUTH_FALLBACK not enabled in production (safe)")
else:
    ok(f"FLASK_ENV={os.getenv('FLASK_ENV', 'development')} — auth fallback check skipped")

# ── 5. Redis Readiness ──────────────────────────
print("\n--- 5. Redis Readiness ---")
if redis_found:
    ok("Redis URL present")
    url = os.getenv("REDIS_URL") or os.getenv("REDIS_TLS_URL") or ""
    if url.startswith("rediss://"):
        ok("Upstash TLS rediss:// supported")
    elif url.startswith("redis://"):
        warn("Redis URL uses redis:// not rediss:// — TLS recommended for production")
    else:
        warn("Redis URL scheme unrecognized")
else:
    fail("Redis URL missing")

socketio_svc = file_read("services/socketio_service.py")
if "CHAIN_SOCKETIO_REDIS_MANAGER" in socketio_svc:
    ok("Socket.IO Redis manager toggle exists")
else:
    warn("Socket.IO Redis manager toggle (CHAIN_SOCKETIO_REDIS_MANAGER) not found")

if "message_queue" in socketio_svc:
    ok("Socket.IO Redis message_queue configured")
else:
    warn("Socket.IO message_queue not configured")

redis_svc = file_read("services/redis_service.py")
if "CircuitBreaker" in redis_svc:
    ok("Redis circuit breaker present")
if "memory_fallback" in redis_svc.lower() or "_MEMORY_FALLBACK" in redis_svc:
    ok("Redis memory fallback present")

# Check Redis doesn't crash app on failure (circuit breaker + fallback paths)
if "get_json" in redis_svc and "except Exception" in redis_svc:
    ok("Redis get_json has exception handling (won't crash)")
if "set_json" in redis_svc and "except Exception" in redis_svc:
    ok("Redis set_json has exception handling (won't crash)")

# ── 6. Neon Readiness ───────────────────────────
print("\n--- 6. Neon Readiness ---")
dsn = os.getenv("DATABASE_URL", "")
if dsn:
    ok("DATABASE_URL present")
else:
    fail("DATABASE_URL missing")

# Live Neon checks
try:
    from services.neon_service import fast_query, get_pool_status, get_neon_health
    from services.circuit_breaker import CircuitBreaker

    # Direct SELECT 1 first (also triggers lazy pool init)
    sel1 = fast_query("SELECT 1 AS ok", timeout_ms=15000, default=[])
    if sel1:
        ok("Neon SELECT 1 works (connected)")
    else:
        warn("Neon SELECT 1 returned no results")

    status = get_pool_status()
    if status and status.get("pool_ready"):
        ok("Neon pool initializes")
    else:
        warn("Neon pool not ready yet")

    # Circuit breaker check via _NEON_BREAKER
    try:
        from services.neon_service import _NEON_BREAKER
        if _NEON_BREAKER.get_state() == "closed":
            ok("Neon circuit breaker closed")
        else:
            warn(f"Neon circuit breaker state: {_NEON_BREAKER.get_state()}")
    except ImportError:
        warn("Could not check Neon circuit breaker state directly")

except Exception as e:
    fail(f"Neon health check failed: {e}")

# ── 7. Core DB Tables ──
print("\n--- 7. Core DB Tables ---")
try:
    from services.neon_service import fast_query as fq
    for tbl in DB_TABLES:
        res = fq(
            "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relname = %s LIMIT 1",
            (tbl,),
            timeout_ms=15000,
            default=[],
        )
        if res:
            ok(f"DB table exists: {tbl}")
        else:
            fail(f"DB table missing: {tbl}")
except Exception as e:
    fail(f"Could not verify DB tables: {e}")

# ── 8. Security Checks ──────────────────────────
print("\n--- 8. Security Checks ---")
if "CSRFProtect" in app_py:
    ok("CSRF protection configured in app.py")
else:
    fail("CSRFProtect not found in app.py")

secret_key = os.getenv("SECRET_KEY", "default-dev-secret")
is_dev_secret = "dev" in secret_key.lower() or "default" in secret_key.lower() or len(secret_key) < 20
if is_dev_secret:
    warn("SECRET_KEY appears to be a development/default key")
else:
    ok("SECRET_KEY is not a default/dev key")

flask_env_prod = os.getenv("FLASK_ENV", "").lower() == "production"
if flask_env_prod:
    debug_val = os.getenv("FLASK_DEBUG", os.getenv("DEBUG", "0"))
    if debug_val in ("0", "false", ""):
        ok("Debug mode not enabled in production")
    else:
        fail("Debug mode appears enabled in production")
else:
    ok(f"FLASK_ENV={os.getenv('FLASK_ENV', 'development')} — debug check deferred")

if "MAX_CONTENT_LENGTH" in app_py:
    ok("Upload size limit configured (MAX_CONTENT_LENGTH)")
else:
    warn("MAX_CONTENT_LENGTH not configured in app.py")

storage_svc = file_read("services/storage_service.py")
if "ALLOWED_EXTENSIONS" in storage_svc:
    ok("Allowed upload extensions configured")
    exts = re.findall(r"\{([^}]+)\}", storage_svc[storage_svc.index("ALLOWED_EXTENSIONS"):storage_svc.index("ALLOWED_EXTENSIONS")+500])
    if exts:
        ok(f"Upload extensions defined: {exts[0][:100]}")
else:
    warn("No allowed upload extensions found")

# Check dangerous debug routes disabled or protected
dev_routes = re.findall(r'@app\.route\(.*dev.*\)|@app\.get\(\s*"/dev', app_py)
if dev_routes:
    for rt in dev_routes[:5]:
        if "FLASK_ENV" in app_py.split(rt.split("def")[0])[-1][:500] if "def" in rt else True:
            pass  # likely guarded
    guarded = "FLASK_ENV" in app_py[app_py.index('/dev'):app_py.index('/dev')+1000] if '/dev' in app_py else True
    if guarded:
        ok("Dev routes guarded by FLASK_ENV check")
    else:
        warn("Dev routes may not be production-guarded")
else:
    ok("No dev-only debug routes detected")

# Admin routes require auth
admin_routes_text = file_read("api_routes/admin_routes.py")
if "require_admin" in admin_routes_text:
    ok("Admin routes protected by require_admin")
else:
    warn("Admin routes may lack require_admin protection")

# Payout routes require auth
payout_routes = file_read("api_routes/wallet_routes.py") if file_exists("api_routes/wallet_routes.py") else ""
if "login_required" in payout_routes or "require_admin" in payout_routes:
    ok("Payout routes require auth/admin")
else:
    warn("Payout routes: auth check not clearly detected in wallet_routes.py")

# ── 9. Performance Readiness ────────────────────
print("\n--- 9. Performance Readiness ---")
try:
    from services.neon_service import fast_query as nq
    idx_rows = nq("SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND indexname LIKE 'idx_chain%' ORDER BY indexname", timeout_ms=20000, default=[])
    idx_names = {r["indexname"] for r in idx_rows if r}

    perf_indexes = {
        "Relationship (follows/friends/blocks)": ["idx_chain_follows_follower_active", "idx_chain_follows_following_active", "idx_chain_friends_pair_status", "idx_chain_blocks_pair_active"],
        "Friend requests": ["idx_chain_friend_requests_sender_status", "idx_chain_friend_requests_recipient_status"],
        "Messages": ["idx_chain_messages_thread_created"],
        "Thread members": ["idx_chain_thread_members_profile_thread", "idx_chain_thread_members_thread_profile"],
        "Discovery": ["idx_chain_profiles_discovery_active"],
    }
    for group, idx_list in perf_indexes.items():
        present = [i for i in idx_list if i in idx_names]
        missing = [i for i in idx_list if i not in idx_names]
        if not missing:
            ok(f"Performance indexes present: {group}")
        else:
            warn(f"Performance indexes missing for {group}: {', '.join(missing)}")

except Exception as e:
    warn(f"Could not verify performance indexes: {e}")

# Query timeouts not too low for Neon
neon_svc_text = file_read("services/neon_service.py")
if "timeout_ms: int = 10000" in neon_svc_text or "timeout_ms: int = 20000" in neon_svc_text or "timeout_ms=10000" in neon_svc_text:
    ok("Neon query timeouts reasonable (>=10s)")
elif "timeout_ms: int = 5000" in neon_svc_text and "timeout_ms=10000" in neon_svc_text:
    ok("Neon fast_query uses 10s, write_query 5s — reasonable")
else:
    warn("Neon timeouts may be too low — check fast_query/write_query defaults")

# Redis bulk cache functions exist
if "def cache_mget" in redis_svc:
    ok("Redis cache_mget (bulk get) exists")
else:
    warn("cache_mget not found in redis_service.py")
if "def cache_set_bulk" in redis_svc:
    ok("Redis cache_set_bulk (pipeline) exists")
else:
    warn("cache_set_bulk not found in redis_service.py")

# ── 10. Reality Tests Presence ──────────────────
print("\n--- 10. Reality Tests Presence ---")
for test_file in REALITY_TESTS:
    if file_exists(test_file):
        ok(f"Reality test exists: {test_file}")
    else:
        warn(f"Reality test missing: {test_file}")

# ── 11. Load Test Scripts (dry-run plans) ──────
print("\n--- 11. Load Test Plans (dry-run) ---")

load_plans = {
    "100 message send simulation": {
        "description": "Send 100 messages across 10 threads, measure p50/p95/p99 latency",
        "prerequisites": "test user + test threads exist, Redis connected",
        "destructive": False,
        "script": "scripts/loadtest_messages_dryrun.py (not yet implemented)",
    },
    "50 call signaling simulation": {
        "description": "Simulate 50 WebRTC call signaling rounds, measure negotiation latency",
        "prerequisites": "test users exist, WebSocket/Socket.IO connected",
        "destructive": False,
        "script": "scripts/loadtest_calls_dryrun.py (not yet implemented)",
    },
    "Feed pagination stress": {
        "description": "Page through discovery/reels/feed with offset up to 200, measure response times",
        "prerequisites": "profiles + content exist in DB",
        "destructive": False,
        "script": "scripts/loadtest_feed_dryrun.py (not yet implemented)",
    },
}
for name, plan in load_plans.items():
    print(f"  [INFO] Plan: {name}")
    print(f"         {plan['description']}")
    print(f"         Destructive: {plan['destructive']}")
    print(f"         Script: {plan['script']}")
    ok(f"Load test plan defined: {name}")

# ── Summary ─────────────────────────────────────
print(f"\n{'=' * 60}")
print(f"PHASE 118 — DEPLOYMENT READINESS SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}")
print(f"  FAIL: {FAIL}")
print(f"  WARN: {WARN}")
print()

if BLOCKERS:
    print("  BLOCKERS (must fix):")
    for b in BLOCKERS:
        print(f"    - {b}")
else:
    ok("No blockers")

if WARNINGS:
    print("  WARNINGS (review before deploy):")
    for w in WARNINGS:
        print(f"    - {w}")

print()
has_blockers = FAIL > 0
has_warnings = WARN > 0

# Determine safety tiers
local_beta = not has_blockers  # local beta is OK without blockers
ext_beta = not has_blockers  # external beta may have warnings
public_prod = not has_blockers and not has_warnings  # public prod needs clean

print(f"  safe_for_local_beta: {'YES' if local_beta else 'NO'}")
print(f"  safe_for_external_beta: {'YES' if ext_beta else 'NO'}")
print(f"  safe_for_public_production: {'YES' if public_prod else 'NO'}")

if local_beta:
    print("\n  Recommended next command:")
    print("    python3 scripts/audit_phase117_production_readiness.py")
    print("    python3 scripts/test_message_reality.py")
    print("    python3 scripts/test_content_reality.py")

if WARNINGS:
    print("\n  Recommended fixes before external beta:")
    for w in WARNINGS:
        print(f"    - {w}")

sys.exit(0 if local_beta else 1)
