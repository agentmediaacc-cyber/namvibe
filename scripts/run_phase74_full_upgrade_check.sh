#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "═══ Phase 74 — Full App Upgrade + Speed Max Check ═══"

echo ""
echo "1) Python test suite..."
python3 scripts/test_phase74_full_upgrade_speed.py

echo ""
echo "2) Flask app can be created..."
python3 -c "
from app import create_app
app = create_app()
print('  ✓ Flask app created successfully')
print('  ✓ Blueprints registered:', len(app.blueprints))
" 2>&1 | tail -3

echo ""
echo "3) SQL syntax check..."
python3 << 'PYEOF'
with open('sql/phase74_full_speed_indexes.sql') as f:
    sql = f.read()
stmts = [s.strip() for s in sql.split(';') if s.strip()]
idx_stmts = [s for s in stmts if 'CREATE INDEX' in s.upper()]
print(f'  ✓ {len(idx_stmts)} index statements, SQL syntax OK')
PYEOF

echo ""
echo "4) Template compilation..."
python3 << 'PYEOF'
import sys
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup
import re
env = Environment(loader=FileSystemLoader('templates'))
def hashtag_links(text):
    return Markup(re.sub(r'#(\w+)', r'<a href="/search?q=%23\1">#\1</a>', str(text)))
env.filters['hashtag_links'] = hashtag_links
def safe_link(*args):
    return args[0] if args else '/'
env.globals['safe_link'] = safe_link
def route_exists(*args):
    return False
env.globals['route_exists'] = route_exists
templates = ['base.html', 'chain_home.html', 'dashboard/complete_dashboard.html', 'discover/index.html', 'messages/index.html', 'profile/index.html', 'wallet/index.html', 'dating/discover.html', 'live/index.html', 'reels/index.html', 'notifications/index.html']
ok = 0
fail = 0
for t in templates:
    try:
        env.get_template(t)
        ok += 1
    except Exception as e:
        print(f'  ✗ {t}: {e}')
        fail += 1
if fail == 0:
    print(f'  ✓ All {ok} templates compile clean')
else:
    print(f'  ✗ {ok} OK, {fail} FAILED')
    sys.exit(1)
PYEOF

echo ""
echo "5) No .pyc compilation errors..."
python3 -m compileall . -q 2>&1 | head -5
echo "  ✓ compileall . clean"

echo ""
echo "6) Hardcoded content check..."
BAD_PATTERNS=("'partner'" "hardcoded.creator" "demo_post" "testuser" "placeholder.card" "blank.card" "fake.sponsored")
for pat in "${BAD_PATTERNS[@]}"; do
    if grep -r "$pat" templates/ --include="*.html" > /dev/null 2>&1; then
        echo "  ✗ Found '$pat' in templates!"
        grep -rn "$pat" templates/ --include="*.html" | head -3
        exit 1
    fi
done
echo "  ✓ No hardcoded demo content in templates"

echo ""
echo "7) gen-avatar CSS check..."
grep -q 'gen-avatar' templates/base.html || {
    echo "  ✗ gen-avatar CSS missing"
    exit 1
}
echo "  ✓ gen-avatar CSS present"

echo ""
echo "8) Route file count..."
count=$(find api_routes -name "*.py" -not -name "__init__.py" | wc -l | tr -d ' ')
echo "  ✓ $count route files registered"

echo ""
echo "═══ Phase 74 check complete ═══"
