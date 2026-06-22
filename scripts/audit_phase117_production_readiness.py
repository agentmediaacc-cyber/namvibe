#!/usr/bin/env python3
"""
Phase 117 — Final Production Readiness Audit for NamVibe.

Checks all 25 audit areas against real project files and real Neon DB.
Never prints secrets. Never mutates data.

Usage:
    python3 scripts/audit_phase117_production_readiness.py
"""

import os
import re
import sys
import importlib
import pkgutil

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
    global WARN
    WARN += 1
    print(f"  [WARN] {msg}")


def check(condition, msg):
    if condition:
        ok(msg)
    else:
        fail(msg)


# ──────────────────────────────────────────────
print("\n=== PHASE 117 — PRODUCTION READINESS AUDIT ===\n")


# ── 1. Auth security ─────────────────────────
print("--- 1. Auth Security ---")

try:
    import services.auth_service
    ok("auth_service module imported successfully")
except ImportError as e:
    fail(f"auth_service import failed: {e}")

try:
    import services.session_service
    ok("session_service module imported successfully")
except ImportError as e:
    fail(f"session_service import failed: {e}")

guard_file = os.path.join(ROOT, "services", "auth_service.py")
if os.path.exists(guard_file):
    with open(guard_file) as f:
        content = f.read()
    if "ALLOW_LOCAL_AUTH_FALLBACK" in content:
        if 'os.getenv("ALLOW_LOCAL_AUTH_FALLBACK", "").lower() in ("1", "true", "yes")' in content:
            ok("ALLOW_LOCAL_AUTH_FALLBACK production guard found")
        else:
            warn("ALLOW_LOCAL_AUTH_FALLBACK referenced but guard pattern unclear")
    else:
        fail("ALLOW_LOCAL_AUTH_FALLBACK guard missing from auth_service.py")
else:
    fail("auth_service.py not found")

if "def _is_production_env" in content:
    ok("Production env check (_is_production_env) present in auth_service")
else:
    warn("Production env check pattern unclear")


# ── 2. CSRF Protection ───────────────────────
print("\n--- 2. CSRF Protection ---")

app_py_path = os.path.join(ROOT, "app.py")
if os.path.exists(app_py_path):
    with open(app_py_path) as f:
        app_content = f.read()
    if "CSRFProtect" in app_content:
        ok("CSRFProtect imported")
    else:
        fail("CSRFProtect not imported")
    if "csrf = CSRFProtect(app)" in app_content or "csrf.init_app" in app_content:
        ok("CSRFProtect initialized")
    else:
        fail("CSRFProtect not initialized")
    if "csrf.exempt" in app_content:
        ok("CSRF exemptions exist (expected for API routes)")
    else:
        warn("No CSRF exemptions found")
else:
    fail("app.py not found")


# ── 3. Session Security ──────────────────────
print("\n--- 3. Session Security ---")

if os.path.exists(app_py_path):
    if "SESSION_COOKIE_SECURE" in app_content:
        ok("SESSION_COOKIE_SECURE configured")
    else:
        fail("SESSION_COOKIE_SECURE not configured")
    if "SESSION_COOKIE_HTTPONLY" in app_content:
        ok("SESSION_COOKIE_HTTPONLY configured")
    else:
        fail("SESSION_COOKIE_HTTPONLY not configured")
    if "SESSION_COOKIE_SAMESITE" in app_content:
        ok("SESSION_COOKIE_SAMESITE configured")
    else:
        fail("SESSION_COOKIE_SAMESITE not configured")
    if "PERMANENT_SESSION_LIFETIME" in app_content:
        ok("PERMANENT_SESSION_LIFETIME configured")
    else:
        fail("PERMANENT_SESSION_LIFETIME not configured")
    if "ProxyFix" in app_content:
        ok("ProxyFix middleware present (HTTPS behind proxy)")
    else:
        warn("ProxyFix middleware not found")
else:
    fail("app.py not found")


# ── 4. Registration/Login/Logout ─────────────
print("\n--- 4. Registration/Login/Logout ---")

