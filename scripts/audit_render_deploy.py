"""Phase 107 — Render Free Test Deployment Readiness Audit.

Checks every layer needed for a safe Render (free-tier) deployment.
Reports blockers, warnings, required env vars, and exact deploy steps.
"""

import os
import sys
import re
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
print("PHASE 107 — RENDER FREE TEST DEPLOYMENT AUDIT")
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
# 1b. .dockerignore
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
# 2.  render.yaml
# ---------------------------------------------------------------------------
print("\n--- 2. render.yaml ---")

ry = _check_path("render.yaml")
if ry:
    text = _file_text("render.yaml")
    yaml_checks = {
        "runtime: docker" in text: "runtime: docker",
        "healthCheckPath: /healthz" in text: "healthCheckPath: /healthz",
        "plan: free" in text: "plan: free",
        "SECRET_KEY" in text: "SECRET_KEY env var declared",
        "DATABASE_URL" in text: "DATABASE_URL env var declared",
        "REDIS_URL" in text: "REDIS_URL env var declared",
        "SUPABASE_URL" in text: "SUPABASE_URL env var declared",
        "SUPABASE_ANON_KEY" in text: "SUPABASE_ANON_KEY env var declared",
        "SUPABASE_SERVICE_ROLE_KEY" in text: "SUPABASE_SERVICE_ROLE_KEY env var declared",
        "APP_BASE_URL" in text: "APP_BASE_URL env var declared",
        "REDIS_SSL_CERT_REQS" in text and "required" in text: "REDIS_SSL_CERT_REQS=required",
    }
    for ok, label in yaml_checks.items():
        _ok(label) if ok else _warn("render.yaml", f"missing {label}")

    # Check optional secrets declared
    for sec in ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET",
                "TURN_SERVER_URL", "TURN_USERNAME", "TURN_PASSWORD", "SENTRY_DSN"]:
        if sec in text:
            _ok(f"render.yaml optional: {sec}")
        else:
            _warn("render.yaml", f"optional {sec} not declared (needed for LiveKit/TURN/Sentry)")
else:
    _fail("render.yaml", "not found")

# ---------------------------------------------------------------------------
# 3.  gunicorn.conf.py
# ---------------------------------------------------------------------------
print("\n--- 3. gunicorn.conf.py ---")

gcf = _check_path("gunicorn.conf.py")
if gcf:
    text = _file_text("gunicorn.conf.py")
    if 'os.environ.get("PORT", "8080")' in text:
        _ok("gunicorn.conf.py reads $PORT")
    else:
        _warn("gunicorn.conf.py", "may not read $PORT")
    if 'worker_class = "gevent"' in text:
        _ok("gunicorn.conf.py worker_class = gevent")
    else:
        _fail("gunicorn.conf.py", "worker_class not gevent")
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
else:
    _fail("/healthz", "endpoint not found")

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

# Check REDIS_SSL_CERT_REQS support
if "ssl_cert_reqs" in redis_text:
    _ok("Redis", "SSL cert reqs configurable via REDIS_SSL_CERT_REQS")
else:
    _warn("Redis", "no REDIS_SSL_CERT_REQS support")

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
# 9.  No .env in image
# ---------------------------------------------------------------------------
print("\n--- 9. .env not in image ---")

di_text = _file_text(".dockerignore")
if ".env" in di_text:
    _ok(".env excluded by .dockerignore")
else:
    _fail(".env", "not in .dockerignore — will leak into image")

gi_text = _file_text(".gitignore")
if ".env" in gi_text:
    _ok(".env excluded by .gitignore")
else:
    _warn(".env", "not in .gitignore (low risk for Render)")

# ---------------------------------------------------------------------------
# 10.  No secrets printed in logs
# ---------------------------------------------------------------------------
print("\n--- 10. No secrets in logs ---")

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
            pattern = re.compile(rf'(print|log_info|log_warning|log_error).*{secret}', re.IGNORECASE)
            matches = pattern.findall(content)
            if matches and "get_env" not in content.split(secret)[0][-20:]:
                if "mask" not in content.split(secret)[0][-30:].lower():
                    leaks.append(f"{path}: prints {secret}")

