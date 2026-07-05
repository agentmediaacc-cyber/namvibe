#!/bin/bash

set -u

DOMAIN="${DOMAIN:-namvibe.com}"
PORT="${PORT:-8080}"
LOCAL_BASE="http://127.0.0.1:${PORT}"
DOMAIN_BASE="https://${DOMAIN}"
FAILURES=0

URLS=(
  "${LOCAL_BASE}/healthz"
  "${LOCAL_BASE}/"
  "${DOMAIN_BASE}/healthz"
  "${DOMAIN_BASE}/"
)

for url in "${URLS[@]}"; do
  echo "[test] $url"
  body_file="/tmp/namvibe_test_body.$$"
  err_file="/tmp/namvibe_test_err.$$"
  http_code="$(curl --silent --show-error --output "$body_file" --write-out "%{http_code}" --max-time 20 "$url" 2>"$err_file" || true)"
  curl_error=""
  if [ -s "$err_file" ]; then
    curl_error="$(tr '\n' ' ' < "$err_file" | sed 's/[[:space:]]\+/ /g')"
  fi

  if [ "$http_code" = "200" ]; then
    echo "PASS $url -> HTTP $http_code"
  else
    echo "FAIL $url -> HTTP ${http_code:-000}"
    if [ -n "$curl_error" ]; then
      echo "curl_error: $curl_error"
    fi
    FAILURES=$((FAILURES + 1))
  fi

  rm -f "$body_file" "$err_file"
done

if [ "$FAILURES" -gt 0 ]; then
  echo "[result] FAIL ($FAILURES endpoint(s) failed)"
  exit 1
fi

echo "[result] PASS"