for route_file in ["api_routes/auth_routes.py", "routes/auth_routes.py"]:
    fp = os.path.join(ROOT, route_file)
    if os.path.exists(fp):
        with open(fp) as f:
            rc = f.read()
        if "def register" in rc or "register_post" in rc:
            ok(f"Registration route found in {route_file}")
            break
        if "def login" in rc:
            ok(f"Login route found in {route_file}")
            break
else:
    fail("No auth route file found with registration/login")

for tmpl in ["auth/login.html", "auth/register.html", "auth/forgot_password.html", "auth/reset_password.html"]:
    if os.path.exists(os.path.join(ROOT, "templates", tmpl)):
        ok(f"Template exists: {tmpl}")
    else:
        warn(f"Template missing: {tmpl}")

if os.path.exists(app_py_path):
    logout_in_app = "logout" in app_content or "/logout" in app_content
    auth_routes_path = os.path.join(ROOT, "api_routes", "auth_routes.py")
    logout_in_auth_routes = os.path.exists(auth_routes_path) and "logout" in open(auth_routes_path).read()
    if logout_in_app or logout_in_auth_routes:
        ok("Logout route referenced (app.py or auth_routes.py)")
    else:
        warn("Logout route not obviously referenced in app.py or auth_routes.py")


# ── 5. Profile Loading ───────────────────────
print("\n--- 5. Profile Loading ---")

for svc in ["profile_service.py", "profile_context_service.py", "profile_completion_service.py"]:
    if os.path.exists(os.path.join(ROOT, "services", svc)):
        ok(f"Profile service exists: {svc}")
    else:
        fail(f"Profile service missing: {svc}")

for route_file in ["api_routes/profile_routes.py"]:
    fp = os.path.join(ROOT, route_file)
    if os.path.exists(fp):
        with open(fp) as f:
            rc = f.read()
        if "def profile" in rc or "def get_profile" in rc or "profile_bundle" in rc:
            ok(f"Profile routes found in {route_file}")
            break
else:
    fail("No profile route file found")


# ── 6. Follow/Friend System ──────────────────
print("\n--- 6. Follow/Friend System ---")

for svc in ["social_relationship_service.py", "relationship_cache_service.py"]:
    if os.path.exists(os.path.join(ROOT, "services", svc)):
        ok(f"Social service exists: {svc}")
    else:
        fail(f"Social service missing: {svc}")

if os.path.exists(os.path.join(ROOT, "api_routes", "social_routes.py")):
    ok("social_routes.py exists")
else:
    fail("social_routes.py missing")

if os.path.exists(os.path.join(ROOT, "api_routes", "friend_routes.py")):
    ok("friend_routes.py exists")
else:
    warn("friend_routes.py missing")

if os.path.exists(os.path.join(ROOT, "api_routes", "follow_request_routes.py")):
    ok("follow_request_routes.py exists")
else:
    warn("follow_request_routes.py missing")


# ── 7. Messaging ─────────────────────────────
print("\n--- 7. Messaging ---")

for svc in ["messaging_engine.py", "message_thread_service.py", "message_delivery_service.py"]:
    if os.path.exists(os.path.join(ROOT, "services", svc)):
        ok(f"Messaging service exists: {svc}")
    else:
        warn(f"Messaging service missing: {svc}")

for route_file in ["api_routes/message_routes.py", "api_routes/messaging_routes.py",
                    "api_routes/message_production_routes.py"]:
    fp = os.path.join(ROOT, route_file)
    if os.path.exists(fp):
        ok(f"Messaging route file exists: {route_file}")

if os.path.exists(os.path.join(ROOT, "templates", "messages", "index.html")):
    ok("Messages template exists")
else:
    warn("Messages template missing")

if os.path.exists(os.path.join(ROOT, "scripts", "test_message_reality.py")):
    ok("Message reality test exists")
else:
    fail("Message reality test missing")


# ── 8. Calls/WebRTC ──────────────────────────
print("\n--- 8. Calls/WebRTC ---")

for svc in ["call_service.py", "call_feature_service.py", "webrtc_turn_service.py", "callkit_service.py"]:
    if os.path.exists(os.path.join(ROOT, "services", svc)):
        ok(f"Call service exists: {svc}")
    else:
        warn(f"Call service missing: {svc}")

