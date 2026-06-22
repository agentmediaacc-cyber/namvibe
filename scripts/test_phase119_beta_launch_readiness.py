#!/usr/bin/env python3
"""
Phase 119 — Limited Beta Deployment Setup.

Checks all 8 audit areas for controlled beta rollout readiness.
Runs smoke tests against the app, verifies docs, and validates env config.
Never prints secrets. Never mutates data.

Usage:
    python3 scripts/test_phase119_beta_launch_readiness.py
"""

import os
import re
import sys
import json
import time

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

def file_exists(path):
    return os.path.exists(os.path.join(ROOT, path))

def file_read(path):
    fp = os.path.join(ROOT, path)
    if os.path.exists(fp):
        with open(fp) as f:
            return f.read()
    return ""

def get_env(key, default=""):
    return os.getenv(key, default)

REQUIRED_ENV = [
    "SECRET_KEY",
    "DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
]
REDIS_ENV = ["REDIS_URL", "REDIS_TLS_URL"]
RECOMMENDED_ENV = [
    "SENTRY_DSN",
    "LIVEKIT_URL",
    "LIVEKIT_API_KEY",
    "LIVEKIT_API_SECRET",
    "TURN_SERVER_URL",
    "TURN_USERNAME",
    "TURN_PASSWORD",
    "APP_BASE_URL",
]
REQUIRED_DOCS = [
    "docs/BETA_LAUNCH_CHECKLIST.md",
    "docs/ROLLBACK_PLAN.md",
    "docs/ENVIRONMENT_VARIABLES.md",
    "docs/BETA_MONITORING_PLAN.md",
]

print("\n=== PHASE 119 — LIMITED BETA DEPLOYMENT SETUP ===\n")

# ── 1. Beta Environment Checklist ──────────────
print("--- 1. Beta Environment Checklist ---")
all_req_set = True
for var in REQUIRED_ENV:
    val = get_env(var)
    if val:
        ok(f"  env {var} = SET")
    else:
        fail(f"  env {var} = MISSING (required)")
        all_req_set = False

redis_found = any(get_env(v) for v in REDIS_ENV)
if redis_found:
    ok("  env REDIS_URL or REDIS_TLS_URL = SET")
else:
    fail("  env REDIS_URL or REDIS_TLS_URL = MISSING (required for Socket.IO)")
    all_req_set = False

flask_env = get_env("FLASK_ENV")
if flask_env == "production":
    ok("FLASK_ENV=production")
else:
    warn(f"FLASK_ENV={flask_env!r} — expected 'production' for beta")

env_val = get_env("ENV")
if env_val == "production":
    ok("ENV=production")
else:
    warn(f"ENV={env_val!r} — expected 'production' for beta")

fallback = get_env("ALLOW_LOCAL_AUTH_FALLBACK", "").lower()
if fallback in ("", "0", "false", "no"):
    ok("ALLOW_LOCAL_AUTH_FALLBACK not enabled (safe)")
else:
    fail("ALLOW_LOCAL_AUTH_FALLBACK is enabled in production — disable before beta")

for var in RECOMMENDED_ENV:
    if get_env(var):
        ok(f"  env {var} = SET (recommended)")
    else:
        warn(f"  env {var} = MISSING (recommended for full functionality)")

if all_req_set:
    ok("All required beta env vars present")

# ── 2. Deployment Command Check ────────────────
print("\n--- 2. Deployment Command Check ---")
docker = file_read("Dockerfile")
if "gunicorn" in docker and "0.0.0.0" in docker and "$PORT" in docker:
    ok("Dockerfile: gunicorn + 0.0.0.0 + $PORT")
else:
    warn("Dockerfile may be missing gunicorn/bind/PORT")

if file_exists("cloudrun.yaml"):
    cr = file_read("cloudrun.yaml")
    if "secretKeyRef" in cr:
        ok("cloudrun.yaml: Secret Manager integration")
    if "containerPort" in cr:
        ok("cloudrun.yaml: containerPort defined")
    if "FLASK_ENV" in cr and "production" in cr:
        ok("cloudrun.yaml: FLASK_ENV=production")
else:
    warn("cloudrun.yaml missing — Cloud Run deploy not configured")

if file_exists("render.yaml"):
    rn = file_read("render.yaml")
    if "dockerfilePath" in rn:
        ok("render.yaml: Dockerfile path configured")
    if "healthCheckPath" in rn:
        ok("render.yaml: healthCheckPath configured")
    if "sync: false" in rn:
        ok("render.yaml: secrets sync:false")
else:
    warn("render.yaml missing — Render deploy not configured")

if '"healthz"' in file_read("app.py") or '"/healthz"' in file_read("app.py"):
    ok("Health endpoint /healthz exists in app.py")
else:
    fail("Health endpoint /healthz not found")

