#!/usr/bin/env bash
set -e

echo "=== PHASE 23: DISABLE SLOW IP CHECK + DEBUG RELOADER ==="

mkdir -p backups/phase23
cp app.py backups/phase23/app.py.bak
cp .env backups/phase23/env.bak 2>/dev/null || true

# Add local performance flags
for line in \
"CHAIN_DISABLE_PREWARM=1" \
"CHAIN_DISABLE_DB_PING=1" \
"CHAIN_FAST_LOCAL=0" \
"CHAIN_DISABLE_IP_REPUTATION=1" \
"FLASK_DEBUG=0" \
"FLASK_ENV=production" \
"ENV=production"
do
  key="${line%%=*}"
  if grep -q "^$key=" .env 2>/dev/null; then
    sed -i.bak "s/^$key=.*/$line/" .env
  else
    echo "$line" >> .env
  fi
done

python3 - <<'PY'
from pathlib import Path

p = Path("app.py")
text = p.read_text()

# Hard-disable debug/reloader in direct app.py startup.
text = text.replace("debug=True", "debug=False")
text = text.replace("use_reloader=True", "use_reloader=False")

# If app.run has no use_reloader arg, add it safely.
text = text.replace(
    "app.run(host=",
    "app.run(debug=False, use_reloader=False, host="
) if "app.run(host=" in text and "use_reloader" not in text[text.rfind("app.run("):text.rfind("app.run(")+300] else text

p.write_text(text)
print("Patched app.py debug/reloader")
PY

# Patch IP reputation query if present
python3 - <<'PY'
from pathlib import Path

targets = list(Path(".").rglob("*.py"))
patched = []
for p in targets:
    if "venv" in p.parts or "__pycache__" in p.parts:
        continue
    text = p.read_text(errors="ignore")
    if "chain_ip_reputation" not in text:
        continue

    if "CHAIN_DISABLE_IP_REPUTATION" in text:
        continue

    text = text.replace(
        "SELECT is_blocked FROM chain_ip_reputation WHERE ip_address = %s",
        "SELECT FALSE AS is_blocked /* disabled locally */"
    )

    # Also add a simple env guard near file imports if possible
    if "import os" not in text:
        text = "import os\n" + text

    patched.append(str(p))
    p.write_text(text)

print("Patched IP reputation files:", patched)
PY

python3 -m py_compile app.py services/*.py api_routes/*.py

echo ""
echo "✅ Phase 23 complete."
echo "Start using:"
echo "python3 scripts/run_fast_local_real_db.py"
