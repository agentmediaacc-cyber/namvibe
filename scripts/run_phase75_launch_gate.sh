#!/usr/bin/env bash
# Phase 75 — VPS Launch Gate
# Runs every phase sequentially. On first failure, prints status and exits.
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

cd "$(dirname "$0")/.."

echo ""
echo -e "${YELLOW}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║       CHAIN VPS Launch Gate — Full Pre-Deployment Check    ║${NC}"
echo -e "${YELLOW}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

TOTAL=0
PASSED=0
FAILED=0

run_phase() {
    local name="$1"
    local cmd="$2"
    TOTAL=$((TOTAL + 1))
    echo -e "${YELLOW}[${TOTAL}] ${name}...${NC}"
    set +e
    eval "$cmd" 2>&1 | tail -5
    local rc=$?
    set -e
    if [ $rc -eq 0 ]; then
        echo -e "${GREEN}  ✅ ${name} PASSED${NC}"
        PASSED=$((PASSED + 1))
    else
        echo -e "${RED}  ❌ ${name} FAILED (exit code $rc)${NC}"
        FAILED=$((FAILED + 1))
    fi
    echo ""
}

# ── Required environment checks ──
if [ ! -f "app.py" ]; then
    echo -e "${RED}ERROR: Not in project root (app.py not found)${NC}"
    exit 1
fi

echo "Starting at: $(date)"
echo "Python: $(python3 --version)"
echo "Node:   $(node --version 2>/dev/null || echo 'not found')"
echo "Redis:  $(redis-cli ping 2>/dev/null || echo 'not reachable')"
echo ""

# ── Phase 0: Compileall ──
run_phase "compileall" "python3 -m compileall . -q 2>&1"

# ── Phase 69: Communication ──
run_phase "Phase 69 — Real-time Communication" "python3 scripts/test_phase69_real_communication.py 2>&1 | tail -5"

# ── Phase 73: Homepage Real Data ──
run_phase "Phase 73 — Homepage Real Data" "python3 scripts/test_phase73_homepage_real_data.py 2>&1 | tail -5"

# ── Phase 74: Full Speed Upgrade ──
run_phase "Phase 74 — Full Speed Upgrade" "python3 scripts/test_phase74_full_upgrade_speed.py 2>&1 | tail -5"

# ── Phase 75: Real User Journey ──
run_phase "Phase 75 — Real User Journey" "python3 scripts/test_phase75_real_user_journey.py 2>&1 | tail -15"

# ── Summary ──
echo -e "${YELLOW}══════════════════════════════════════════════════════════════${NC}"
echo ""
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}  ✅ ALL ${PASSED}/${TOTAL} PHASES PASSED — VPS LAUNCH READY${NC}"
    echo ""
    echo "  Next steps:"
    echo "    1. Apply indexes: python3 scripts/apply_phase74_full_speed_indexes.py"
    echo "    2. Set env: CHAIN_ENV=production, CHAIN_DEV_TOOLS=0"
    echo "    3. Set DATABASE_URL, REDIS_URL via env vars"
    echo "    4. Run with gunicorn or uWSGI behind nginx"
    echo "    5. Set up SSL cert via certbot/letsencrypt"
    echo "    6. Configure firewall (ufw)"
    echo "    7. Set up logrotate, fail2ban"
    echo ""
    exit 0
else
    echo -e "${RED}  ❌ ${FAILED}/${TOTAL} PHASES FAILED — NOT READY FOR VPS${NC}"
    echo ""
    echo "  Review errors above, fix issues, and re-run."
    echo ""
    exit 1
fi