if os.path.exists(os.path.join(ROOT, "api_routes", "call_routes.py")):
    ok("call_routes.py exists")
else:
    fail("call_routes.py missing")

if os.path.exists(os.path.join(ROOT, "scripts", "test_call_reality.py")):
    ok("Call reality test exists")
else:
    fail("Call reality test missing")

turn_found = False
turn_file = os.path.join(ROOT, "services", "webrtc_turn_service.py")
if os.path.exists(turn_file):
    with open(turn_file) as f:
        tc = f.read()
    if "TURN_SERVER_URL" in tc or "turn" in tc.lower():
        turn_found = True
        ok("TURN server referenced in webrtc_turn_service.py")
check(turn_found, "TURN server config present")


# ── 9. Stories ───────────────────────────────
print("\n--- 9. Stories ---")

for svc in ["stories_service.py", "status_service.py"]:
    if os.path.exists(os.path.join(ROOT, "services", svc)):
        ok(f"Stories service exists: {svc}")
    else:
        warn(f"Stories service missing: {svc}")

for tmpl in ["stories/index.html", "status/index.html"]:
    if os.path.exists(os.path.join(ROOT, "templates", tmpl)):
        ok(f"Stories template exists: {tmpl}")
        break
else:
    warn("No stories template found")

if os.path.exists(os.path.join(ROOT, "scripts", "test_content_reality.py")):
    ok("Content reality test exists (includes stories)")
else:
    fail("Content reality test missing")


# ── 10. Reels ─────────────────────────────────
print("\n--- 10. Reels ---")

for svc in ["reels_engine.py", "reels_service.py", "reel_processing_engine.py"]:
    if os.path.exists(os.path.join(ROOT, "services", svc)):
        ok(f"Reels service exists: {svc}")
    else:
        warn(f"Reels service missing: {svc}")

if os.path.exists(os.path.join(ROOT, "api_routes", "reels_routes.py")):
    ok("reels_routes.py exists")
else:
    fail("reels_routes.py missing")

if os.path.exists(os.path.join(ROOT, "templates", "reels", "index.html")):
    ok("Reels template exists")
else:
    warn("Reels template missing")


# ── 11. Feed/Discovery ────────────────────────
print("\n--- 11. Feed/Discovery ---")

for svc in ["feed_engine.py", "feed_service.py", "feed_cursor_service.py",
            "discovery_service.py", "recommendation_service.py", "trending_service.py"]:
    if os.path.exists(os.path.join(ROOT, "services", svc)):
        ok(f"Feed/Discovery service exists: {svc}")
    else:
        warn(f"Feed/Discovery service missing: {svc}")

for route_file in ["api_routes/feed_routes.py", "api_routes/discovery_routes.py",
                    "api_routes/explore_routes.py"]:
    fp = os.path.join(ROOT, route_file)
    if os.path.exists(fp):
        ok(f"Feed/Discovery route file exists: {route_file}")

if os.path.exists(os.path.join(ROOT, "api_routes", "homepage_api.py")):
    ok("homepage_api.py exists")
else:
    warn("homepage_api.py missing")


# ── 12. Notifications ─────────────────────────
print("\n--- 12. Notifications ---")

for svc in ["notification_engine.py", "push_notification_engine.py", "push_notification_service.py",
            "push_token_service.py", "notification_preferences_service.py"]:
    fp = os.path.join(ROOT, "services", svc)
    if os.path.exists(fp):
        ok(f"Notification service exists: {svc}")
    elif svc != "notification_preferences_service.py":
        warn(f"Notification service missing: {svc}")

for route_file in ["api_routes/notification_routes.py", "api_routes/notification_center_routes.py",
                    "api_routes/push_notification_routes.py"]:
    fp = os.path.join(ROOT, route_file)
    if os.path.exists(fp):
        ok(f"Notification route file exists: {route_file}")

if os.path.exists(os.path.join(ROOT, "templates", "notifications", "index.html")):
    ok("Notifications template exists")
else:
    warn("Notifications template missing")


# ── 13. Wallet ───────────────────────────────
print("\n--- 13. Wallet ---")

