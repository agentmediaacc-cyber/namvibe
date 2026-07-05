#!/bin/bash

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/Desktop/chain_app}"
LOG_DIR="$APP_DIR/logs"
ACCESS_LOG="$LOG_DIR/gunicorn_access.log"
ERROR_LOG="$LOG_DIR/gunicorn_error.log"
PID_FILE="$LOG_DIR/gunicorn.pid"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8080}"
HEALTH_URL="http://127.0.0.1:${PORT}/healthz"
WORKER_CLASS="eventlet"
WORKERS="1"
MAX_WAIT_SECONDS=30
MAX_ATTEMPTS=15

print_failure_logs() {
  echo "[fail] Recent Gunicorn error log:"
  tail -n 80 "$ERROR_LOG" 2>/dev/null || true
}

cleanup_port() {
  echo "[start] Releasing port $PORT if occupied..."
  local pids=""
  pids="$(lsof -ti "tcp:${PORT}" || true)"
  if [ -z "$pids" ]; then
    return
  fi

  for pid in $pids; do
    kill "$pid" 2>/dev/null || true
  done
  sleep 2

  pids="$(lsof -ti "tcp:${PORT}" || true)"
  if [ -n "$pids" ]; then
    echo "[start] Escalating stale listeners on $PORT..."
    for pid in $pids; do
      kill -9 "$pid" 2>/dev/null || true
    done
    sleep 1
  fi

  pids="$(lsof -ti "tcp:${PORT}" || true)"
  if [ -n "$pids" ]; then
    echo "[fail] Could not free port $PORT"
    exit 1
  fi
}

cd "$APP_DIR"
mkdir -p "$LOG_DIR"

if [ -f "venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

cleanup_port

if [ -f "$PID_FILE" ]; then
  echo "[start] Removing stale PID file $PID_FILE"
  rm -f "$PID_FILE"
fi

: > "$ACCESS_LOG"
: > "$ERROR_LOG"

export PORT
export FLASK_ENV=production
export ENV=production
export CHAIN_GUNICORN_WORKER="$WORKER_CLASS"
export CHAIN_FAST_LOCAL=1
export CHAIN_DISABLE_PREWARM=1
export CHAIN_DISABLE_DB_PING=1
export CHAIN_DISABLE_SCHEMA_CHECK=1
export PYTHONUNBUFFERED=1

echo "[start] Environment:"
echo "  PORT=$PORT"
echo "  CHAIN_GUNICORN_WORKER=$CHAIN_GUNICORN_WORKER"
echo "  CHAIN_FAST_LOCAL=$CHAIN_FAST_LOCAL"
echo "  CHAIN_DISABLE_PREWARM=$CHAIN_DISABLE_PREWARM"
echo "  CHAIN_DISABLE_DB_PING=$CHAIN_DISABLE_DB_PING"
echo "  CHAIN_DISABLE_SCHEMA_CHECK=$CHAIN_DISABLE_SCHEMA_CHECK"

echo "[start] Launching Gunicorn on $HOST:$PORT..."
gunicorn app:app \
  --bind "$HOST:$PORT" \
  --workers "$WORKERS" \
  --worker-class "$WORKER_CLASS" \
  --timeout 120 \
  --keep-alive 5 \
  --daemon \
  --pid "$PID_FILE" \
  --access-logfile "$ACCESS_LOG" \
  --error-logfile "$ERROR_LOG" \
  --log-level info

sleep 2

if [ ! -f "$PID_FILE" ]; then
  echo "[fail] Gunicorn did not create $PID_FILE"
  print_failure_logs
  exit 1
fi

PID="$(cat "$PID_FILE")"
echo "[start] Gunicorn PID: $PID"

if ! kill -0 "$PID" 2>/dev/null; then
  echo "[fail] Gunicorn exited before readiness checks"
  print_failure_logs
  exit 1
fi

READY=0
for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "[fail] Gunicorn exited during readiness checks"
    print_failure_logs
    exit 1
  fi

  http_code="$(curl --silent --show-error --output /tmp/namvibe_healthz.$$ --write-out "%{http_code}" --max-time 5 "$HEALTH_URL" 2>/tmp/namvibe_healthz_err.$$ || true)"
  if [ "$http_code" = "200" ]; then
    READY=1
    rm -f /tmp/namvibe_healthz.$$ /tmp/namvibe_healthz_err.$$
    break
  fi

  echo "[start] Waiting for /healthz ($attempt/$MAX_ATTEMPTS) -> HTTP ${http_code:-000}"
  if [ -s /tmp/namvibe_healthz_err.$$ ]; then
    tr '\n' ' ' < /tmp/namvibe_healthz_err.$$ | sed 's/[[:space:]]\+/ /g'
    printf "\n"
  fi
  rm -f /tmp/namvibe_healthz.$$ /tmp/namvibe_healthz_err.$$
  sleep 2
done

if [ "$READY" != "1" ]; then
  echo "[fail] Local healthz did not return 200 within ${MAX_WAIT_SECONDS}s"
  print_failure_logs
  exit 1
fi

echo "[ok] NamVibe local origin is ready"
echo "  Local healthz: $HEALTH_URL"
echo "  Local home:    http://127.0.0.1:${PORT}/"
echo "  Access log:    $ACCESS_LOG"
echo "  Error log:     $ERROR_LOG"
