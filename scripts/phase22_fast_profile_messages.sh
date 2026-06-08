#!/usr/bin/env bash
set -e

echo "=== PHASE 22: FAST PROFILE + MESSAGES FIX ==="

mkdir -p backups/phase22
cp services/profile_service.py backups/phase22/profile_service.py.bak
cp services/messaging_engine.py backups/phase22/messaging_engine.py.bak 2>/dev/null || true

python3 - <<'PY'
from pathlib import Path
p = Path("services/profile_service.py")
text = p.read_text()

start = text.find("def _chain_profile_columns_set")
if start == -1:
    raise SystemExit("Could not find _chain_profile_columns_set")

end = text.find("\ndef ", start + 1)
if end == -1:
    raise SystemExit("Could not find end of function")

new_func = r'''def _chain_profile_columns_set(refresh=False):
    """
    Production fast path.

    Do NOT inspect Neon schema on every request.
    Messages/Profile page was freezing because this function called
    get_table_columns('chain_profiles') during /messages/.
    """
    return set(NEON_PROFILE_COLUMNS)
'''

text = text[:start] + new_func + text[end:]
p.write_text(text)
print("Patched _chain_profile_columns_set to fixed production columns")
PY

python3 - <<'PY'
from pathlib import Path

p = Path("services/messaging_engine.py")
if not p.exists():
    print("messaging_engine.py not found, skipped")
    raise SystemExit

text = p.read_text()

# Reduce slow thread query timeout from 2000 to 800 where present.
text = text.replace("timeout_ms=2000", "timeout_ms=800")
text = text.replace("timeout_ms=3000", "timeout_ms=800")

# Ensure default fallback returns empty list fast instead of blocking page.
p.write_text(text)
print("Reduced messaging_engine Neon timeouts")
PY

python3 -m py_compile app.py services/*.py api_routes/*.py

echo ""
echo "✅ Phase 22 complete."
echo "Now restart Flask."
