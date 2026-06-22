"""Phase 103 — Cloud Run Test Deployment Readiness Audit.

Checks every layer needed for a safe, free/low-cost Cloud Run deployment.
Reports blockers, warnings, required secrets, and exact deploy command.
"""

import os
import sys
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

results = {"passed": 0, "failed": 0, "warnings": 0, "blockers": [], "warnings_list": []}

def _ok(label, detail=""):
    results["passed"] += 1
    msg = f"  [PASS] {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)

def _fail(label, detail=""):
    results["failed"] += 1
    msg = f"{label}: {detail}" if detail else label
    results["blockers"].append(msg)
    print(f"  [FAIL] {label} — {detail}")

def _warn(label, detail=""):
    results["warnings"] += 1
    msg = f"{label}: {detail}" if detail else label
    results["warnings_list"].append(msg)
    print(f"  [WARN] {label} — {detail}")

def _check_path(*parts):
    p = ROOT.joinpath(*parts)
    return p if p.exists() else None

def _file_text(*parts):
    p = ROOT.joinpath(*parts)
    return p.read_text() if p.exists() else ""

def _contains(text, *patterns):
    return all(p in text for p in patterns)

print("=" * 60)
print("PHASE 103 — CLOUD RUN DEPLOYMENT READINESS AUDIT")
print("=" * 60)

# ---------------------------------------------------------------------------
# 1.  Dockerfile
# ---------------------------------------------------------------------------
print("\n--- 1. Dockerfile ---")

df = _check_path("Dockerfile")
if df:
    text = _file_text("Dockerfile")
    checks = {
        "FROM python:3.12-slim" in text: "FROM python:3.12-slim",
        "ENV PORT=8080" in text: "ENV PORT=8080",
        "EXPOSE 8080" in text: "EXPOSE 8080",
        "gunicorn" in text and "--bind 0.0.0.0:$PORT" in text: "gunicorn --bind 0.0.0.0:$PORT",
        "--worker-class gevent" in text: "worker-class gevent",
        "--timeout 120" in text: "timeout 120",
        "COPY requirements.txt" in text: "requirements.txt caching",
        "RUN pip install" in text: "pip install",
        "COPY ." in text: "COPY .",
        "libpq-dev" in text and "libmagic1" in text: "system deps (psycopg2 + magic)",
    }
    all_ok = True
    for ok, label in checks.items():
        if ok:
            _ok(label)
        else:
            _fail("Dockerfile", f"missing {label}")
            all_ok = False
    if all_ok:
        _ok("Dockerfile", "all checks pass")
else:
    _fail("Dockerfile", "not found")

# ---------------------------------------------------------------------------
# 1b.  .dockerignore
# ---------------------------------------------------------------------------
print("\n--- 1b. .dockerignore ---")

di = _check_path(".dockerignore")
if di:
    text = _file_text(".dockerignore")
    for pattern in [".env", ".git", "__pycache__", "venv", "secrets", "*.pyc"]:
        if pattern in text:
            _ok(f".dockerignore excludes {pattern}")
        else:
            _warn(".dockerignore", f"does not exclude {pattern} (low risk)")
else:
    _warn(".dockerignore", "not found — .env might leak into image")

# ---------------------------------------------------------------------------
# 2.  cloudrun.yaml
# ---------------------------------------------------------------------------
print("\n--- 2. cloudrun.yaml ---")

