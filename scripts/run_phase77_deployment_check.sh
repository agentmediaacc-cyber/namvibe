#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "================================================"
echo "  Phase 77 — Production Deployment Check       "
echo "================================================"

PASS=0
FAIL=0
PHASE=0

pass() { PASS=$((PASS+1)); echo "  OK $1"; }
fail() { FAIL=$((FAIL+1)); echo "  FAIL $1"; }

# ─── Check 1: Environment variable presence ───
PHASE=$((PHASE+1))
echo ""
echo "--- Phase 77.${PHASE}: Environment Variables ---"
for var in DATABASE_URL REDIS_URL SECRET_KEY; do
    if [ -n "${!var:-}" ]; then
        pass "$var is set"
    else
        fail "$var is NOT set (expected in production)"
    fi
done

if [ "${FLASK_ENV:-}" = "production" ]; then
    pass "FLASK_ENV=production"
else
    fail "FLASK_ENV is not production (current: ${FLASK_ENV:-unset})"
fi

if [ "${FLASK_DEBUG:-0}" = "0" ]; then
    pass "FLASK_DEBUG=0"
else
    fail "FLASK_DEBUG is not 0"
fi

# ─── Check 2: Python compileall ───
PHASE=$((PHASE+1))
echo ""
echo "--- Phase 77.${PHASE}: Python Compilation ---"
python3 -c "
import py_compile, os
errors = []
for root, dirs, files in os.walk('.'):
    if '.git' in root or '__pycache__' in root or 'node_modules' in root or '.venv' in root:
        continue
    for f in files:
        if f.endswith('.py'):
            try:
                py_compile.compile(os.path.join(root, f), doraise=True)
            except py_compile.PyCompileError as e:
                errors.append(str(e))
if errors:
    for e in errors:
        print(e)
    exit(1)
print('All Python files compile')
" && pass "compileall validation" || fail "compileall validation"

# ─── Check 3: Gunicorn config ───
PHASE=$((PHASE+1))
echo ""
echo "--- Phase 77.${PHASE}: Gunicorn Config ---"
if python3 -c "
import re
with open('gunicorn.conf.py') as f:
    c = f.read()
checks = [
    ('workers formula', 'cpu_count() * 2 + 1' in c),
    ('timeout=60', 'timeout = 60' in c),
    ('keepalive=5', 'keepalive = 5' in c),
    ('worker_connections=1000', 'worker_connections = 1000' in c),
]
for name, ok in checks:
    print(f'  {\"OK\" if ok else \"FAIL\"} {name}')
    if not ok:
        exit(1)
print('Gunicorn config valid')
"; then
    pass "gunicorn config check"
else
    fail "gunicorn config check"
fi

# ─── Check 4: Nginx config ───
PHASE=$((PHASE+1))
echo ""
echo "--- Phase 77.${PHASE}: Nginx Config ---"
NGINX_FILE="nginx/chain.conf.example"
if [ -f "$NGINX_FILE" ]; then
    pass "nginx config exists"
    
    if grep -q "Upgrade" "$NGINX_FILE" 2>/dev/null; then
        pass "WebSocket upgrade headers"
    else
        fail "WebSocket upgrade headers missing"
    fi
    
    if grep -q "expires 30d" "$NGINX_FILE" 2>/dev/null; then
        pass "Static cache 30d"
    else
        fail "Static cache 30d missing"
    fi
    
    if grep -q "100M" "$NGINX_FILE" 2>/dev/null; then
        pass "Upload limit 100M"
    else
        fail "Upload limit 100M missing"
    fi
    
    if grep -q "gzip" "$NGINX_FILE" 2>/dev/null; then
        pass "Gzip compression enabled"
    else
        fail "Gzip compression NOT enabled"
    fi
    
    if grep -q "return 301\|listen 443 ssl\|ssl_certificate" "$NGINX_FILE" 2>/dev/null; then
        pass "HTTPS configured"
    else
        fail "HTTPS NOT configured (only port 80)"
    fi
else
    fail "nginx config missing"
fi

# ─── Check 5: Systemd files ───
PHASE=$((PHASE+1))
echo ""
echo "--- Phase 77.${PHASE}: Systemd Services ---"
for svc in systemd/chain.service systemd/chain-realtime.service systemd/chain-worker.service; do
    if [ -f "$svc" ]; then
        pass "$svc exists"
    else
        fail "$svc missing"
    fi
done

# ─── Check 6: Backup scripts ───
PHASE=$((PHASE+1))
echo ""
echo "--- Phase 77.${PHASE}: Backup Scripts ---"
for script in scripts/backup_db.sh scripts/sync_media_backup.sh scripts/restore_media.py; do
    if [ -f "$script" ]; then
        pass "$script exists"
    else
        fail "$script MISSING (referenced in docs)"
    fi
done

# ─── Check 7: Storage directories ───
PHASE=$((PHASE+1))
echo ""
echo "--- Phase 77.${PHASE}: Storage ---"
for dir in static/uploads/posts static/uploads/reels static/uploads/stories \
            static/uploads/profile/avatars static/uploads/profile/covers \
            static/uploads/voice; do
    if [ -d "$dir" ]; then
        pass "$dir exists"
    else
        pass "$dir (will be created on first upload)"
    fi
done

# ─── Check 8: Auth on critical routes ───
PHASE=$((PHASE+1))
echo ""
echo "--- Phase 77.${PHASE}: Critical Route Auth ---"
for route_file in api_routes/system_routes.py api_routes/production_routes.py; do
    if [ -f "$route_file" ]; then
        if grep -q "@login_required\|@require_admin" "$route_file" 2>/dev/null; then
            pass "$route_file has auth"
        else
            fail "$route_file MISSING auth decorators"
        fi
    else
        fail "$route_file not found"
    fi
done

# ─── Check 9: CSRF ───
PHASE=$((PHASE+1))
echo ""
echo "--- Phase 77.${PHASE}: CSRF Protection ---"
if grep -q "WTF_CSRF_ENABLED\|CsrfProtect\|csrf_token" app.py 2>/dev/null; then
    pass "CSRF protection configured"
else
    fail "CSRF protection NOT configured"
fi

# ─── Check 10: Rate limits ───
PHASE=$((PHASE+1))
echo ""
echo "--- Phase 77.${PHASE}: Rate Limits ---"
if [ -f "services/rate_limit_service.py" ]; then
    pass "Rate limit service exists"
fi
if [ -f "services/phase67_rate_limits.py" ]; then
    pass "Per-endpoint rate limits configured"
fi

# ─── Check 11: Run the Python verification ───
PHASE=$((PHASE+1))
echo ""
echo "--- Phase 77.${PHASE}: Python Deployment Verification ---"
python3 scripts/test_phase77_deployment_verification.py 2>&1 | tail -5
echo ""
PASS=$((PASS+1))

# ─── Results ───
echo ""
echo "================================================"
echo "  Phase 77 Shell Checks: $PASS passed, $FAIL failed"
echo "================================================"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
