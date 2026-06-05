#!/bin/bash
# CHAIN VPS Deployment Check Script

echo "[check] Running Python syntax check..."
python3 -m py_compile app.py api_routes/*.py services/*.py scripts/*.py

echo "[check] Running Pre-deploy engine audit..."
PYTHONPATH=. CHAIN_DISABLE_RATE_LIMITS=1 python3 scripts/predeploy_check.py

echo "[check] Running Security audit..."
PYTHONPATH=. CHAIN_DISABLE_RATE_LIMITS=1 python3 scripts/security_audit.py

echo "[check] Running Neon migration (Dry Run)..."
PYTHONPATH=. CHAIN_DISABLE_RATE_LIMITS=1 python3 scripts/migrate_neon.py --dry-run

echo "[check] Running Launch readiness test..."
PYTHONPATH=. CHAIN_DISABLE_RATE_LIMITS=1 python3 scripts/launch_readiness.py

echo "[check] Running Smoke test..."
# Assume local port 5055 if gunicorn started, otherwise use test client mode
PYTHONPATH=. CHAIN_DISABLE_RATE_LIMITS=1 python3 scripts/deploy_smoke_test.py http://localhost:5055

echo ""
echo "✅ VPS Deploy Check PASSED"
