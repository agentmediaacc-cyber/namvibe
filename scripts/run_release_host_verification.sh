#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/venv/bin/python3}"
RESULTS_ROOT="${RESULTS_ROOT:-tmp/release-verification}"
RUN_ID="$(date +%Y%m%d_%H%M%S)_$$"
RUN_DIR="$RESULTS_ROOT/$RUN_ID"
CURRENT_STAGE="startup"
mkdir -p "$RUN_DIR"

log() {
  printf '[release-host] %s\n' "$*"
}

run_stage() {
  local stage="$1"
  shift
  CURRENT_STAGE="$stage"
  local stdout="$RUN_DIR/${stage}.stdout.log"
  local stderr="$RUN_DIR/${stage}.stderr.log"
  local status_file="$RUN_DIR/${stage}.status"
  local started
  started="$(date +%s)"
  log "stage=$stage start"
  set +e
  "$@" >"$stdout" 2>"$stderr"
  local status=$?
  set -e
  local finished
  finished="$(date +%s)"
  printf '%s\n' "$status" >"$status_file"
  cat >"$RUN_DIR/${stage}.json" <<JSON
{"stage":"$stage","exit_code":$status,"started_at":$started,"finished_at":$finished}
JSON
  if [[ "$status" -ne 0 ]]; then
    log "stage=$stage FAIL exit_code=$status"
    return "$status"
  fi
  log "stage=$stage PASS"
}

sanitize_summary() {
  local summary="$RUN_DIR/final_summary.txt"
  {
    echo "run_dir=$RUN_DIR"
    echo "repo_root=$REPO_ROOT"
    echo "python=$PYTHON_BIN"
    echo "sandbox_network_disabled=${CODEX_SANDBOX_NETWORK_DISABLED:-unset}"
  } >"$summary"
}

main() {
  log "repo_state"
  git status --short >"$RUN_DIR/git_status.txt"
  git rev-parse HEAD >"$RUN_DIR/head.txt"
  git branch --show-current >"$RUN_DIR/branch.txt"

  run_stage secret_scan "$PYTHON_BIN" scripts/test_tracked_secret_safety.py
  run_stage neon_dns "$PYTHON_BIN" scripts/diagnose_neon_connectivity.py
  run_stage neon_config "$PYTHON_BIN" scripts/check_neon_configuration.py
  run_stage neon_connection "$PYTHON_BIN" scripts/test_neon_connection.py
  run_stage call_integration "$PYTHON_BIN" scripts/test_call_security_integration.py
  run_stage dependency_check "$PYTHON_BIN" -m pip check
  run_stage compile_check "$PYTHON_BIN" -m compileall app.py api_v1 api_routes services scripts

  sanitize_summary
  log "summary=$RUN_DIR/final_summary.txt"
}

trap 'log "FAILED stage=$CURRENT_STAGE"' ERR
main "$@"