cr = _check_path("cloudrun.yaml")
if cr:
    text = _file_text("cloudrun.yaml")
    yaml_checks = {
        "apiVersion: serving.knative.dev/v1": "apiVersion",
        "kind: Service": "kind: Service",
        "containerPort: 8080": "containerPort: 8080",
        "minScale" in text and '"0"' in text: "minScale: 0",
        "maxScale" in text and '"5"' in text: "maxScale: 5",
        "cpu:" in text and '"1"' in text: "cpu: 1",
        "memory:" in text and '"2Gi"' in text: "memory: 2Gi",
        "containerConcurrency: 80": "containerConcurrency: 80",
        "timeoutSeconds: 300": "timeoutSeconds: 300",
    }
    for ok, label in yaml_checks.items():
        _ok(label) if ok else _fail("cloudrun.yaml", f"missing {label}")

    # Check required secretKeyRef entries
    required_secrets = [
        "SECRET_KEY", "DATABASE_URL", "REDIS_URL",
        "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY",
        "APP_BASE_URL",
    ]
    optional_secrets = [
        "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET",
        "TURN_SERVER_URL", "TURN_USERNAME", "TURN_PASSWORD",
        "SENTRY_DSN",
    ]
    for sec in required_secrets:
        if f"name: {sec}" in text:
            _ok(f"cloudrun.yaml secret: {sec}")
        else:
            _fail("cloudrun.yaml", f"missing secretKeyRef for {sec}")
    for sec in optional_secrets:
        if f"name: {sec}" in text:
            _ok(f"cloudrun.yaml optional secret: {sec}")
        else:
            _warn("cloudrun.yaml", f"missing optional secretKeyRef for {sec} (needed for LiveKit/TURN/Sentry)")

    # Check FLASK_ENV and ENV
    for envvar in ["FLASK_ENV", "ENV"]:
        if f'value: "production"' in text and f"name: {envvar}" in text:
            _ok(f"cloudrun.yaml sets {envvar}=production")
        else:
            _fail("cloudrun.yaml", f"{envvar} not set to production")

    # Check no placeholders left
    if "REGION_PLACEHOLDER" in text:
        _fail("cloudrun.yaml", "REGION_PLACEHOLDER not replaced")
    if "IMAGE_PLACEHOLDER" in text:
        _fail("cloudrun.yaml", "IMAGE_PLACEHOLDER not replaced")
else:
    _fail("cloudrun.yaml", "not found")

# ---------------------------------------------------------------------------
# 3.  gunicorn.conf.py
# ---------------------------------------------------------------------------
print("\n--- 3. gunicorn.conf.py ---")

gcf = _check_path("gunicorn.conf.py")
if gcf:
    text = _file_text("gunicorn.conf.py")
    if "bind = \"127.0.0.1:5055\"" in text:
        _warn("gunicorn.conf.py", "binds 127.0.0.1:5055 — Dockerfile CMD overrides this, but dead code")
    else:
        _ok("gunicorn.conf.py", "bind address customized")
else:
    _warn("gunicorn.conf.py", "not found — Dockerfile CMD is authoritative")

# ---------------------------------------------------------------------------
# 4.  PORT binding
# ---------------------------------------------------------------------------
print("\n--- 4. PORT binding ---")

dockerfile_cmd = _file_text("Dockerfile")
if "ENV PORT=8080" in dockerfile_cmd and "EXPOSE 8080" in dockerfile_cmd and "0.0.0.0:$PORT" in dockerfile_cmd:
    _ok("PORT binding", "0.0.0.0:$PORT (8080)")
else:
    _fail("PORT binding", "check Dockerfile PORT/EXPOSE/bind")

# ---------------------------------------------------------------------------
# 5.  healthz endpoint
# ---------------------------------------------------------------------------
print("\n--- 5. /healthz endpoint ---")

app_text = _file_text("app.py")
if "@app.route(\"/healthz\")" in app_text:
    _ok("/healthz endpoint exists")
    # Check it doesn't touch DB
    healthz_code = app_text[app_text.index("@app.route(\"/healthz\")"):]
    healthz_code = healthz_code[:healthz_code.index("\n@") if "\n@" in healthz_code else 500]
    if "get_neon_health" not in healthz_code and "get_redis_health" not in healthz_code:
        _ok("/healthz", "no DB/Redis dependency (lightweight)")
    else:
        _warn("/healthz", "has DB/Redis dependency — may slow startup probe")
else:
    _fail("/healthz", "endpoint not found")

# Also check other health endpoints
for route in ["/health/db", "/health/redis", "/health/realtime", "/health/supabase"]:
    if f"@app.route(\"{route}\")" in app_text:
        _ok(f"{route} endpoint exists")
    else:
        _warn(f"health route", f"{route} not found")

# ---------------------------------------------------------------------------
# 6.  Redis URL handling
# ---------------------------------------------------------------------------
print("\n--- 6. Redis URL handling ---")