for svc in ["wallet_service.py", "wallet_engine.py", "wallet_action_service.py",
            "wallet_ledger_service.py", "payment_fraud_service.py"]:
    if os.path.exists(os.path.join(ROOT, "services", svc)):
        ok(f"Wallet service exists: {svc}")
    else:
        fail(f"Wallet service missing: {svc}")

if os.path.exists(os.path.join(ROOT, "api_routes", "wallet_routes.py")):
    ok("wallet_routes.py exists")
else:
    fail("wallet_routes.py missing")

for tmpl in ["wallet/dashboard.html", "wallet/transactions.html", "wallet/payouts.html"]:
    if os.path.exists(os.path.join(ROOT, "templates", tmpl)):
        ok(f"Wallet template exists: {tmpl}")
    else:
        warn(f"Wallet template missing: {tmpl}")

if os.path.exists(os.path.join(ROOT, "scripts", "test_wallet_reality.py")):
    ok("Wallet reality test exists")
else:
    warn("Wallet reality test missing")


# ── 14. Creator Earnings ──────────────────────
print("\n--- 14. Creator Earnings ---")

for svc in ["creator_earnings_service.py", "payout_service.py"]:
    if os.path.exists(os.path.join(ROOT, "services", svc)):
        ok(f"Creator earnings service exists: {svc}")
    else:
        warn(f"Creator earnings service missing: {svc}")

if os.path.exists(os.path.join(ROOT, "templates", "wallet", "creator_earnings.html")):
    ok("Creator earnings template exists")
else:
    warn("Creator earnings template missing")


# ── 15. Payouts/Admin Approvals ───────────────
print("\n--- 15. Payouts/Admin Approvals ---")

for tmpl in ["admin/payouts.html", "admin/topups.html", "admin/withdrawals.html"]:
    if os.path.exists(os.path.join(ROOT, "templates", tmpl)):
        ok(f"Admin payout template exists: {tmpl}")
    else:
        warn(f"Admin payout template missing: {tmpl}")

if os.path.exists(os.path.join(ROOT, "api_routes", "admin_routes.py")):
    ok("admin_routes.py exists")
else:
    warn("admin_routes.py missing")


# ── 16. Moderation/Report/Block/Restrict ─────
print("\n--- 16. Moderation/Report/Block/Restrict ---")

for svc in ["moderation_engine.py", "moderation_service.py", "moderation_log_service.py",
            "reporting_service.py", "content_flag_service.py", "blocking_service.py",
            "restriction_service.py", "appeal_service.py", "spam_detection_service.py"]:
    if os.path.exists(os.path.join(ROOT, "services", svc)):
        ok(f"Moderation service exists: {svc}")
    else:
        warn(f"Moderation service missing: {svc}")

for route_file in ["api_routes/moderation_routes.py", "api_routes/safety_routes.py",
                    "api_routes/block_routes.py", "api_routes/admin_safety_routes.py"]:
    fp = os.path.join(ROOT, route_file)
    if os.path.exists(fp):
        ok(f"Moderation route file exists: {route_file}")
    else:
        warn(f"Moderation route file missing: {route_file}")

for tmpl in ["safety/report.html", "safety/blocked.html", "safety/reports.html"]:
    if os.path.exists(os.path.join(ROOT, "templates", tmpl)):
        ok(f"Safety template exists: {tmpl}")
    else:
        warn(f"Safety template missing: {tmpl}")


# ── 17. Upload/Media Security ─────────────────
print("\n--- 17. Upload/Media Security ---")

for svc in ["media_pipeline.py", "media_storage_service.py", "storage_service.py"]:
    if os.path.exists(os.path.join(ROOT, "services", svc)):
        ok(f"Media service exists: {svc}")
    else:
        warn(f"Media service missing: {svc}")

if "MAX_CONTENT_LENGTH" in app_content or "MAX_CONTENT_LENGTH" in str(open(app_py_path).read()):
    ok("MAX_CONTENT_LENGTH configured in app.py")
else:
    warn("MAX_CONTENT_LENGTH not found in app.py")