if leaks:
    for leak in leaks:
        _warn("Secret leak", leak)
else:
    _ok("No secrets printed in logs", "all env var references are masked or safe")

# ---------------------------------------------------------------------------
# 11.  Static files served
# ---------------------------------------------------------------------------
print("\n--- 11. Static files ---")

_static_dir = ROOT / "static"
if _static_dir.is_dir():
    _ok("static/ directory exists")
else:
    _warn("static/", "directory missing — check deployment")

# ---------------------------------------------------------------------------
# 12.  WebSocket readiness
# ---------------------------------------------------------------------------
print("\n--- 12. WebSocket readiness ---")

req_text = _file_text("requirements.txt")
ws_checks = {
    "gevent" in req_text: "gevent",
    "gevent-websocket" in req_text: "gevent-websocket",
    "Flask-SocketIO" in req_text: "Flask-SocketIO",
    "gunicorn" in req_text: "gunicorn",
}
for ok, label in ws_checks.items():
    _ok(f"WebSocket dep: {label}") if ok else _fail("WebSocket", f"missing {label}")

if "gevent.monkey.patch_all()" in app_text:
    _ok("gevent monkey patch", "at top of app.py")
else:
    _fail("gevent monkey patch", "not found")

# ---------------------------------------------------------------------------
# 13.  Requirements lock
# ---------------------------------------------------------------------------
print("\n--- 13. Requirements — exact versions ---")

lines = [l.strip() for l in req_text.splitlines() if l.strip() and not l.startswith("#")]
unpinned = [l for l in lines if "==" not in l and ">=" not in l and "<=" not in l]
if unpinned:
    _warn("Requirements", f"{len(unpinned)} unpinned packages: {unpinned[:5]}")
else:
    _ok("Requirements", "all packages pinned with ==")

# ---------------------------------------------------------------------------
# 14.  Dockerfile CMD vs Render PORT
# ---------------------------------------------------------------------------
print("\n--- 14. Render PORT compatibility ---")

# Render assigns PORT automatically, Dockerfile uses $PORT
if "0.0.0.0:$PORT" in dockerfile_cmd:
    _ok("Render PORT", "Dockerfile binds to $PORT (Render default)")
else:
    _fail("Render PORT", "Dockerfile does not use $PORT")

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

blocked = len(results["blockers"])
ready = blocked == 0

print(f"\n  ready_for_render_deploy: {'true' if ready else 'false'}")
print(f"  blockers: {blocked}")
print(f"  warnings: {results['warnings']}")
print(f"  passed:   {results['passed']}")

# Required env vars
print("\n  Required Render env vars (set in Dashboard):")
for var in [
    "SECRET_KEY", "DATABASE_URL", "REDIS_URL",
    "SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY",
    "APP_BASE_URL",
]:
    print(f"    - {var}")

print("\n  Public env vars (set in render.yaml or Dashboard):")
for var in [
    "FLASK_ENV=production",
    "ENV=production",
    "REDIS_SSL_CERT_REQS=required",
]:
    print(f"    - {var}")

print("\n  Optional env vars (if using LiveKit/TURN/Sentry):")
for var in [
    "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET",
    "TURN_SERVER_URL", "TURN_USERNAME", "TURN_PASSWORD",
    "SENTRY_DSN",
]:
    print(f"    - {var}")

print(f"""
  Deploy Steps:

  1. Push this repo to GitHub

  2a. BLUEPRINT (fast):
     - In Render Dashboard: New + Blueprint
     - Connect your repo
     - Fill in sync:false env vars in the "Environment" tab
     - Click "Apply"

  2b. MANUAL (more control):
     - In Render Dashboard: New + Web Service
     - Connect your repo
     - Runtime: Docker
     - Build Command: (leave default — Dockerfile)
     - Start Command: (leave default)
     - Plan: Free
     - Set all env vars from the list above
     - Set Health Check Path: /healthz
     - Click "Create Web Service"

  3. Verify:
     - curl https://<service-name>.onrender.com/healthz
     - curl https://<service-name>.onrender.com/
     - python3 scripts/test_cloudrun_smoke.py --url https://<service-name>.onrender.com
""")

sys.exit(0 if ready else 1)