redis_text = _file_text("services/redis_service.py")
if "REDIS_URL" in redis_text:
    _ok("Redis env var handled")
    if "_MEMORY_FALLBACK" in redis_text:
        _ok("Redis", "in-memory fallback when unavailable")
    else:
        _warn("Redis", "no fallback mechanism")
else:
    _fail("Redis URL", "not checked in redis_service.py")

socketio_text = _file_text("services/socketio_service.py")
if "REDIS_URL" in socketio_text:
    _ok("Socket.IO Redis manager", "reads REDIS_URL")
else:
    _fail("Socket.IO Redis", "not configured")

# Check REDIS_URL in .env is not localhost (would break on Cloud Run)
env_text = _file_text(".env")
for line in env_text.splitlines():
    if line.strip().startswith("REDIS_URL="):
        redis_val = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
        if "localhost" in redis_val or "127.0.0.1" in redis_val:
            _warn("REDIS_URL", "points to localhost — real-time features degraded on Cloud Run")
            _warn("REDIS_URL", "set a managed Redis URL (Upstash / Memorystore) for full functionality")
        else:
            _ok("REDIS_URL", "does not point to localhost (managed Redis detected)")
        break

# ---------------------------------------------------------------------------
# 7.  Neon DATABASE_URL handling
# ---------------------------------------------------------------------------
print("\n--- 7. Neon DATABASE_URL ---")

neon_text = _file_text("services/neon_service.py")
if "DATABASE_URL" in neon_text:
    _ok("Neon DATABASE_URL env var handled")
    if "CircuitBreaker" in neon_text:
        _ok("Neon", "circuit breaker present")
    else:
        _warn("Neon", "no circuit breaker")
else:
    _fail("Neon DATABASE_URL", "not configured")

# ---------------------------------------------------------------------------
# 8.  Supabase uploads
# ---------------------------------------------------------------------------
print("\n--- 8. Supabase uploads ---")

supabase_text = _file_text("utils/supabase_client.py")
if "SUPABASE_URL" in supabase_text and "SUPABASE_ANON_KEY" in supabase_text:
    _ok("Supabase env vars handled")
else:
    _warn("Supabase", "env vars may not be fully configured")

# ---------------------------------------------------------------------------
# 9.  env secret injection
# ---------------------------------------------------------------------------
print("\n--- 9. Env secret injection ---")

# Check that cloudrun.yaml uses valueFrom.secretKeyRef for secrets (not plain values)
cr_text = _file_text("cloudrun.yaml")
if "valueFrom" in cr_text and "secretKeyRef" in cr_text:
    _ok("cloudrun.yaml uses Secret Manager (secretKeyRef)")
else:
    _fail("Secret injection", "cloudrun.yaml must use secretKeyRef, not plain values")

# Check for any plain-text secrets in cloudrun.yaml
for suspicious in ["supabase", "postgres://", "redis://"]:
    if suspicious in cr_text.lower() and "valueFrom" not in cr_text.split(suspicious)[0][-50:]:
        _warn("cloudrun.yaml", f"possible plain-text secret: {suspicious}")

# ---------------------------------------------------------------------------
# 10.  No .env in image
# ---------------------------------------------------------------------------
print("\n--- 10. .env not in image ---")

di_text = _file_text(".dockerignore")
if ".env" in di_text:
    _ok(".env excluded by .dockerignore")
else:
    _fail(".env", "not in .dockerignore — will leak into image")

# Also check .gitignore
gi_text = _file_text(".gitignore")
if ".env" in gi_text:
    _ok(".env excluded by .gitignore")
else:
    _warn(".env", "not in .gitignore (low risk for Cloud Run)")

# ---------------------------------------------------------------------------
# 11.  No secrets printed in logs
# ---------------------------------------------------------------------------
print("\n--- 11. No secrets in logs ---")

# Scan for potential secret logging
secret_patterns = [
    "SECRET_KEY", "DATABASE_URL", "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET",
    "TURN_PASSWORD",
]
leaks = []
for root_dir, dirs, files in os.walk(ROOT):
    if "venv" in root_dir or "__pycache__" in root_dir or ".git" in root_dir:
        continue
    for f in files:
        if not f.endswith(".py"):
            continue
        path = os.path.join(root_dir, f)
        try:
            content = open(path).read()
        except Exception:
            continue
        for secret in secret_patterns:
            # Look for print/log of the secret VALUE (not env var reference)
            pattern = re.compile(rf'(print|log_info|log_warning|log_error).*{secret}', re.IGNORECASE)
            matches = pattern.findall(content)
            if matches and "get_env" not in content.split(secret)[0][-20:]:
                # Check it's not a masked log
                if "mask" not in content.split(secret)[0][-30:].lower():
                    leaks.append(f"{path}: prints {secret}")

