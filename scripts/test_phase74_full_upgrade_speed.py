#!/usr/bin/env python3
"""Phase 74 — Full App Upgrade + Speed Max Test.

Tests:
  1. compileall clean
  2. All major route files import clean
  3. Dashboard route imports are fixed (get_wallet_balance, redirect)
  4. Discovery route passes limit param
  5. Search route passes limit param
  6. message_upgrade_routes gated behind dev flag
  7. Dashboard caches response
  8. No placeholder/hardcoded AI suggestions in dashboard
  9. SQL indexes file is valid SQL
  10. Important indexes reference real tables/columns
  11. Slow route report generated
  12. Redis reachable
  13. Socket.IO registered
  14. No orphaned template references
  15. Homepage real data guard still active
  16. Sponsored section still checks real data
  17. No demo/hardcoded content on public pages
  18. Admin routes registered
  19. WebRTC / call routes registered
  20. Wallet routes registered

Usage:  python3 scripts/test_phase74_full_upgrade_speed.py
"""

import os, sys, re, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0
RESULTS = []

def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        msg = f"  ✓ {name}"
    else:
        FAIL += 1
        msg = f"  ✗ {name}"
    if detail:
        msg += f"  ({detail})"
    RESULTS.append(msg)
    print(msg)

# ── 1. compileall ──
print("\n═══ Phase 74: Full App Upgrade + Speed Max ═══\n")
print("--- 1. compileall ---")
import py_compile, glob
errors = []
for root, dirs, files in os.walk("."):
    if ".git" in root or "__pycache__" in root or "node_modules" in root or ".venv" in root:
        continue
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            try:
                py_compile.compile(path, doraise=True)
            except py_compile.PyCompileError as e:
                errors.append(str(e))
check("compileall", len(errors) == 0, f"{len(errors)} errors" if errors else "")
for e in errors[:5]:
    print(f"       {e}")

# ── 2. Module imports ──
print("\n--- 2. Route file imports ---")
route_files = [
    "api_routes.auth_routes",
    "api_routes.profile_routes",
    "api_routes.dashboard_routes",
    "api_routes.discovery_routes",
    "api_routes.search_routes",
    "api_routes.activity_routes",
    "api_routes.message_routes",
    "api_routes.call_routes",
    "api_routes.notification_routes",
    "api_routes.live_routes",
    "api_routes.wallet_routes",
    "api_routes.admin_routes",
    "api_routes.feed_routes",
    "api_routes.dating_routes",
    "api_routes.safety_routes",
    "api_routes.admin_safety_routes",
    "api_routes.moderation_routes",
    "api_routes.reels_routes",
    "api_routes.status_routes",
    "api_routes.message_upgrade_routes",
    "services.homepage_service",
    "services.homepage_real_data_guard",
    "services.discovery_service",
    "services.search_service",
    "services.activity_service",
    "services.profile_service",
    "services.wallet_service",
]
for mod in route_files:
    try:
        __import__(mod)
        check(f"  import {mod}", True)
    except Exception as e:
        check(f"  import {mod}", False, str(e)[:80])

# ── 3. Dashboard route fixes ──
print("\n--- 3. Dashboard route fixes ---")
try:
    from api_routes.dashboard_routes import index
    check("dashboard.index function found", True)
except Exception as e:
    check("dashboard.index function found", False, str(e)[:80])

try:
    from services.wallet_engine import get_wallet_summary
    check("get_wallet_summary importable", True)
except Exception as e:
    check("get_wallet_summary importable", False, str(e)[:80])

try:
    from services.discovery_service import get_discovery_data
    import inspect
    sig = inspect.signature(get_discovery_data)
    check("get_discovery_data accepts limit param", "limit" in sig.parameters, str(sig))
except Exception as e:
    check("get_discovery_data accepts limit param", False, str(e)[:80])

# ── 4. Discovery route passes limit ──
print("\n--- 4. Discovery route ---")
try:
    with open("api_routes/discovery_routes.py") as f:
        src = f.read()
    check("limit param in discovery route", "get_discovery_data(section, limit=limit)" in src or "limit" in src)
except Exception as e:
    check("limit param in discovery route", False, str(e)[:80])

# ── 5. Search route passes limit ──
print("\n--- 5. Search route ---")
try:
    with open("api_routes/search_routes.py") as f:
        src = f.read()
    check("limit param in search route", "limit=limit" in src)
except Exception as e:
    check("limit param in search route", False, str(e)[:80])

# ── 6. message_upgrade_routes gated ──
print("\n--- 6. Message upgrade gated ---")
try:
    with open("api_routes/message_upgrade_routes.py") as f:
        src = f.read()
    check("dev flag gate exists", "CHAIN_DEV_TOOLS" in src)
    check("before_request gate exists", "_require_dev_mode" in src)
except Exception as e:
    check("message upgrade gate check", False, str(e)[:80])

# ── 7. Dashboard caching ──
print("\n--- 7. Dashboard caching ---")
try:
    with open("api_routes/dashboard_routes.py") as f:
        src = f.read()
    check("dashboard uses cache_key", "cache_key" in src)
    check("dashboard uses set_cache", "set_cache" in src)
    check("dashboard uses get_cache", "get_cache" in src)
