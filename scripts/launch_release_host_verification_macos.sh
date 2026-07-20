#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_REPO="$(git -C "$SCRIPT_DIR/.." rev-parse --show-toplevel)"
SOURCE_RUNTIME_REPO=""
SOURCE_VENV=""
SOURCE_ENV_REPO=""
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
LABEL="com.namvibe.release-verification.$RUN_ID"
DOMAIN="gui/$(id -u)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      SOURCE_REPO="${2:?missing repo}"; shift 2 ;;
    --runtime-repo)
      SOURCE_RUNTIME_REPO="${2:?missing runtime repo}"; shift 2 ;;
    --venv)
      SOURCE_VENV="${2:?missing venv}"; shift 2 ;;
    --env-repo)
      SOURCE_ENV_REPO="${2:?missing env repo}"; shift 2 ;;
    --wait)
      WAIT=1; shift ;;
    *)
      echo "usage: $0 [--repo PATH] [--runtime-repo PATH] [--venv PATH] [--env-repo PATH] [--wait]" >&2
      exit 2 ;;
  esac
done
SOURCE_RUNTIME_REPO="${SOURCE_RUNTIME_REPO:-$SOURCE_REPO}"
if [[ -z "$SOURCE_VENV" ]]; then
  if [[ -x "$SOURCE_REPO/venv/bin/python3" ]]; then
    SOURCE_VENV="$SOURCE_REPO/venv"
  else
    SOURCE_VENV="$HOME/Desktop/chain_app/venv"
  fi
fi
SOURCE_ENV_REPO="${SOURCE_ENV_REPO:-$SOURCE_REPO}"
if [[ ! -f "$SOURCE_ENV_REPO/.env" && -f "$HOME/Desktop/chain_app/.env" ]]; then
  SOURCE_ENV_REPO="$HOME/Desktop/chain_app"
fi
WAIT="${WAIT:-0}"
WAIT_TIMEOUT_SECONDS="${WAIT_TIMEOUT_SECONDS:-3600}"
DIRECT_FALLBACK="${DIRECT_FALLBACK:-0}"
VERIFY_ROOT="/private/tmp/namvibe-release-verification"
RUN_DIR="$VERIFY_ROOT/$RUN_ID"
REPO="$RUN_DIR/repo"
RUNTIME_REPO="$REPO"
VENV="$RUN_DIR/venv"
PLIST_FILE="$RUN_DIR/com.namvibe.release-verification.$RUN_ID.plist"
JOB_SCRIPT="$SOURCE_REPO/scripts/run_release_host_verification_macos_job.sh"
WRAPPER_SCRIPT="$SOURCE_REPO/scripts/run_release_host_verification.sh"
LAUNCH_WRAPPER="/private/tmp/namvibe-release-launch-$RUN_ID.sh"
JOB_WRAPPER="/private/tmp/namvibe-release-job-$RUN_ID.sh"
WRAPPER_COPY="/private/tmp/namvibe-release-wrapper-$RUN_ID.sh"

mkdir -p "$VERIFY_ROOT"
rm -rf "$REPO"
git clone --no-hardlinks --branch "$(git -C "$SOURCE_REPO" branch --show-current)" "$SOURCE_REPO" "$REPO"
git -C "$REPO" remote remove origin 2>/dev/null || true
if [[ -f "$SOURCE_ENV_REPO/.env" ]]; then
  install -m 600 "$SOURCE_ENV_REPO/.env" "$REPO/.env"
fi
mkdir -p "$RUN_DIR"
rm -rf "$VENV"
ditto "$SOURCE_VENV" "$VENV"

cat >"$LAUNCH_WRAPPER" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
cd "$REPO"
exec /bin/bash "$JOB_WRAPPER" "$RUN_DIR" "$REPO" "$RUNTIME_REPO" "$VENV" "$WRAPPER_COPY"
EOF
chmod +x "$LAUNCH_WRAPPER"

cp "$JOB_SCRIPT" "$JOB_WRAPPER"
chmod +x "$JOB_WRAPPER"
cp "$WRAPPER_SCRIPT" "$WRAPPER_COPY"
chmod +x "$WRAPPER_COPY"

cat >"$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$LAUNCH_WRAPPER</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/private/tmp</string>
  <key>StandardOutPath</key>
  <string>$RUN_DIR/launchd-stdout.log</string>
  <key>StandardErrorPath</key>
  <string>$RUN_DIR/launchd-stderr.log</string>
  <key>RunAtLoad</key>
  <true/>
  <key>ProcessType</key>
  <string>Interactive</string>
</dict>
</plist>
EOF

plutil -lint "$PLIST_FILE"