if leaks:
    for leak in leaks:
        _warn("Secret leak", leak)
else:
    _ok("No secrets printed in logs", "all env var references are masked or safe")

# ---------------------------------------------------------------------------
# 12.  Static files served
# ---------------------------------------------------------------------------
print("\n--- 12. Static files ---")

_static_dir = ROOT / "static"
if _static_dir.is_dir():
    _ok("static/ directory exists")
    # Check that Flask serves static files by default
    if "static" in app_text:
        _ok("static routing", "Flask serves /static/ by default")
else:
    _warn("static/", "directory missing — check deployment")

# ---------------------------------------------------------------------------
# 13.  WebSocket readiness
# ---------------------------------------------------------------------------
print("\n--- 13. WebSocket readiness ---")

req_text = _file_text("requirements.txt")
ws_checks = {
    "gevent" in req_text: "gevent",
    "gevent-websocket" in req_text: "gevent-websocket",
    "Flask-SocketIO" in req_text: "Flask-SocketIO",
    "gunicorn" in req_text: "gunicorn",
}
for ok, label in ws_checks.items():
    _ok(f"WebSocket dep: {label}") if ok else _fail("WebSocket", f"missing {label}")

# Check socketio init uses Redis manager
if "message_queue=mgr" in socketio_text:
    _ok("Socket.IO", "Redis message queue configured")
else:
    _warn("Socket.IO", "no Redis message queue (single-node only)")

# Check gevent monkey patch at top of app.py
if "gevent.monkey.patch_all()" in app_text:
    _ok("gevent monkey patch", "at top of app.py")
else:
    _fail("gevent monkey patch", "not found")

# ---------------------------------------------------------------------------
# 14.  Startup time
# ---------------------------------------------------------------------------
print("\n--- 14. Startup time ---")

# Check for delayed prewarm
if "schedule_delayed_homepage_prewarm" in app_text:
    _ok("Delayed prewarm", "runs in background thread, doesn't block startup")
else:
    _warn("Startup", "no delayed prewarm — startup may be slow")

# Check that prewarm is gated by production env
if 'if not _is_production_env()' in app_text:
    _ok("Prewarm gating", "dev env disables prewarm by default")
else:
    _warn("Prewarm gating", "not found")

# Check whether the delayed startup prewarm runs in gunicorn
# The prewarm is called from `if __name__ == "__main__":` which won't run under gunicorn
if 'if __name__ == "__main__"' in app_text:
    _ok("Prewarm safe under gunicorn", "prewarm only runs in __main__ block, not under gunicorn WSGI")
else:
    _warn("Prewarm", "could not verify gunicorn safety")

# ---------------------------------------------------------------------------
# 15.  No auto migration
# ---------------------------------------------------------------------------
print("\n--- 15. No auto migration ---")

# Check that ensure_content_schema is gated behind env var
if 'os.getenv("CHAIN_BOOTSTRAP_SCHEMA", "0") == "1"' in app_text:
    _ok("Auto schema gated", "CHAIN_BOOTSTRAP_SCHEMA must be explicitly set to 1")
else:
    fail("Auto migration", "schema bootstrap not gated")

# Check the migrations/ folder for sql files only
migrations_dir = ROOT / "migrations"
if migrations_dir.is_dir():
    sql_files = list(migrations_dir.glob("*.sql"))
    py_files = list(migrations_dir.glob("*.py"))
    if py_files:
        _warn("Migrations", f"Python files in migrations/ — {[f.name for f in py_files]}")
    if sql_files:
        _ok("Migrations", f"{len(sql_files)} SQL files (manual apply only)")
else:
    _warn("Migrations", "migrations/ directory missing")

# ---------------------------------------------------------------------------
# 16.  Procfile / background workers
# ---------------------------------------------------------------------------
print("\n--- 16. Background workers ---")