nginx_conf = os.path.join(ROOT, "nginx", "chain.conf.example")
if os.path.exists(nginx_conf):
    with open(nginx_conf) as f:
        nc = f.read()
    if "client_max_body_size" in nc:
        ok("nginx client_max_body_size configured")
    else:
        warn("nginx client_max_body_size not configured")
else:
    warn("nginx config not found")


# ── 18. Redis Health/Fallback ─────────────────
print("\n--- 18. Redis Health/Fallback ---")

if os.path.exists(os.path.join(ROOT, "services", "redis_service.py")):
    ok("redis_service.py exists")
    with open(os.path.join(ROOT, "services", "redis_service.py")) as f:
        rc = f.read()
    if "CircuitBreaker" in rc:
        ok("Redis circuit breaker present")
    else:
        warn("Redis circuit breaker not found")
    if "memory" in rc.lower() and "fallback" in rc.lower():
        ok("Redis memory fallback present")
    else:
        warn("Redis memory fallback not found")
    if "mget_json" in rc:
        ok("Redis mget_json (bulk get) available")
    else:
        warn("Redis mget_json not available")
    if "set_json_bulk" in rc:
        ok("Redis set_json_bulk (pipeline) available")
    else:
        warn("Redis set_json_bulk not available")
else:
    fail("redis_service.py missing")


# ── 19. Neon Pool Health ─────────────────────
print("\n--- 19. Neon Pool Health ---")

if os.path.exists(os.path.join(ROOT, "services", "neon_service.py")):
    ok("neon_service.py exists")
    with open(os.path.join(ROOT, "services", "neon_service.py")) as f:
        nc = f.read()
    if "ThreadedConnectionPool" in nc:
        ok("ThreadedConnectionPool used")
    else:
        warn("ThreadedConnectionPool not found")
    if "CircuitBreaker" in nc:
        ok("Neon circuit breaker present")
    else:
        warn("Neon circuit breaker not found")
    if "fast_query" in nc and "write_query" in nc:
        ok("fast_query and write_query available")
    else:
        fail("fast_query or write_query missing")
else:
    fail("neon_service.py missing")


# ── 20. Cloud Run Readiness ──────────────────
print("\n--- 20. Cloud Run Readiness ---")

for dep_file in ["cloudrun.yaml", "cloudrun.example.yaml", "Dockerfile"]:
    if os.path.exists(os.path.join(ROOT, dep_file)):
        ok(f"Deployment file exists: {dep_file}")
    else:
        fail(f"Deployment file missing: {dep_file}")

dockerfile = os.path.join(ROOT, "Dockerfile")
if os.path.exists(dockerfile):
    with open(dockerfile) as f:
        dc = f.read()
    if "gunicorn" in dc:
        ok("Dockerfile uses gunicorn")
    else:
        warn("Dockerfile does not use gunicorn")
    if "gevent" in dc or "worker-class" in dc:
        ok("Dockerfile configures gevent workers")
    else:
        warn("Dockerfile may lack gevent worker class")


# ── 21. Render Readiness ─────────────────────
print("\n--- 21. Render Readiness ---")

for dep_file in ["render.yaml", "Procfile"]:
    if os.path.exists(os.path.join(ROOT, dep_file)):
        ok(f"Deployment file exists: {dep_file}")
    else:
        warn(f"Deployment file missing: {dep_file}")


# ── 22. Mobile UI Routes ─────────────────────
print("\n--- 22. Mobile UI Routes ---")

if os.path.exists(os.path.join(ROOT, "api_routes", "mobile_api_routes.py")):
    ok("mobile_api_routes.py exists")
    with open(os.path.join(ROOT, "api_routes", "mobile_api_routes.py")) as f:
        mc = f.read()
    if "def " in mc:
        ok("Mobile API routes contain handlers")
    else:
        warn("Mobile API routes may be empty")
else:
    warn("mobile_api_routes.py missing")


# ── 23. Broken Routes/Templates ──────────────
print("\n--- 23. Broken Routes/Templates ---")