cat >"$RUN_DIR/launcher-status.txt" <<EOF
run_id=$RUN_ID
launcher_method=launchd
launchd_label=$LABEL
run_dir=$RUN_DIR
plist_file=$PLIST_FILE
launch_wrapper=$LAUNCH_WRAPPER
job_script=$JOB_SCRIPT
wrapper_script=$WRAPPER_SCRIPT
wrapper_copy=$WRAPPER_COPY
domain=$DOMAIN
source_repo=$SOURCE_REPO
source_runtime_repo=$SOURCE_RUNTIME_REPO
source_venv=$SOURCE_VENV
source_env_repo=$SOURCE_ENV_REPO
repo=$REPO
runtime_repo=$RUNTIME_REPO
venv=$VENV
EOF

if [[ "$DIRECT_FALLBACK" -eq 1 ]]; then
  {
    printf 'bootstrap_status=%s\n' "SKIPPED_DUE_TO_DIRECT_FALLBACK"
    printf 'kickstart_status=%s\n' "SKIPPED_DUE_TO_DIRECT_FALLBACK"
    printf 'launchctl_print_status=%s\n' "SKIPPED_DUE_TO_DIRECT_FALLBACK"
    printf 'launcher_mode=%s\n' "direct_fallback"
  } >>"$RUN_DIR/launcher-status.txt"
  set +e
  env -u CODEX_SANDBOX_NETWORK_DISABLED RUN_DIR="$RUN_DIR" bash "$JOB_WRAPPER" "$RUN_DIR" "$REPO" "$RUNTIME_REPO" "$VENV" "$WRAPPER_COPY" >>"$RUN_DIR/host-output.log" 2>>"$RUN_DIR/host-error.log"
  direct_status=$?
  set -e
  printf 'direct_status=%s\n' "$direct_status" >>"$RUN_DIR/launcher-status.txt"
  if [[ "$WAIT" -eq 1 ]]; then
    STATUS_FILE="$RUN_DIR/host-status.txt"
    max_tries=$((WAIT_TIMEOUT_SECONDS / 2))
    if (( max_tries < 1 )); then
      max_tries=1
    fi
    for _ in $(seq 1 "$max_tries"); do
      if [[ -f "$STATUS_FILE" ]]; then
        break
      fi
      sleep 2
    done
    if [[ ! -f "$STATUS_FILE" ]]; then
      {
        echo "launcher_wait=timeout"
        echo "launchd_print_exists=$( [[ -f "$RUN_DIR/launchctl-print.txt" ]] && echo yes || echo no )"
        echo "launchd_stdout_exists=$( [[ -f "$RUN_DIR/launchd-stdout.log" ]] && echo yes || echo no )"
        echo "launchd_stderr_exists=$( [[ -f "$RUN_DIR/launchd-stderr.log" ]] && echo yes || echo no )"
      } >>"$RUN_DIR/launcher-status.txt"
      exit 1
    fi
    cat "$STATUS_FILE"
  else
    printf 'result_file=%s\n' "$RUN_DIR/host-output.log"
    printf 'status_file=%s\n' "$RUN_DIR/host-status.txt"
  fi
  exit "$direct_status"
fi

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
set +e
launchctl bootstrap "$DOMAIN" "$PLIST_FILE"
bootstrap_status=$?
set -e

if [[ "$bootstrap_status" -ne 0 ]]; then
  {
    printf 'bootstrap_status=%s\n' "$bootstrap_status"
    printf 'kickstart_status=%s\n' "SKIPPED_DUE_TO_BOOTSTRAP_FAILURE"
    printf 'launchctl_print_status=%s\n' "SKIPPED_DUE_TO_BOOTSTRAP_FAILURE"
    printf 'launcher_mode=%s\n' "direct_fallback"
  } >>"$RUN_DIR/launcher-status.txt"
  set +e
  env -u CODEX_SANDBOX_NETWORK_DISABLED RUN_DIR="$RUN_DIR" bash "$JOB_WRAPPER" "$RUN_DIR" "$REPO" "$RUNTIME_REPO" "$VENV" "$WRAPPER_COPY" >>"$RUN_DIR/host-output.log" 2>>"$RUN_DIR/host-error.log"
  direct_status=$?
  set -e
  printf 'direct_status=%s\n' "$direct_status" >>"$RUN_DIR/launcher-status.txt"
  if [[ "$WAIT" -eq 1 ]]; then
    STATUS_FILE="$RUN_DIR/host-status.txt"
    max_tries=$((WAIT_TIMEOUT_SECONDS / 2))
    if (( max_tries < 1 )); then
      max_tries=1
    fi
    for _ in $(seq 1 "$max_tries"); do
      if [[ -f "$STATUS_FILE" ]]; then
        break
      fi
      sleep 2
    done
    if [[ ! -f "$STATUS_FILE" ]]; then
      {
        echo "launcher_wait=timeout"
        echo "launchd_print_exists=$( [[ -f \"$RUN_DIR/launchctl-print.txt\" ]] && echo yes || echo no )"
        echo "launchd_stdout_exists=$( [[ -f \"$RUN_DIR/launchd-stdout.log\" ]] && echo yes || echo no )"
        echo "launchd_stderr_exists=$( [[ -f \"$RUN_DIR/launchd-stderr.log\" ]] && echo yes || echo no )"
      } >>"$RUN_DIR/launcher-status.txt"
      exit 1
    fi
    cat "$STATUS_FILE"
  else
    printf 'result_file=%s\n' "$RUN_DIR/host-output.log"
    printf 'status_file=%s\n' "$RUN_DIR/host-status.txt"
  fi
  exit "$direct_status"