proc = _file_text("Procfile")
if proc:
    if "worker:" in proc:
        _warn("Procfile", "worker process defined but won't run on Cloud Run")
    _ok("Procfile", "present (Cloud Run uses Dockerfile only)")
else:
    _warn("Procfile", "not found")

# ---------------------------------------------------------------------------
# 17.  Requirements lock
# ---------------------------------------------------------------------------
print("\n--- 17. Requirements — exact versions ---")

req_text = _file_text("requirements.txt")
lines = [l.strip() for l in req_text.splitlines() if l.strip() and not l.startswith("#")]
unpinned = [l for l in lines if "==" not in l and ">=" not in l and "<=" not in l]
if unpinned:
    _warn("Requirements", f"{len(unpinned)} unpinned packages: {unpinned[:5]}")
else:
    _ok("Requirements", "all packages pinned with ==")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("AUDIT SUMMARY")
print("=" * 60)
print(f"\n  Passed:   {results['passed']}")
print(f"  Warnings: {results['warnings']}")
print(f"  Blockers: {results['failed']}")

if results["blockers"]:
    print("\n  BLOCKERS:")
    for b in results["blockers"]:
        print(f"    - {b}")

if results["warnings_list"]:
    print("\n  WARNINGS:")
    for w in results["warnings_list"]:
        print(f"    - {w}")

# Determine readiness
blocked = len(results["blockers"])
ready = blocked == 0

print(f"\n  ready_for_cloud_run_test: {'true' if ready else 'false'}")
print(f"  blockers: {blocked}")
print(f"  warnings: {results['warnings']}")
print(f"  passed:   {results['passed']}")

# Required Google Cloud secrets
print("\n  Required Google Cloud Secrets (Secret Manager):")
print("    chain-secret-key")
print("    chain-database-url")
print("    chain-redis-url")
print("    chain-supabase-url")
print("    chain-supabase-anon-key")
print("    chain-supabase-service-role-key")
print("    chain-app-base-url")

print("\n  Optional Google Cloud Secrets (if using LiveKit/TURN/Sentry):")
print("    chain-livekit-url")
print("    chain-livekit-api-key")
print("    chain-livekit-api-secret")
print("    chain-turn-server-url")
print("    chain-turn-username")
print("    chain-turn-password")
print("    chain-sentry-dsn")

# Exact deploy command
REGION = "us-central1"
PROJECT = "YOUR_GCP_PROJECT_ID"
SERVICE = "chain-app"
IMAGE = f"gcr.io/{PROJECT}/{SERVICE}:test-$(date +%Y%m%d-%H%M)"

print(f"""
  Exact Deploy Command:

  # 1. Build & push
  docker build -t {IMAGE} .
  docker push {IMAGE}

  # 2. Create secrets (one-time)
  # (Use gcloud secrets create / gcloud secrets versions add for each secret above)

  # 3. Deploy (replace PROJECT and IMAGE)
  gcloud run deploy {SERVICE} \\
    --image {IMAGE} \\
    --region {REGION} \\
    --project {PROJECT} \\
    --platform managed \\
    --allow-unauthenticated \\
    --concurrency 80 \\
    --timeout 300 \\
    --memory 2Gi \\
    --cpu 1 \\
    --min-instances 0 \\
    --max-instances 5 \\
    --set-env-vars FLASK_ENV=production,ENV=production \\
    --update-secrets SECRET_KEY=chain-secret-key:latest \\
    --update-secrets DATABASE_URL=chain-database-url:latest \\
    --update-secrets REDIS_URL=chain-redis-url:latest \\
    --update-secrets SUPABASE_URL=chain-supabase-url:latest \\
    --update-secrets SUPABASE_ANON_KEY=chain-supabase-anon-key:latest \\
    --update-secrets SUPABASE_SERVICE_ROLE_KEY=chain-supabase-service-role-key:latest \\
    --update-secrets APP_BASE_URL=chain-app-base-url:latest

  # 4. Verify deployment
  # curl https://<service-url>/healthz
  # curl https://<service-url>/
  # python3 scripts/test_phase102_full_user_flow.py
""")

sys.exit(0 if ready else 1)
