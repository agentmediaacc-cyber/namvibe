#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# deploy_all.sh  —  Full Cloud Run deployment pipeline
# Usage:
#   chmod +x scripts/deploy_all.sh
#   PROJECT_ID=my-gcp-project ./scripts/deploy_all.sh
# ============================================================

PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-chain-app}"

if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: PROJECT_ID env var is required."
    echo "Usage: PROJECT_ID=my-gcp-project $0"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=============================================="
echo "  Deploy All  —  Project: $PROJECT_ID"
echo "  Region: $REGION  |  Service: $SERVICE"
echo "=============================================="
echo ""

# --------------------------------------------------
# Step 0: Preflight checks
# --------------------------------------------------
echo "--- Step 0: Preflight checks ---"

if ! command -v gcloud &>/dev/null; then
    echo "  FAILED: gcloud CLI not found. Install from https://cloud.google.com/sdk"
    exit 1
fi

if ! gcloud auth print-access-token &>/dev/null; then
    echo "  FAILED: Not authenticated. Run: gcloud auth login"
    exit 1
fi

echo "  gcloud OK, authenticated"
echo ""

# --------------------------------------------------
# Step 1: Ensure APP_BASE_URL secret exists (placeholder)
# --------------------------------------------------
echo "--- Step 1: Ensure chain-app-base-url secret exists ---"

EXISTING=$(gcloud secrets list --project "$PROJECT_ID" --format="value(name)" --filter="name:chain-app-base-url" 2>/dev/null || true)
if [ -z "$EXISTING" ]; then
    echo "  Creating chain-app-base-url with placeholder..."
    echo -n "PLACEHOLDER" | gcloud secrets create "chain-app-base-url" \
        --project "$PROJECT_ID" --data-file=- --quiet
    echo "  Created (placeholder). Will update after deploy."
else
    echo "  chain-app-base-url already exists."
fi

echo ""

# --------------------------------------------------
# Step 2: Upload secrets from .env
# --------------------------------------------------
echo "--- Step 2: Upload secrets from .env ---"

(cd "$ROOT_DIR" && python3 "$SCRIPT_DIR/setup_gcloud_secrets_from_env.py")
echo ""

# --------------------------------------------------
# Step 3: Build & deploy to Cloud Run
# --------------------------------------------------
echo "--- Step 3: Build & deploy ---"

python3 "$SCRIPT_DIR/deploy_cloudrun_test.py" 2>&1 | tee /tmp/deploy_output.txt

# Extract URL from deploy output
DEPLOYED_URL=$(grep "Deployed URL:" /tmp/deploy_output.txt | sed 's/.*Deployed URL: //' || true)
if [ -z "$DEPLOYED_URL" ]; then
    # Fallback: get from gcloud
    echo "  Fetching URL from Cloud Run..."
    DEPLOYED_URL=$(gcloud run services describe "$SERVICE" \
        --project "$PROJECT_ID" --region "$REGION" \
        --format="value(status.url)" --quiet 2>/dev/null || true)
fi
rm -f /tmp/deploy_output.txt

if [ -z "$DEPLOYED_URL" ]; then
    echo "  WARNING: Could not determine deployed URL. Continuing..."
fi
echo ""

# --------------------------------------------------
# Step 4: Update APP_BASE_URL with actual URL
# --------------------------------------------------
echo "--- Step 4: Update APP_BASE_URL ---"

if [ -n "$DEPLOYED_URL" ]; then
    echo -n "$DEPLOYED_URL" | gcloud secrets versions add "chain-app-base-url" \
        --project "$PROJECT_ID" --data-file=- --quiet
    echo "  Updated chain-app-base-url -> $DEPLOYED_URL"
    echo ""
fi

# --------------------------------------------------
# Step 5: Smoke test
# --------------------------------------------------
echo "--- Step 5: Smoke test ---"

if [ -n "$DEPLOYED_URL" ]; then
    python3 "$SCRIPT_DIR/test_cloudrun_smoke.py" --url "$DEPLOYED_URL"
else
    python3 "$SCRIPT_DIR/test_cloudrun_smoke.py"
fi

echo ""
echo "=============================================="
echo "  Pipeline complete!"
echo "  URL: ${DEPLOYED_URL:-unknown}"
echo "=============================================="
