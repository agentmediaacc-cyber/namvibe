#!/usr/bin/env bash
set -uo pipefail

RUN_DIR="${1:-}"
REPO="${2:-}"
RUNTIME_REPO="${3:-}"
VENV="${4:-}"
WRAPPER="${5:-}"
if [[ -z "$RUN_DIR" || -z "$REPO" || -z "$RUNTIME_REPO" || -z "$VENV" || -z "$WRAPPER" ]]; then
  echo "ERROR: missing required arguments" >&2
  exit 2
fi

STATUS=99
FINISHED=0

write_status() {
  local status="${1:-99}"
  if [[ -n "$RUN_DIR" ]]; then
    mkdir -p "$RUN_DIR"
    {
      printf 'finish_time=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      printf 'job_pid=%s\n' "$$"
      printf 'status=%s\n' "$status"
    } >> "$RUN_DIR/run-metadata.txt"
    tmp_status="$RUN_DIR/host-status.txt.tmp"
    printf '%s\n' "$status" > "$tmp_status"
    mv "$tmp_status" "$RUN_DIR/host-status.txt"
  fi
}

finish() {
  local rc=$?
  if [[ "$FINISHED" -eq 0 ]]; then
    FINISHED=1
    write_status "$rc"
  fi
}

trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

[[ -d "$REPO" ]] || exit 71
[[ -d "$RUNTIME_REPO" ]] || exit 72
[[ -f "$VENV/bin/python3" ]] || exit 73
[[ -f "$WRAPPER" ]] || exit 74

export REPO RUNTIME_REPO VENV

START_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
JOB_PID="$$"
{
  printf 'start_time=%s\n' "$START_TS"
  printf 'job_pid=%s\n' "$JOB_PID"
  printf 'parent_pid=%s\n' "$PPID"
  printf 'uid=%s\n' "$(id -u)"
  printf 'user=%s\n' "$(id -un)"
  printf 'shell=%s\n' "${SHELL:-unknown}"
  printf 'cwd=%s\n' "$PWD"
  printf 'repo_exists=%s\n' "yes"
  printf 'repo=%s\n' "$REPO"
  printf 'runtime_repo=%s\n' "$RUNTIME_REPO"
  printf 'venv=%s\n' "$VENV"
  printf 'venv_exists=%s\n' "yes"
  printf 'wrapper_exists=%s\n' "yes"
  printf 'wrapper_path=%s\n' "$WRAPPER"
  printf 'python_path=%s\n' "$(command -v python3)"
  printf 'network_disabled=%s\n' "${CODEX_SANDBOX_NETWORK_DISABLED:+present}"
} > "$RUN_DIR/run-metadata.txt"

set +e
RUN_DIR="$RUN_DIR" bash "$WRAPPER" >> "$RUN_DIR/host-output.log" 2>> "$RUN_DIR/host-error.log"
STATUS=$?
set -e
FINISHED=1
write_status "$STATUS"
exit "$STATUS"
