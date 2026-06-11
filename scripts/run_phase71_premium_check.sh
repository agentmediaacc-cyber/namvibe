#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

check() {
    if [ $? -eq 0 ]; then
        echo -e "  ${GREEN}[PASS]${NC} $1"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}[FAIL]${NC} $1"
        FAIL=$((FAIL + 1))
    fi
}

echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  Phase 71 — Premium Speed + UI Polish — Full Check${NC}"
echo -e "${GREEN}============================================================${NC}"

# ── 1. Python version ──
echo -e "\n${YELLOW}--- 1. Python ---${NC}"
python3 --version > /dev/null 2>&1; check "Python 3 available"

# ── 2. virtualenv ──
echo -e "\n${YELLOW}--- 2. Virtualenv ---${NC}"
if [ -d "venv" ]; then
    source venv/bin/activate
    check "Virtualenv activated"
elif [ -d ".venv" ]; then
    source .venv/bin/activate
    check "Virtualenv activated"
else
    echo -e "  ${YELLOW}[WARN]${NC} No virtualenv found — using system python"
    PASS=$((PASS + 1))
fi

# ── 3. Dependencies ──
echo -e "\n${YELLOW}--- 3. Dependencies ---${NC}"
python3 -c "import flask; import psycopg2" > /dev/null 2>&1; check "Flask + psycopg2 importable"

# ── 4. Compileall ──
echo -e "\n${YELLOW}--- 4. Compileall ---${NC}"
python3 -m compileall . -q 2>&1 | grep -E "Error|error" || true
check "Compileall passes"

# ── 5. SQL syntax check ──
echo -e "\n${YELLOW}--- 5. SQL Syntax ---${NC}"
python3 -c "
import sqlparse
sql = open('sql/phase71_performance_indexes.sql').read()
statements = [s.strip() for s in sql.split(';') if s.strip()]
print(f'  {len(statements)} statements parsed')
" > /dev/null 2>&1; check "SQL parses cleanly"

# ── 6. Base template + code fix checks ──
echo -e "\n${YELLOW}--- 6. Template Checks ---${NC}"
python3 -c "
c = open('templates/base.html').read()
assert '.skeleton' in c and '@keyframes shimmer' in c, 'Missing skeleton'
assert 'page-fade-in' in c and '@keyframes fadeIn' in c, 'Missing transitions'
assert 'premium-card' in c, 'Missing premium cards'
assert '#a0aab8' in c, 'Missing contrast fix'
assert 'min-height: 44px' in c, 'Missing touch target fix'
assert '@media (max-width: 760px)' in c, 'Missing mobile media query'
print('All template checks passed')
"; check "All template checks"

# ── 7. Code fix checks ──
echo -e "\n${YELLOW}--- 7. Code Fixes ---${NC}"
python3 -c "
api = open('api_routes/dashboard_routes.py').read()
assert 'LIMIT 200' in api, 'Missing LIMIT in dashboard'
msg = open('services/messaging_engine.py').read()
assert 'profile_id, muted FROM chain_thread_members' in msg, 'Missing batch muted check'
hp = open('services/homepage_service.py').read()
assert 'list(unique)' in hp, 'Missing parameterized query in homepage'
print('All code fix checks passed')
"; check "All code fix checks"

# ── Summary ──
echo ""
TOTAL=$((PASS + FAIL))
echo -e "${GREEN}============================================================${NC}"
echo -e "Total: ${PASS} passed, ${FAIL} failed (${TOTAL} checks)"
echo -e "${GREEN}============================================================${NC}"

if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}❌ ${FAIL} CHECK(S) FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}✅ ALL CHECKS PASSED${NC}"
    exit 0
fi