fi

set +e
launchctl kickstart -k "$DOMAIN/$LABEL"
kickstart_status=$?
launchctl_print_status=0
launchctl print "$DOMAIN/$LABEL" >"$RUN_DIR/launchctl-print.txt" 2>&1
launchctl_print_status=$?
set -e

{
  printf 'bootstrap_status=%s\n' "$bootstrap_status"
  printf 'kickstart_status=%s\n' "$kickstart_status"
  printf 'launchctl_print_status=%s\n' "$launchctl_print_status"
} >>"$RUN_DIR/launcher-status.txt"

if [[ "$kickstart_status" -ne 0 || "$launchctl_print_status" -ne 0 ]]; then
  {
    printf 'launcher_mode=%s\n' "kickstart_fallback"
  } >>"$RUN_DIR/launcher-status.txt"
  set +e
  RUN_DIR="$RUN_DIR" bash "$JOB_WRAPPER" "$RUN_DIR" "$REPO" "$RUNTIME_REPO" "$VENV" "$WRAPPER_COPY" >>"$RUN_DIR/host-output.log" 2>>"$RUN_DIR/host-error.log"
  direct_status=$?
  set -e
  printf 'direct_status=%s\n' "$direct_status" >>"$RUN_DIR/launcher-status.txt"
  if [[ "$WAIT" -eq 1 ]]; then
    STATUS_FILE="$RUN_DIR/host-status.txt"
    max_tries=$((WAIT_TIMEOUT_SECONDS / 2))
    if (( max_tries < 1 )); then
      max_tries=1
    fi
    for _ in $(seq 1 "$max_tries"); do
      if [[ -f "$STATUS_FILE" ]]; then
        break
      fi
      sleep 2
    done
    if [[ ! -f "$STATUS_FILE" ]]; then
      {
        echo "launcher_wait=timeout"
        echo "launchd_print_exists=$( [[ -f \"$RUN_DIR/launchctl-print.txt\" ]] && echo yes || echo no )"
        echo "launchd_stdout_exists=$( [[ -f \"$RUN_DIR/launchd-stdout.log\" ]] && echo yes || echo no )"
        echo "launchd_stderr_exists=$( [[ -f \"$RUN_DIR/launchd-stderr.log\" ]] && echo yes || echo no )"
      } >>"$RUN_DIR/launcher-status.txt"
      exit 1
    fi
    cat "$STATUS_FILE"
  else
    printf 'result_file=%s\n' "$RUN_DIR/host-output.log"
    printf 'status_file=%s\n' "$RUN_DIR/host-status.txt"
  fi
  exit "$direct_status"
fi

if [[ "$WAIT" -eq 1 ]]; then
  STATUS_FILE="$RUN_DIR/host-status.txt"
  max_tries=$((WAIT_TIMEOUT_SECONDS / 2))
  if (( max_tries < 1 )); then
    max_tries=1
  fi
  for _ in $(seq 1 "$max_tries"); do
    if [[ -f "$STATUS_FILE" ]]; then
      break
    fi
    sleep 2
  done
  if [[ ! -f "$STATUS_FILE" ]]; then
    {
      echo "launcher_wait=timeout"
      echo "launchd_print_exists=$( [[ -f "$RUN_DIR/launchctl-print.txt" ]] && echo yes || echo no )"
      echo "launchd_stdout_exists=$( [[ -f "$RUN_DIR/launchd-stdout.log" ]] && echo yes || echo no )"
      echo "launchd_stderr_exists=$( [[ -f "$RUN_DIR/launchd-stderr.log" ]] && echo yes || echo no )"
    } >>"$RUN_DIR/launcher-status.txt"
    exit 1
  fi
  launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
  cat "$STATUS_FILE"
else
  printf 'result_file=%s\n' "$RUN_DIR/host-output.log"
  printf 'status_file=%s\n' "$RUN_DIR/host-status.txt"
fi
