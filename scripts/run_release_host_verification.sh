#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:?REPO is required}"
RUNTIME_REPO="${RUNTIME_REPO:-$REPO}"
VENV="${VENV:-$REPO/venv}"

PYTHON_BIN="${PYTHON_BIN:-$VENV/bin/python3}"
RESULTS_ROOT="${RESULTS_ROOT:-$REPO/tmp/release-verification}"
if [[ -n "${RUN_DIR:-}" ]]; then
  RUN_DIR="${RUN_DIR%/}"
  RUN_ID="${RUN_ID:-$(basename "$RUN_DIR")}"
else
  RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)_$$}"
  RUN_DIR="$RESULTS_ROOT/$RUN_ID"
fi
mkdir -p "$RUN_DIR/pycache"
export PYTHONPYCACHEPREFIX="$RUN_DIR/pycache"

log() {
  printf '[release-host] %s\n' "$*"
}

sanitize() {
  "$PYTHON_BIN" - "$@" <<'PY'
import hashlib, os, sys
from urllib.parse import urlparse

mode = sys.argv[1]
if mode == "host":
    raw = sys.argv[2] if len(sys.argv) > 2 else ""
    parsed = urlparse(raw)
    host = parsed.hostname or raw
    if not host:
        print("")
    else:
        print(hashlib.sha256(host.encode()).hexdigest()[:12])
elif mode == "path":
    raw = sys.argv[2] if len(sys.argv) > 2 else ""
    print(hashlib.sha256(raw.encode()).hexdigest()[:12])
else:
    print("")
PY
}

run_stage() {
  local stage="$1"
  shift
  local stdout="$RUN_DIR/${stage}.stdout.log"
  local stderr="$RUN_DIR/${stage}.stderr.log"
  local status_file="$RUN_DIR/${stage}.status"
  local result_file="$RUN_DIR/${stage}.json"
  local timeout_s="${STAGE_TIMEOUT_SECONDS:-300}"
  local started finished status result
  started="$(date +%s)"
  log "stage=$stage start"
  case "$stage" in
    database_path_selection|neon_dns|neon_tcp|neon_connection|call_security_integration|cloudflare_process|cloudflare_connection|public_dns|public_tls|public_routes|socketio_handshake|browser_desktop|browser_tablet|browser_mobile|browser_small_mobile|runtime_log_scan|log_secret_scan)
      if [[ -n "${CODEX_SANDBOX_NETWORK_DISABLED:-}" ]]; then
        finished="$(date +%s)"
        result="BLOCKED_EXTERNAL"
        : >"$stdout"
        printf 'blocked_in_codex_sandbox=1\n' >"$stderr"
        printf '%s\n' "$result" >"$status_file"
        cat >"$result_file" <<JSON
{"stage":"$stage","result":"$result","exit_code":92,"started_at":$started,"finished_at":$finished}
JSON
        log "stage=$stage result=$result exit_code=92"
        return 0
      fi
      ;;
  esac
  set +e
  "$PYTHON_BIN" - "$stdout" "$stderr" "$timeout_s" "$@" <<'PY'
import os
import subprocess
import sys

stdout_path, stderr_path, timeout_s, *cmd = sys.argv[1:]
timeout_s = int(timeout_s)
if not cmd:
    raise SystemExit(2)
with open(stdout_path, 'wb') as out, open(stderr_path, 'wb') as err:
    try:
        cp = subprocess.run(cmd, stdout=out, stderr=err, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        print(f'timeout_after_seconds={timeout_s}', file=err)
        raise SystemExit(124)
raise SystemExit(cp.returncode)
PY
  status=$?
  set -e
  finished="$(date +%s)"
  case "$status" in
    0) result="PASS" ;;
    124) result="BLOCKED_EXTERNAL" ;;
    2|90|91|92|93) result="BLOCKED_EXTERNAL" ;;
    *) result="FAIL" ;;
  esac
  printf '%s\n' "$result" >"$status_file"
  cat >"$result_file" <<JSON
{"stage":"$stage","result":"$result","exit_code":$status,"started_at":$started,"finished_at":$finished}
JSON
  log "stage=$stage result=$result exit_code=$status"
  return 0
}

