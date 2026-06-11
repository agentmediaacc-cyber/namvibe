#!/usr/bin/env bash
#
# Phase 70 — Full Local Pre-VPS Check
# Runs compileall, Redis check, Flask app smoke, and phase70 inspection.
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PASS=0
FAIL=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { PASS=$((PASS+1)); echo -e "  ${GREEN}[PASS]${NC} $1"; }
fail() { FAIL=$((FAIL+1)); echo -e "  ${RED}[FAIL]${NC} $1"; }
warn() { echo -e "  ${YELLOW}[WARN]${NC} $1"; }

echo ""
echo "============================================================"
echo " Phase 70 — Full Local Pre-VPS Check"
echo "============================================================"
echo ""

# ── 1. Activate virtual environment ─────────────────────────────
echo "--- 1. Virtual Environment ---"
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || true
    pass "venv activated"
elif [ -d ".venv" ]; then
    source .venv/bin/activate 2>/dev/null || true
    pass ".venv activated"
else
    warn "No virtual environment found (venv/ or .venv/)"
fi

# Check Python version
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0")
if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
    pass "Python $PY_VER (>= 3.10)"
else
    fail "Python $PY_VER (< 3.10 required)"
fi

# ── 2. Check Redis ──────────────────────────────────────────────
echo ""
echo "--- 2. Redis ---"
if command -v redis-cli &>/dev/null; then
    if redis-cli ping 2>/dev/null | grep -q "PONG"; then
        pass "Redis is running"
    else
        warn "Redis not responding — start with: redis-server &"
    fi
elif lsof -i :6379 -P 2>/dev/null | grep -q LISTEN; then
    pass "Redis port 6379 listening"
else
    warn "Redis not detected — some features will fall back"
fi

# ── 3. Python compileall ─────────────────────────────────────────
echo ""
echo "--- 3. Python Compilation ---"
if python3 -m compileall . -q 2>/dev/null; then
    pass "compileall clean"
else
    python3 -m compileall . -q 2>&1 | head -20
    fail "compileall has errors"
fi

# ── 4. Flask App Import ──────────────────────────────────────────
echo ""
echo "--- 4. Flask App Import ---"
START=$SECONDS
if python3 -c "
import os
os.environ['CHAIN_DISABLE_CALL_WORKER'] = '1'
os.environ['CHAIN_DISABLE_SCHEDULER'] = '1'
from app import create_app
app = create_app()
print('OK')
" 2>&1 | tail -1 | grep -q '^OK$'; then
    ELAPSED=$((SECONDS - START))
    pass "Flask app imports cleanly (${ELAPSED}s)"
else
    python3 -c "
import os
os.environ['CHAIN_DISABLE_CALL_WORKER'] = '1'
os.environ['CHAIN_DISABLE_SCHEDULER'] = '1'
from app import create_app
app = create_app()
" 2>&1 | tail -20
    fail "Flask app import failed"
fi

# ── 5. Health Check (if app is running) ──────────────────────────
echo ""
echo "--- 5. App Health ---"
if curl -sf http://127.0.0.1:5000/system/api/realtime-health > /dev/null 2>&1; then
    HEALTH=$(curl -s http://127.0.0.1:5000/system/api/realtime-health)
    if echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('ok') else 1)" 2>/dev/null; then
        pass "App health endpoint OK"
    else
        warn "Health endpoint returned: $HEALTH"
    fi
else
    warn "App not running on :5000 — start with: python3 run.py"
fi

# ── 6. Dependency Check ──────────────────────────────────────────
echo ""
echo "--- 6. Dependencies ---"
if [ -f "requirements.txt" ]; then
    python3 -c "
import pkg_resources, sys
with open('requirements.txt') as f:
    reqs = pkg_resources.parse_requirements(f)
missing = []
for r in reqs:
    try:
        pkg_resources.working_set.require(str(r))
    except Exception:
        missing.append(str(r))
if missing:
    print('MISSING:', ' '.join(missing))
    sys.exit(1)
else:
    print('OK')
" 2>&1 | tail -1 | grep -q '^OK$' && pass "All requirements installed" || warn "Some requirements missing — run: pip install -r requirements.txt"
else
    warn "No requirements.txt found"
fi

# ── 7. Git Security ──────────────────────────────────────────────
echo ""
echo "--- 7. Git Security ---"
if git rev-parse --git-dir > /dev/null 2>&1; then
    TRACKED_SECRETS=$(git ls-files secrets/ 2>/dev/null | wc -l)
    if [ "$TRACKED_SECRETS" -eq 0 ]; then
        pass "No secrets/ tracked in git"
    else
        fail "secrets/ files tracked in git! Run: git rm --cached secrets/*"
    fi
    ENV_TRACKED=$(git ls-files .env 2>/dev/null | wc -l)
    if [ "$ENV_TRACKED" -eq 0 ]; then
        pass "No .env tracked in git"
    else
        fail ".env tracked in git!"
    fi
else
    warn "Not a git repository"
fi

# ── 8. Run Phase 70 Test ─────────────────────────────────────────
echo ""
echo "--- 8. Phase 70 Inspection Test ---"
if python3 scripts/test_phase70_full_app_inspection.py 2>&1; then
    pass "Phase 70 inspection test passed"
else
    fail "Phase 70 inspection test has failures"
fi

# ── Summary ──────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo -e " ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}"
echo "============================================================"
if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}❌ Some checks failed — review above before VPS deployment${NC}"
    exit 1
else
    echo -e "${GREEN}✅ All checks passed — ready for VPS deployment${NC}"
    exit 0
fi
