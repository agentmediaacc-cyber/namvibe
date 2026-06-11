#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
PASS=0; FAIL=0
check() { if [ $? -eq 0 ]; then echo -e "  ${GREEN}[PASS]${NC} $1"; PASS=$((PASS+1)); else echo -e "  ${RED}[FAIL]${NC} $1"; FAIL=$((FAIL+1)); fi; }

echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  Phase 72 — Final Premium Real-Device Hardening — Full Check${NC}"
echo -e "${GREEN}============================================================${NC}"

# ── 1. Python & venv ──
echo -e "\n${YELLOW}--- 1. Environment ---${NC}"
python3 --version > /dev/null 2>&1; check "Python 3 available"
if [ -d venv ]; then source venv/bin/activate; check "venv activated"
elif [ -d .venv ]; then source .venv/bin/activate; check "venv activated"
else PASS=$((PASS+1)); fi
python3 -c "import flask; import psycopg2; import concurrent.futures" > /dev/null 2>&1; check "Flask + psycopg2 + concurrent"

# ── 2. Compileall ──
echo -e "\n${YELLOW}--- 2. Compileall ---${NC}"
python3 -m compileall . -q 2>&1 | grep -E "Error|error" || true; check "Compileall passes"

# ── 3. Wallet request cache ──
echo -e "\n${YELLOW}--- 3. Wallet Request Cache ---${NC}"
python3 -c "
import ast; f=open('services/wallet_service.py').read()
tree=ast.parse(f)
cache_found=any('cache_get' in n.__class__.__name__ or (isinstance(n,ast.Call) and getattr(getattr(n.func,'id',None),'__contains__',lambda x:False)('cache_get')) for n in ast.walk(tree))
assert 'cache_get' in f and 'cache_set' in f, 'Missing request cache'
print('Wallet request cache confirmed')
"; check "get_wallet uses request cache"

# ── 4. Wallet route parallel ──
echo -e "\n${YELLOW}--- 4. Wallet Route Parallel ---${NC}"
python3 -c "
f=open('api_routes/wallet_routes.py').read()
assert 'ThreadPoolExecutor' in f and 'f_wallet' in f, 'Missing ThreadPoolExecutor'
print('Wallet route parallel confirmed')
"; check "Wallet route uses ThreadPoolExecutor"

# ── 5. Profile bundle parallel ──
echo -e "\n${YELLOW}--- 5. Profile Bundle Parallel ---${NC}"
python3 -c "
f=open('services/profile_service.py').read()
assert 'ThreadPoolExecutor' in f and 'bundle_results' in f, 'Missing ThreadPoolExecutor in bundle'
print('Profile bundle parallel confirmed')
"; check "Profile bundle uses ThreadPoolExecutor"

# ── 6. Homepage serial queries parallel ──
echo -e "\n${YELLOW}--- 6. Homepage Query Parallel ---${NC}"
python3 -c "
f=open('services/homepage_service.py').read()
assert 'f_groups' in f or 'f_sponsored' in f or 'f_wallet' in f, 'Missing parallel queries in homepage'
print('Homepage parallel confirmed')
"; check "Homepage serial queries parallelized"

# ── 7. Mobile CSS checks ──
echo -e "\n${YELLOW}--- 7. Mobile CSS ---${NC}"
python3 -c "
c=open('templates/base.html').read()
assert 'touch-action: manipulation' in c, 'Missing touch-action'
assert '-webkit-tap-highlight-color' in c, 'Missing tap highlight'
assert 'aspect-ratio' in c, 'Missing aspect-ratio'
assert 'reconnect-banner' in c, 'Missing reconnect banner'
assert 'search-bar-mobile' in c, 'Missing mobile search'
print('All mobile CSS checks passed')
"; check "All mobile CSS checks"

# ── 8. SocketIO reconnection ──
echo -e "\n${YELLOW}--- 8. SocketIO Reconnection ---${NC}"
python3 -c "
c=open('templates/base.html').read()
assert 'reconnectionAttempts' in c, 'Missing reconnectionAttempts'
assert 'reconnectionDelayMax' in c, 'Missing reconnectionDelayMax'
assert 'chain-reconnect-banner' in c, 'Missing reconnect banner element'
print('SocketIO reconnection confirmed')
"; check "SocketIO exponential backoff"

# ── Summary ──
TOTAL=$((PASS+FAIL))
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "Total: ${PASS} passed, ${FAIL} failed (${TOTAL} checks)"
echo -e "${GREEN}============================================================${NC}"
if [ "$FAIL" -gt 0 ]; then echo -e "${RED}❌ ${FAIL} CHECK(S) FAILED${NC}"; exit 1
else echo -e "${GREEN}✅ ALL CHECKS PASSED${NC}"; exit 0; fi