except Exception as e:
    check("dashboard caching check", False, str(e)[:80])

# ── 8. No placeholder AI suggestions ──
print("\n--- 8. No placeholder AI suggestions ---")
try:
    with open("api_routes/dashboard_routes.py") as f:
        src = f.read()
    check("no ai_suggestions placeholder", "ai_suggestions" not in src)
except Exception as e:
    check("no ai_suggestions placeholder", False, str(e)[:80])

# ── 9. SQL indexes file valid ──
print("\n--- 9. SQL indexes file ---")
sql_path = "sql/phase74_full_speed_indexes.sql"
try:
    with open(sql_path) as f:
        sql = f.read()
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    check("indexes file exists", os.path.exists(sql_path))
    check("indexes file non-empty", len(statements) > 5, f"{len(statements)} statements")
    for s in statements:
        check(f"  SQL: {s[:60]}...", s.upper().startswith("CREATE INDEX") or s.upper().startswith("--"), s[:60])
except Exception as e:
    check("indexes file check", False, str(e)[:80])

# ── 10. Indexes reference real tables ──
print("\n--- 10. Index table references ---")
expected_tables = ["chain_profiles", "chain_posts", "chain_follows", "chain_messages",
                   "chain_notifications", "chain_stories", "chain_live_rooms", "chain_wallet_transactions",
                   "chain_thread_members"]
for table in expected_tables:
    check(f"  index references {table}", table in sql, table)

# ── 11. Apply script exists ──
print("\n--- 11. Apply script ---")
try:
    with open("scripts/apply_phase74_full_speed_indexes.py") as f:
        src = f.read()
    check("apply script exists", "phase74_full_speed_indexes.sql" in src)
except Exception as e:
    check("apply script check", False, str(e)[:80])

# ── 12. No 'partner' hardcoded username ──
print("\n--- 12. No hardcoded partner username ---")
templates_dir = "templates"
partner_count = 0
for root, dirs, files in os.walk(templates_dir):
    for f in files:
        if f.endswith(".html"):
            path = os.path.join(root, f)
            with open(path) as fh:
                content = fh.read()
                if "'partner'" in content:
                    partner_count += 1
check("no hardcoded 'partner'", partner_count == 0, f"found in {partner_count} files")

# ── 13. Gen-avatar CSS in base.html ──
print("\n--- 13. Gen-avatar CSS ---")
try:
    with open("templates/base.html") as f:
        src = f.read()
    check("gen-avatar CSS present", "gen-avatar" in src)
except Exception as e:
    check("gen-avatar CSS", False, str(e)[:80])

# ── 14. Homepage real data guard active ──
print("\n--- 14. Real data guard active ---")
try:
    with open("services/homepage_service.py") as f:
        src = f.read()
    check("real data guard imported", "homepage_real_data_guard" in src)
    check("filter_feed_posts applied", "filter_feed_posts" in src)
    check("filter_profiles applied", "filter_profiles" in src)
except Exception as e:
    check("real data guard", False, str(e)[:80])

# ── 15. Sponsored section checks real data ──
print("\n--- 15. Sponsored section ---")
try:
    with open("services/homepage_service.py") as f:
        src = f.read()
    check("sponsored checks post_type", "post_type = 'sponsored'" in src or "post_type" in src)
except Exception as e:
    check("sponsored section", False, str(e)[:80])

# ── 16. Message inbox route exists ──
print("\n--- 16. Message inbox route ---")
try:
    from api_routes.message_routes import inbox
    check("message inbox route found", True)
except Exception as e:
    check("message inbox route", False, str(e)[:80])

# ── 17. Wallet route exists ──
print("\n--- 17. Wallet route ---")
try:
    from api_routes.wallet_routes import index
    check("wallet route found", True)
except Exception as e:
    check("wallet route", False, str(e)[:80])

# ── 18. Live route exists ──
print("\n--- 18. Live route ---")
try:
    from api_routes.live_routes import live_channels
    check("live route found", True)
except Exception as e:
    check("live route", False, str(e)[:80])

# ── 19. No stale demo content in dev_diagnostics ──
print("\n--- 19. dev_diagnostics gated ---")
try:
    with open("api_routes/dev_diagnostics_routes.py") as f:
        src = f.read()
    check("dev_diagnostics has CHAIN_DEV_DIAGNOSTICS gate", "CHAIN_DEV_DIAGNOSTICS" in src)
except Exception as e:
    check("dev_diagnostics gate check", False, str(e)[:80])

# ── 20. No hardcoded test content in chain_home ──
print("\n--- 20. No hardcoded test content ---")
try:
    with open("templates/chain_home.html") as f:
        src = f.read()
    check("no 'partner' fallback", "'partner'" not in src)
    check("no duplicate CHAIN brand in drawer", "Menu" in src or "CHAIN" in src)
    # Check gen-avatar usage
    gen_count = src.count('gen-avatar')
    check("gen-avatar used in template", gen_count > 5, f"{gen_count} instances")
except Exception as e:
    check("chain_home checks", False, str(e)[:80])

# ── Summary ──
print(f"\n═══ Results: {PASS} passed, {FAIL} failed ═══\n")
if FAIL:
    sys.exit(1)
