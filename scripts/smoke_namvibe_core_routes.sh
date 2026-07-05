#!/bin/bash

set -u

PORT="${PORT:-8080}"
BASE_URL="${BASE_URL:-http://127.0.0.1:${PORT}}"
FAILURES=0

ROUTES=(
  "/"
  "/healthz"
  "/auth/login"
  "/discover"
  "/profile/"
  "/messages"
  "/notifications"
  "/reels"
  "/stories"
  "/search"
)

is_acceptable_status() {
  case "$1" in
    200|302|401) return 0 ;;
    *) return 1 ;;
  esac
}

for route in "${ROUTES[@]}"; do
  url="${BASE_URL}${route}"
  echo "[smoke] $url"
  body_file="/tmp/namvibe_smoke_body.$$"
  err_file="/tmp/namvibe_smoke_err.$$"
  http_code="$(curl --location --silent --show-error --output "$body_file" --write-out "%{http_code}" --max-time 20 "$url" 2>"$err_file" || true)"
  curl_error=""
  if [ -s "$err_file" ]; then
    curl_error="$(tr '\n' ' ' < "$err_file" | sed 's/[[:space:]]\+/ /g')"
  fi

  if is_acceptable_status "$http_code"; then
    echo "PASS $route -> HTTP $http_code"
  else
    echo "FAIL $route -> HTTP ${http_code:-000}"
    if [ -n "$curl_error" ]; then
      echo "curl_error: $curl_error"
    fi
    FAILURES=$((FAILURES + 1))
  fi

  rm -f "$body_file" "$err_file"
done

if [ "$FAILURES" -gt 0 ]; then
  echo "[result] FAIL ($FAILURES route(s) failed)"
  exit 1
fi

echo "[result] PASS"