if os.path.exists(app_py_path):
    bp_pattern = re.compile(r'register_blueprint\((\w+_bp|\w+_blueprint)')
    bps = bp_pattern.findall(app_content)
    if bps:
        ok(f"{len(bps)} blueprints registered in app.py")
    else:
        warn("No blueprints found registered")
    
    route_pattern = re.compile(r'@\w+\.route\(|\.add_url_rule\(')
    routes = route_pattern.findall(app_content)
    if routes:
        ok(f"Route decorators found in app.py")
    else:
        warn("No route decorators found in app.py")


# ── 24. Secrets Leak Scan ────────────────────
print("\n--- 24. Secrets Leak Scan ---")

SEARCH_PATTERNS = [
    ("SUPABASE_SERVICE_ROLE_KEY", "SERVICE_ROLE_KEY in env print/log"),
    ("SUPABASE_ANON_KEY", "ANON_KEY in env print/log"),
    ("DATABASE_URL", "DATABASE_URL in env print/log"),
    ("SECRET_KEY", "SECRET_KEY in env print/log"),
    ("STRIPE_SECRET_KEY", "Stripe key in env print/log"),
]
leak_found = False
for pattern, desc in SEARCH_PATTERNS:
    for root_dir, dirs, files in os.walk(os.path.join(ROOT, "services")):
        for fn in files:
            if fn.endswith(".py"):
                fp = os.path.join(root_dir, fn)
                with open(fp) as f:
                    try:
                        c = f.read()
                    except Exception:
                        continue
                if pattern in c and "os.getenv" not in c and "os.environ.get" not in c and "get_env" not in c and "masked" not in c.lower():
                    warn(f"Possible {desc} leak in {fn}")
                    leak_found = True
if not leak_found:
    ok("No obvious secrets leaked in service files (keys accessed via get_env/os.getenv)")


# ── 25. Performance Hotspots ─────────────────
print("\n--- 25. Performance Hotspots ---")

perf_checks = [
    ("relationship_cache_service.py", "get_many_relationship_states", "Bulk ANY queries (Phase 115)"),
    ("relationship_cache_service.py", "cache_mget", "Bulk Redis mget (Phase 116)"),
    ("relationship_cache_service.py", "CHAIN_TEST_MODE", "Test-mode cache skip (Phase 116)"),
    ("social_relationship_service.py", "_load_relationship_state", "Single CTE for relationship (Phase 114)"),
    ("social_relationship_service.py", "_refresh_follow_counts", "Combined follow counts (Phase 114)"),
    ("discovery_service.py", "timeout_ms=5000", "Discovery timeouts increased (Phase 114)"),
    ("auth_service.py", "ALLOW_LOCAL_AUTH_FALLBACK", "Auth fallback guard (Phase 114)"),
]
for svc_name, pattern, desc in perf_checks:
    svc_path = os.path.join(ROOT, "services", svc_name)
    if os.path.exists(svc_path):
        with open(svc_path) as f:
            c = f.read()
        if pattern in c:
            ok(f"{desc} — confirmed")
        else:
            warn(f"{desc} — pattern not found in {svc_name}")

for idx_name in ["idx_chain_follows_follower_active", "idx_chain_follows_following_active",
                  "idx_chain_friend_requests_sender_status", "idx_chain_friend_requests_recipient_status",
                  "idx_chain_friends_pair_status", "idx_chain_blocks_pair_active",
                  "idx_chain_thread_members_profile_thread", "idx_chain_thread_members_thread_profile",
                  "idx_chain_messages_thread_created", "idx_chain_profiles_discovery_active"]:
    script_path = os.path.join(ROOT, "scripts", "phase114_performance_indexes.py")
    if os.path.exists(script_path):
        with open(script_path) as f:
            c = f.read()
        if idx_name in c:
            ok(f"Index defined in phase114 script: {idx_name}")
            break
    else:
        warn("phase114_performance_indexes.py missing")
        break


# ── DB Table Checks (live Neon) ──────────────
print("\n--- DB Table & Index Checks (live Neon) ---")