stage_ok() {
  [[ -f "$RUN_DIR/$1.status" ]] && [[ "$(cat "$RUN_DIR/$1.status")" == "PASS" ]]
}

main() {
  log "repo_state"
  log "run_dir=$RUN_DIR"
  export RUN_DIR RUNTIME_REPO REPO
  git -C "$REPO" status --short >"$RUN_DIR/git_status.txt"
  git -C "$REPO" rev-parse HEAD >"$RUN_DIR/head.txt"
  git -C "$REPO" branch --show-current >"$RUN_DIR/branch.txt"
  printf '%s\n' "$RUNTIME_REPO" >"$RUN_DIR/runtime_repo.txt"

  run_stage tracked_secret_scan "$PYTHON_BIN" "$REPO/scripts/test_tracked_secret_safety.py"
  run_stage dependency_check "$PYTHON_BIN" -m pip check
  run_stage compile_check "$PYTHON_BIN" -m compileall "$REPO/app.py" "$REPO/api_v1" "$REPO/api_routes" "$REPO/services" "$REPO/scripts"
  run_stage database_path_selection "$PYTHON_BIN" "$REPO/scripts/compare_neon_connection_paths.py"
  run_stage neon_dns "$PYTHON_BIN" "$REPO/scripts/check_neon_configuration.py"
  run_stage neon_tcp "$PYTHON_BIN" "$REPO/scripts/test_neon_connection.py"
  run_stage neon_connection "$PYTHON_BIN" "$REPO/scripts/test_neon_connection.py"
  run_stage call_security_integration "$PYTHON_BIN" "$REPO/scripts/test_call_security_integration.py"

  run_stage gunicorn_restart "$PYTHON_BIN" - <<'PY'
import os, subprocess, time, pathlib
root = pathlib.Path(os.environ["RUNTIME_REPO"])
logs = root / "logs"
logs.mkdir(exist_ok=True)
subprocess.run(["pkill", "-f", "gunicorn app:app"], check=False)
time.sleep(2)
subprocess.run([
    "gunicorn", "app:app",
    "--bind", "127.0.0.1:8080",
    "--workers", "2",
    "--threads", "4",
    "--worker-class", "gevent",
    "--timeout", "120",
    "--access-logfile", str(logs / "gunicorn_access.log"),
    "--error-logfile", str(logs / "gunicorn_error.log"),
    "--daemon",
], cwd=str(root), check=True)
time.sleep(5)
print("gunicorn_restarted")
PY

  run_stage gunicorn_listener "$PYTHON_BIN" - <<'PY'
import subprocess, sys
out = subprocess.check_output(["lsof", "-nP", "-iTCP:8080", "-sTCP:LISTEN"], text=True)
print(out)
sys.exit(0 if "8080" in out else 1)
PY

  run_stage gunicorn_sequential_health "$PYTHON_BIN" - <<'PY'
import subprocess, sys
url = "http://127.0.0.1:8080/healthz"
ok = 0
for i in range(10):
    cp = subprocess.run(["curl", "--ipv4", "--connect-timeout", "3", "--max-time", "10", "-sS", "-o", "/dev/null", "-w", "%{http_code}", url], capture_output=True, text=True)
    if cp.returncode == 0 and cp.stdout.strip() == "200":
        ok += 1
print(f"health_ok={ok}/10")
sys.exit(0 if ok == 10 else 1)
PY

  run_stage gunicorn_sequential_homepage "$PYTHON_BIN" - <<'PY'
import subprocess, sys
url = "http://127.0.0.1:8080/"
ok = 0
for i in range(10):
    cp = subprocess.run(["curl", "--ipv4", "--connect-timeout", "3", "--max-time", "10", "-sS", "-o", "/dev/null", "-w", "%{http_code}", url], capture_output=True, text=True)
    if cp.returncode == 0 and cp.stdout.strip() in {"200", "302", "303"}:
        ok += 1
print(f"homepage_ok={ok}/10")
sys.exit(0 if ok == 10 else 1)
PY

  run_stage gunicorn_concurrent_health "$PYTHON_BIN" - <<'PY'
from concurrent.futures import ThreadPoolExecutor
import subprocess, sys
url = "http://127.0.0.1:8080/healthz"
def probe():
    cp = subprocess.run(["curl", "--ipv4", "--connect-timeout", "3", "--max-time", "10", "-sS", "-o", "/dev/null", "-w", "%{http_code}", url], capture_output=True, text=True)
    return cp.returncode == 0 and cp.stdout.strip() == "200"
with ThreadPoolExecutor(max_workers=10) as pool:
    results = list(pool.map(lambda _: probe(), range(10)))
print(f"concurrent_health_ok={sum(results)}/10")
sys.exit(0 if all(results) else 1)
PY

  run_stage local_routes "$PYTHON_BIN" - <<'PY'
import subprocess, sys
urls = [
    "http://127.0.0.1:8080/healthz",
    "http://127.0.0.1:8080/",
    "http://127.0.0.1:8080/reels/",
    "http://127.0.0.1:8080/profile/@namvibe",
    "http://127.0.0.1:8080/profile/@definitely-missing-profile",
    "http://127.0.0.1:8080/discover",
    "http://127.0.0.1:8080/notifications",
    "http://127.0.0.1:8080/messages",
    "http://127.0.0.1:8080/calls",
    "http://127.0.0.1:8080/socket.io/?EIO=4&transport=polling",
]
ok = 0
for url in urls:
    cp = subprocess.run(["curl", "--ipv4", "--connect-timeout", "3", "--max-time", "15", "-sS", "-o", "/dev/null", "-w", "%{http_code}", url], capture_output=True, text=True)
    if cp.returncode == 0 and cp.stdout.strip():
        ok += 1
print(f"local_routes_ok={ok}/{len(urls)}")
sys.exit(0 if ok == len(urls) else 1)
PY

  run_stage cloudflare_process "$PYTHON_BIN" - <<'PY'
import subprocess, sys
out = subprocess.check_output(["pgrep", "-af", "cloudflared"], text=True)
print(out)
sys.exit(0 if out.strip() else 1)
PY

  run_stage cloudflare_connection "$PYTHON_BIN" - <<'PY'
import os, pathlib, subprocess, sys
root = pathlib.Path(os.environ["RUNTIME_REPO"])
log = root / "logs" / "cloudflared.log"
text = log.read_text() if log.exists() else ""
print(text[-1000:])
sys.exit(0 if ("Registered tunnel connection" in text or "Connection established" in text or "metrics server" in text) else 1)
PY

  run_stage public_dns "$PYTHON_BIN" - <<'PY'
import socket, sys
host = "namvibe.com"
try:
    infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    print(f"addresses={len({info[4][0] for info in infos})}")
    sys.exit(0)
except Exception as exc:
    print(type(exc).__name__, str(exc)[:180])
    sys.exit(1)
PY

  run_stage public_tls "$PYTHON_BIN" - <<'PY'
import subprocess, sys
cp = subprocess.run(["curl", "--ipv4", "--connect-timeout", "5", "--max-time", "20", "-I", "https://namvibe.com/healthz"], capture_output=True, text=True)
print(cp.stdout[:500])
sys.exit(0 if cp.returncode == 0 and "HTTP/" in cp.stdout else 1)
PY

  run_stage public_routes "$PYTHON_BIN" - <<'PY'
import subprocess, sys
urls = [
    "https://namvibe.com/healthz",
    "https://namvibe.com/",
    "https://namvibe.com/reels/",
    "https://namvibe.com/profile/@namvibe",
    "https://namvibe.com/profile/@definitely-missing-profile",
    "https://namvibe.com/discover",
    "https://namvibe.com/notifications",
    "https://namvibe.com/messages",
    "https://namvibe.com/calls",
    "https://namvibe.com/socket.io/?EIO=4&transport=polling",
]
ok = 0
for url in urls:
    cp = subprocess.run(["curl", "--ipv4", "--connect-timeout", "5", "--max-time", "20", "-sS", "-o", "/dev/null", "-w", "%{http_code}", url], capture_output=True, text=True)
    if cp.returncode == 0 and cp.stdout.strip():
        ok += 1
print(f"public_routes_ok={ok}/{len(urls)}")
sys.exit(0 if ok == len(urls) else 1)
PY

  run_stage socketio_handshake "$PYTHON_BIN" - <<'PY'
import subprocess, sys
cp = subprocess.run(["curl", "--ipv4", "--connect-timeout", "5", "--max-time", "20", "-sS", "https://namvibe.com/socket.io/?EIO=4&transport=polling"], capture_output=True, text=True)
print(cp.stdout[:200])
sys.exit(0 if cp.returncode == 0 and cp.stdout.startswith("0") else 1)
PY

  run_stage browser_desktop "$PYTHON_BIN" "$REPO/scripts/test_release_browser_smoke.py" --viewport desktop
  run_stage browser_tablet "$PYTHON_BIN" "$REPO/scripts/test_release_browser_smoke.py" --viewport tablet
  run_stage browser_mobile "$PYTHON_BIN" "$REPO/scripts/test_release_browser_smoke.py" --viewport mobile
  run_stage browser_small_mobile "$PYTHON_BIN" "$REPO/scripts/test_release_browser_smoke.py" --viewport small_mobile

  run_stage runtime_log_scan "$PYTHON_BIN" - <<'PY'
import os, pathlib, re, sys
patterns = [re.compile(p, re.I) for p in [r"Traceback", r"CRITICAL", r"Worker timeout", r"authentication failed", r"password", r"postgresql://", r"redis://", r"rediss://", r"Bearer", r"service_role", r"private key", r"secret", r"token"]]
root = pathlib.Path(os.environ["RUNTIME_REPO"])
logs = [root / "logs" / "gunicorn_error.log", root / "logs" / "gunicorn_access.log", root / "logs" / "cloudflared.log"]
found = False
for path in logs:
    if not path.exists():
        continue
    recent = path.read_text(errors="ignore").splitlines()[-30:]
    for line in recent:
        if any(p.search(line) for p in patterns):
            found = True
            print(f"{path.name}: {line[:180]}")
            break
sys.exit(1 if found else 0)
PY

  run_stage log_secret_scan "$PYTHON_BIN" "$REPO/scripts/test_startup_logs_no_secrets.py"

  run_stage homepage_report "$PYTHON_BIN" - <<'PY'
import json
import os
import pathlib
import re
import subprocess
from statistics import median

root = pathlib.Path(os.environ["RUN_DIR"])
runtime_root = pathlib.Path(os.environ["RUNTIME_REPO"])

def curl_sample(url: str, count: int = 5):
    samples = []
    for _ in range(count):
        cp = subprocess.run(
            ["curl", "--ipv4", "--connect-timeout", "5", "--max-time", "20", "-sS", "-o", "/dev/null", "-w", "%{http_code} %{time_total}", url],
            capture_output=True,
            text=True,
        )
        code, timing = ("", "0")
        if cp.returncode == 0 and cp.stdout.strip():
            parts = cp.stdout.strip().split()
            if len(parts) >= 2:
                code, timing = parts[0], parts[1]
        samples.append({"http_code": code, "time_total": float(timing or 0)})
    return samples

def sample_stats(samples):
    times = [s["time_total"] for s in samples if s["time_total"] >= 0]
    if not times:
        return {"samples": samples, "min": None, "median": None, "p95": None, "max": None}
    ordered = sorted(times)
    p95_idx = min(len(ordered) - 1, max(0, int(round(len(ordered) * 0.95)) - 1))
    return {
        "samples": samples,
        "min": min(times),
        "median": median(times),
        "p95": ordered[p95_idx],
        "max": max(times),
    }

def read_json_lines(path):
    if not path.exists():
        return []
    items = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except Exception:
            continue
    return items

def latest_json(path):
    items = read_json_lines(path)
    return items[-1] if items else {}

def viewport_summary(label, path):
    if not path.exists():
        return {"stage": label, "result": "MISSING_ARTIFACT", "status": "MISSING_ARTIFACT"}
    data = latest_json(path)
    if not data:
        return {"stage": label, "result": "NOT_RUN", "status": "NOT_RUN"}
    data.setdefault("stage", label)
    data.setdefault("result", "NOT_RUN")
    data.setdefault("status", data["result"])
    return data

def viewport_result_map(path):
    results = {}
    for item in read_json_lines(path):
        stage = item.get("stage")
        if stage in {"browser_desktop", "browser_tablet", "browser_mobile", "browser_small_mobile"}:
            results[stage] = item
    return results

browser_desktop = viewport_summary("browser_desktop", root / "browser_desktop.stdout.log")
browser_tablet = viewport_summary("browser_tablet", root / "browser_tablet.stdout.log")
browser_mobile = viewport_summary("browser_mobile", root / "browser_mobile.stdout.log")
browser_small_mobile = viewport_summary("browser_small_mobile", root / "browser_small_mobile.stdout.log")
browser_viewports = {}
browser_viewports.update(viewport_result_map(root / "browser_desktop.stdout.log"))
browser_viewports.update(viewport_result_map(root / "browser_tablet.stdout.log"))
browser_viewports.update(viewport_result_map(root / "browser_mobile.stdout.log"))
browser_viewports.update(viewport_result_map(root / "browser_small_mobile.stdout.log"))
local_health = curl_sample("http://127.0.0.1:8080/healthz", 5)
local_home = curl_sample("http://127.0.0.1:8080/", 5)
local_feed = curl_sample("http://127.0.0.1:8080/api/homepage/feed", 5)
public_health = curl_sample("https://namvibe.com/healthz", 5)
public_home = curl_sample("https://namvibe.com/", 5)

try:
    gunicorn_pids = subprocess.check_output(["pgrep", "-af", "gunicorn.*app:app"], text=True).splitlines()
except Exception:
    gunicorn_pids = []
try:
    cloudflared_pids = subprocess.check_output(["pgrep", "-af", "cloudflared.*namvibe"], text=True).splitlines()
except Exception:
    cloudflared_pids = []

summary = {
    "run_dir": str(root),
    "verified_commit": subprocess.check_output(["git", "-C", str(runtime_root), "rev-parse", "HEAD"], text=True).strip(),
    "local_health": sample_stats(local_health),
    "local_home": sample_stats(local_home),
    "local_feed": sample_stats(local_feed),
    "public_health": sample_stats(public_health),
    "public_home": sample_stats(public_home),
    "gunicorn_pids": gunicorn_pids,
    "cloudflared_pids": cloudflared_pids,
    "browser_desktop": browser_desktop,
    "browser_tablet": browser_tablet,
    "browser_mobile": browser_mobile,
    "browser_small_mobile": browser_small_mobile,
    "browser_viewports": browser_viewports,
}

(root / "homepage_verification_results.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
lines = [
    f"verified_commit={summary['verified_commit']}",
    f"gunicorn_pids={' | '.join(gunicorn_pids) if gunicorn_pids else 'none'}",
    f"cloudflared_pids={' | '.join(cloudflared_pids) if cloudflared_pids else 'none'}",
]
for label, key in (("local_health", "local_health"), ("local_home", "local_home"), ("local_feed", "local_feed"), ("public_health", "public_health"), ("public_home", "public_home")):
    stat = summary[key]
    lines.append(f"{label}_median={stat['median']}")
    lines.append(f"{label}_p95={stat['p95']}")
    lines.append(f"{label}_worst={stat['max']}")
for label, data in (("browser_desktop", browser_desktop), ("browser_tablet", browser_tablet), ("browser_mobile", browser_mobile), ("browser_small_mobile", browser_small_mobile)):
    if data:
        lines.append(f"{label}_result={data.get('result', 'NOT_RUN')}")
        lines.append(f"{label}_screenshot={data.get('screenshot_path', '')}")
        lines.append(f"{label}_console_errors={data.get('console_error_count', 0)}")
        lines.append(f"{label}_page_errors={data.get('page_error_count', 0)}")
        lines.append(f"{label}_failed_requests={data.get('failed_first_party_request_count', 0)}")
        lines.append(f"{label}_overflow={data.get('horizontal_overflow', 0)}")
        lines.append(f"{label}_duplicate_cards={data.get('duplicate_feed_card_count', 0)}")
        lines.append(f"{label}_playing_videos={data.get('playing_video_count', 0)}")
(root / "homepage_verification_summary.txt").write_text("\n".join(lines) + "\n")
print(json.dumps({"summary_file": str(root / "homepage_verification_summary.txt"), "results_file": str(root / "homepage_verification_results.json")}))
PY

  {
    echo "run_dir=$RUN_DIR"
    echo "repo_root=$REPO"
    echo "python=$PYTHON_BIN"
    echo "tracked_secret_scan=$(cat "$RUN_DIR/tracked_secret_scan.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "dependency_check=$(cat "$RUN_DIR/dependency_check.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "compile_check=$(cat "$RUN_DIR/compile_check.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "database_path_selection=$(cat "$RUN_DIR/database_path_selection.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "neon_dns=$(cat "$RUN_DIR/neon_dns.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "neon_tcp=$(cat "$RUN_DIR/neon_tcp.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "neon_connection=$(cat "$RUN_DIR/neon_connection.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "call_security_integration=$(cat "$RUN_DIR/call_security_integration.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "gunicorn_restart=$(cat "$RUN_DIR/gunicorn_restart.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "gunicorn_listener=$(cat "$RUN_DIR/gunicorn_listener.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "gunicorn_sequential_health=$(cat "$RUN_DIR/gunicorn_sequential_health.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "gunicorn_sequential_homepage=$(cat "$RUN_DIR/gunicorn_sequential_homepage.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "gunicorn_concurrent_health=$(cat "$RUN_DIR/gunicorn_concurrent_health.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "local_routes=$(cat "$RUN_DIR/local_routes.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "cloudflare_process=$(cat "$RUN_DIR/cloudflare_process.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "cloudflare_connection=$(cat "$RUN_DIR/cloudflare_connection.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "public_tls=$(cat "$RUN_DIR/public_tls.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "public_dns=$(cat "$RUN_DIR/public_dns.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "public_routes=$(cat "$RUN_DIR/public_routes.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "socketio_handshake=$(cat "$RUN_DIR/socketio_handshake.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "browser_desktop=$(cat "$RUN_DIR/browser_desktop.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "browser_tablet=$(cat "$RUN_DIR/browser_tablet.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "browser_mobile=$(cat "$RUN_DIR/browser_mobile.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "browser_small_mobile=$(cat "$RUN_DIR/browser_small_mobile.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "runtime_log_scan=$(cat "$RUN_DIR/runtime_log_scan.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "log_secret_scan=$(cat "$RUN_DIR/log_secret_scan.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
    echo "homepage_report=$(cat "$RUN_DIR/homepage_report.status" 2>/dev/null || echo SKIPPED_DUE_TO_PREVIOUS_FAILURE)"
  } >"$RUN_DIR/final_summary.txt"

  local failure=0
  for stage in tracked_secret_scan dependency_check compile_check database_path_selection neon_dns neon_connection call_security_integration gunicorn_restart gunicorn_listener gunicorn_sequential_health gunicorn_sequential_homepage gunicorn_concurrent_health local_routes cloudflare_process cloudflare_connection public_dns public_tls public_routes socketio_handshake browser_desktop browser_tablet browser_mobile browser_small_mobile runtime_log_scan log_secret_scan homepage_report; do
    if [[ -f "$RUN_DIR/${stage}.status" ]]; then
      if [[ "$(cat "$RUN_DIR/${stage}.status")" != "PASS" ]]; then
        failure=1
      fi
    else
      failure=1
    fi
  done
  exit "$failure"
}

main "$@"
