#!/usr/bin/env bash
set -e

echo "=== PHASE 21: STOP FREEZING ==="

mkdir -p backups/phase21
cp .env backups/phase21/env.bak 2>/dev/null || true
cp api_routes/message_production_routes.py backups/phase21/message_production_routes.py.bak 2>/dev/null || true

# Disable startup prewarm locally
grep -q "^CHAIN_DISABLE_PREWARM=" .env && \
  sed -i.bak 's/^CHAIN_DISABLE_PREWARM=.*/CHAIN_DISABLE_PREWARM=1/' .env || \
  echo "CHAIN_DISABLE_PREWARM=1" >> .env

grep -q "^CHAIN_DISABLE_DB_PING=" .env && \
  sed -i.bak 's/^CHAIN_DISABLE_DB_PING=.*/CHAIN_DISABLE_DB_PING=1/' .env || \
  echo "CHAIN_DISABLE_DB_PING=1" >> .env

# Keep real Neon on, only stop slow startup checks
grep -q "^CHAIN_FAST_LOCAL=" .env && \
  sed -i.bak 's/^CHAIN_FAST_LOCAL=.*/CHAIN_FAST_LOCAL=0/' .env || \
  echo "CHAIN_FAST_LOCAL=0" >> .env

python3 - <<'PY'
from pathlib import Path

p = Path("api_routes/message_production_routes.py")
text = p.read_text()

# Remove slow table creation from before_app_request
text = text.replace(
'''@message_production_bp.before_app_request
def _ensure_once():
    if not getattr(_ensure_once, "done", False):
        ensure_message_tables()
        _ensure_once.done = True

''',
'''# Table creation is intentionally not run during every app startup/request.
# Run scripts/init_message_tables.py manually when deploying schema changes.

'''
)

p.write_text(text)
print("Removed slow message table init from request startup")
PY

mkdir -p scripts

cat > scripts/init_message_tables.py <<'PY'
from services.message_delivery_service import ensure_message_tables
ensure_message_tables()
print("Message tables/indexes checked.")
PY

python3 -m py_compile app.py api_routes/*.py services/*.py

echo ""
echo "✅ Freeze fix applied."
echo "Now start with:"
echo "export CHAIN_DISABLE_PREWARM=1"
echo "export CHAIN_DISABLE_DB_PING=1"
echo "export CHAIN_FAST_LOCAL=0"
echo "python3 app.py"
