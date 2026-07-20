#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$HOME/Desktop/chain_app}"
exec "$SCRIPT_DIR/run_release_host_verification.sh" --repo "$REPO" --runtime-repo "$REPO" --venv "$REPO/venv" "$@"