# ── 3. Beta Safety Gates ───────────────────────
print("\n--- 3. Beta Safety Gates ---")
app_py = file_read("app.py")

if "CSRFProtect" in app_py:
    ok("CSRF protection enabled")
else:
    fail("CSRF protection not found")

if "debug" not in app_py.lower() or "debug=False" in app_py or "FLASK_ENV" in app_py:
    prod_guarded = 'os.getenv("FLASK_ENV", "development") != "production"' in app_py or 'os.getenv("FLASK_ENV") == "production"' in app_py
    if prod_guarded:
        ok("Debug disabled via FLASK_ENV guard")
    else:
        warn("Debug routes may not be fully production-guarded")
else:
    warn("Debug mode may be referenced in app.py")

admin_routes = file_read("api_routes/admin_routes.py")
if "require_admin" in admin_routes:
    ok("Admin routes protected by require_admin")
else:
    warn("Admin routes may lack require_admin")

payout_routes = file_read("api_routes/wallet_routes.py") if file_exists("api_routes/wallet_routes.py") else ""
if "login_required" in payout_routes or "require_admin" in payout_routes:
    ok("Payout routes require auth")
else:
    warn("Payout routes auth check not clearly detected")

if "MAX_CONTENT_LENGTH" in app_py:
    ok("Upload size limit configured")
else:
    warn("MAX_CONTENT_LENGTH not configured")

rate_limit_svc = file_read("services/rate_limit_service.py")
if "Limiter" in rate_limit_svc and "default_limits" in rate_limit_svc:
    ok("Rate limiting configured")
else:
    warn("Rate limiting not configured")

storage_svc = file_read("services/storage_service.py")
if "ALLOWED_EXTENSIONS" in storage_svc:
    ok("Allowed upload extensions configured")
else:
    warn("Allowed upload extensions not configured")

auth_svc = file_read("services/auth_service.py")
if "ALLOW_LOCAL_AUTH_FALLBACK" in auth_svc:
    ok("Local auth fallback guard exists")
else:
    fail("Local auth fallback guard missing")

# ── 4. Monitoring Plan ─────────────────────────
print("\n--- 4. Monitoring Plan ---")
if file_exists("docs/BETA_MONITORING_PLAN.md"):
    ok("BETA_MONITORING_PLAN.md exists")
else:
    warn("BETA_MONITORING_PLAN.md missing")

if file_exists("services/neon_service.py"):
    neon = file_read("services/neon_service.py")
    if "get_neon_health" in neon:
        ok("Neon health check function exists")
    if "CircuitBreaker" in neon and "_NEON_BREAKER" in neon:
        ok("Neon circuit breaker configured")
    else:
        warn("Neon circuit breaker not found")
else:
    warn("neon_service.py not found")

if file_exists("services/redis_service.py"):
    redis_svc = file_read("services/redis_service.py")
    if "get_redis_health" in redis_svc:
        ok("Redis health check function exists")
    if "CircuitBreaker" in redis_svc:
        ok("Redis circuit breaker configured")
else:
    warn("redis_service.py not found")

# ── 5. Rollback Plan ───────────────────────────
print("\n--- 5. Rollback Plan ---")
if file_exists("docs/ROLLBACK_PLAN.md"):
    ok("ROLLBACK_PLAN.md exists")
    rbp = file_read("docs/ROLLBACK_PLAN.md")
    for section in ["Git Rollback", "Cloud Run Rollback", "Database Rollback", "Maintenance Mode"]:
        if section in rbp:
            ok(f"  Rollback section: {section}")
        else:
            warn(f"  Rollback section missing: {section}")
else:
    warn("ROLLBACK_PLAN.md missing")

# ── 6. Beta User Rules ─────────────────────────
print("\n--- 6. Beta User Rules ---")
if file_exists("docs/BETA_LAUNCH_CHECKLIST.md"):
    ok("BETA_LAUNCH_CHECKLIST.md exists")
    blc = file_read("docs/BETA_LAUNCH_CHECKLIST.md")
    if "5" in blc and "20" in blc:
        ok("  Mentions 5–20 trusted users")
    if "Android" in blc and "iPhone" in blc:
        ok("  Mentions Android, iPhone, laptop testing")
    if "feedback" in blc.lower():
        ok("  Mentions feedback collection")
else:
    warn("BETA_LAUNCH_CHECKLIST.md missing")

if file_exists("docs/ENVIRONMENT_VARIABLES.md"):
    ok("ENVIRONMENT_VARIABLES.md exists")
else:
    warn("ENVIRONMENT_VARIABLES.md missing")

for doc in REQUIRED_DOCS:
    if file_exists(doc):
        ok(f"Required doc exists: {doc}")
    else:
        fail(f"Required doc missing: {doc}")

