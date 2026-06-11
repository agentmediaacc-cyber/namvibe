#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "═══ Phase 73 — Homepage Real Data Check ═══"

echo ""
echo "1) Python test suite..."
python3 scripts/test_phase73_homepage_real_data.py

echo ""
echo "2) Template syntax check (Jinja2)..."
python3 -c "
import sys
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup
import re
env = Environment(loader=FileSystemLoader('templates'))
# Register custom app filters so template compiles standalone
def hashtag_links(text):
    return Markup(re.sub(r'#(\w+)', r'<a href=\"/search?q=%23\1\">#\1</a>', str(text)))
env.filters['hashtag_links'] = hashtag_links
def safe_link(*args):
    return args[0] if args else '/'
env.globals['safe_link'] = safe_link
def route_exists(*args):
    return False
env.globals['route_exists'] = route_exists
try:
    env.get_template('chain_home.html')
    print('  ✓ chain_home.html compiles')
except Exception as e:
    print(f'  ✗ {e}')
    sys.exit(1)
"

echo ""
echo "3) No hardcoded test patterns..."
! grep -q "'partner'" templates/chain_home.html || {
    echo "  ✗ Hardcoded 'partner' still present!"
    exit 1
}
echo "  ✓ No hardcoded 'partner'"

echo ""
echo "4) Gen-avatar CSS in base.html..."
grep -q 'gen-avatar' templates/base.html || {
    echo "  ✗ gen-avatar CSS missing from base.html"
    exit 1
}
echo "  ✓ gen-avatar CSS present"

echo ""
echo "5) Real data guard module exists..."
test -f services/homepage_real_data_guard.py || {
    echo "  ✗ services/homepage_real_data_guard.py missing"
    exit 1
}
echo "  ✓ Real data guard module present"

echo ""
echo "6) Compileall clean..."
python3 -c "
import py_compile, glob, sys
errors = []
for f in glob.glob('*.py') + glob.glob('services/*.py') + glob.glob('api_routes/*.py') + glob.glob('scripts/*.py') + glob.glob('tasks/*.py') + glob.glob('models/*.py') + glob.glob('jobs/*.py'):
    try:
        py_compile.compile(f, doraise=True)
    except py_compile.PyCompileError as e:
        errors.append(str(e))
if errors:
    for e in errors:
        print(f'  ✗ {e}')
    sys.exit(1)
print('  ✓ All Python files compile clean')
"

echo ""
echo "═══ Phase 73 check complete ═══"