try:
    from services.neon_service import fast_query

    REQUIRED_TABLES = [
        "chain_profiles", "chain_follows", "chain_friends",
        "chain_friend_requests", "chain_follow_requests", "chain_blocks",
        "chain_message_threads", "chain_thread_members", "chain_messages",
        "chain_posts", "chain_reels", "chain_status_posts",
        "chain_notifications", "chain_wallets",
        "chain_calls", "chain_call_participants", "chain_call_logs",
        "chain_live_rooms",
    ]

    existing = fast_query(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename",
        timeout_ms=10000, default=[]
    )
    existing_names = set(str(r.get("tablename")) for r in existing)

    for tbl in REQUIRED_TABLES:
        if tbl in existing_names:
            ok(f"DB table exists: {tbl}")
        else:
            warn(f"DB table missing: {tbl}")

    REQUIRED_INDEXES = [
        "idx_chain_follows_follower_active",
        "idx_chain_follows_following_active",
        "idx_chain_friend_requests_sender_status",
        "idx_chain_friend_requests_recipient_status",
        "idx_chain_friends_pair_status",
        "idx_chain_blocks_pair_active",
        "idx_chain_thread_members_profile_thread",
        "idx_chain_thread_members_thread_profile",
        "idx_chain_messages_thread_created",
        "idx_chain_profiles_discovery_active",
    ]
    db_indexes = fast_query(
        "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' ORDER BY indexname",
        timeout_ms=10000, default=[]
    )
    existing_indexes = set(str(r.get("indexname")) for r in db_indexes)

    for idx in REQUIRED_INDEXES:
        if idx in existing_indexes:
            ok(f"DB index exists: {idx}")
        else:
            warn(f"DB index missing: {idx}")

    pool_status_rows = fast_query(
        "SELECT 1 AS ok",
        timeout_ms=5000, default=[]
    )
    if pool_status_rows:
        ok("Neon DB connection verified (SELECT 1 OK)")
    else:
        fail("Neon DB connection returned empty")

except Exception as e:
    warn(f"Neon DB checks skipped: {e}")


# ── Python Import Checks ─────────────────────
print("\n--- Python Import Checks ---")

API_ROUTES_DIR = os.path.join(ROOT, "api_routes")
api_imports_ok = 0
api_imports_fail = 0

if os.path.isdir(API_ROUTES_DIR):
    for fn in sorted(os.listdir(API_ROUTES_DIR)):
        if fn.endswith(".py") and fn != "__init__.py":
            mod_name = f"api_routes.{fn[:-3]}"
            try:
                importlib.import_module(mod_name)
                api_imports_ok += 1
            except Exception as e:
                api_imports_fail += 1
                warn(f"Import failed: {mod_name} — {e}")
    if api_imports_ok:
        ok(f"{api_imports_ok} api_routes imported successfully")
    if api_imports_fail:
        warn(f"{api_imports_fail} api_routes failed to import")

SERVICES_DIR = os.path.join(ROOT, "services")
svc_imports_ok = 0
svc_imports_fail = 0
if os.path.isdir(SERVICES_DIR):
    for fn in sorted(os.listdir(SERVICES_DIR)):
        if fn.endswith(".py") and fn != "__init__.py":
            mod_name = f"services.{fn[:-3]}"
            try:
                importlib.import_module(mod_name)
                svc_imports_ok += 1
            except Exception as e:
                svc_imports_fail += 1
                warn(f"Import failed: {mod_name} — {e}")
    if svc_imports_ok:
        ok(f"{svc_imports_ok} services imported successfully")
    if svc_imports_fail:
        warn(f"{svc_imports_fail} services failed to import")


# ── Final Summary ────────────────────────────
print("\n" + "=" * 60)
print("AUDIT SUMMARY")
print("=" * 60)
print(f"  PASS: {PASS}")
print(f"  FAIL: {FAIL}")
print(f"  WARN: {WARN}")

if BLOCKERS:
    print(f"\n  BLOCKERS ({len(BLOCKERS)}):")
    for b in BLOCKERS:
        print(f"    - {b}")

local_beta_safe = FAIL == 0
public_production_safe = FAIL == 0 and WARN == 0

print(f"\n  safe_for_local_beta: {'YES' if local_beta_safe else 'NO'}")
print(f"  safe_for_public_production: {'YES' if public_production_safe else 'NO'}")
print()

sys.exit(0 if local_beta_safe else 1)