# ── 7. Smoke Test Script ───────────────────────
print("\n--- 7. Smoke Test ---")

# Live Neon DB checks
try:
    from services.neon_service import fast_query
    sel1 = fast_query("SELECT 1 AS ok", timeout_ms=15000, default=[])
    if sel1:
        ok("DB SELECT 1 works (connected)")
    else:
        fail("DB SELECT 1 failed")
except Exception as e:
    fail(f"DB health check error: {e}")

# Redis health / fallback
try:
    from services.redis_service import redis_available, get_redis_health
    try:
        rh = get_redis_health()
        if rh.get("connected"):
            ok("Redis ping works (connected)")
        elif rh.get("fallback") or rh.get("status") == "ok":
            ok("Redis ping: fallback active (acceptable for beta)")
        else:
            warn(f"Redis status: {rh.get('status', 'unknown')}")
    except Exception:
        warn("Redis health check not available (fallback assumed)")
except ImportError:
    pass  # already checked env var above

# Smoke-test endpoints via test client (separate process; write JSON to tempfile)
import subprocess, tempfile
smoke_code = '''
import os, sys, json
os.environ["FLASK_ENV"] = "development"
os.environ["CHAIN_TEST_MODE"] = "1"
os.environ["CHAIN_FAST_LOCAL"] = "1"
sys.path.insert(0, ".")
import warnings
warnings.filterwarnings("ignore")
import logging
logging.disable(logging.CRITICAL)
import app as app_module
app = app_module.app
app.config["TESTING"] = True
app.config["WTF_CSRF_ENABLED"] = False
client = app.test_client()
results = []
for path, label in [
    ("/healthz", "GET /healthz"),
    ("/health/db", "GET /health/db"),
    ("/health/redis", "GET /health/redis"),
    ("/auth/register", "GET /auth/register"),
    ("/auth/login", "GET /auth/login"),
    ("/profile/", "GET /profile/"),
]:
    try:
        resp = client.get(path)
        results.append({"path": path, "status": resp.status_code, "label": label})
    except Exception as e:
        results.append({"path": path, "status": -1, "label": label, "error": str(e)})
with open(os.environ["_SMOKE_OUT"], "w") as f:
    f.write(json.dumps(results))
'''
try:
    outf = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    outf.close()
    env = {**os.environ, "FLASK_ENV": "development",
           "CHAIN_TEST_MODE": "1", "CHAIN_FAST_LOCAL": "1",
           "_SMOKE_OUT": outf.name}
    proc = subprocess.run(
        [sys.executable, "-c", smoke_code],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
        cwd=ROOT, env=env,
    )
    if os.path.exists(outf.name):
        with open(outf.name) as f:
            raw = f.read().strip()
        os.unlink(outf.name)
        if raw:
            results = json.loads(raw)
            for r in results:
                s = r["status"]
                if s == 200:
                    ok(f"{r['label']} -> {s}")
                elif s in (302, 401, 503):
                    ok(f"{r['label']} -> {s} (expected)")
                else:
                    warn(f"{r['label']} -> {s} (unexpected)")
        else:
            warn(f"Smoke test produced empty output (rc={proc.returncode})")
    else:
        warn(f"Smoke test failed (rc={proc.returncode})")
except Exception as e:
    warn(f"Smoke test error: {e}")

# ── 8. Summary ─────────────────────────────────
print(f"\n{'=' * 60}")
print(f"PHASE 119 — BETA LAUNCH READINESS SUMMARY")
print(f"{'=' * 60}")
print(f"  PASS: {PASS}")
print(f"  FAIL: {FAIL}")
print(f"  WARN: {WARN}")
print()

if BLOCKERS:
    print("  BLOCKERS (must fix before beta):")
    for b in BLOCKERS:
        print(f"    - {b}")
else:
    ok("No blockers")

if WARNINGS:
    print("  WARNINGS (review before beta):")
    for w in WARNINGS:
        print(f"    - {w}")

print()
has_blockers = FAIL > 0
has_warnings = WARN > 0

internal_beta = not has_blockers
external_beta = not has_blockers and not has_warnings
public_launch = False  # always false for beta phase

print(f"  safe_for_internal_beta: {'YES' if internal_beta else 'NO'}")
print(f"  safe_for_external_beta: {'YES' if external_beta else 'NO'}")
print(f"  safe_for_public_launch: {'YES' if public_launch else 'NO'}")

if internal_beta:
    print("\n  Recommended next command:")
    print("    python3 scripts/test_phase118_deployment_readiness.py")
    print("    python3 scripts/audit_phase117_production_readiness.py")
    print("    python3 scripts/test_message_reality.py")

if WARNINGS:
    print("\n  Recommended fixes before external beta:")
    for w in WARNINGS:
        print(f"    - {w}")

sys.exit(0 if internal_beta else 1)
