#!/usr/bin/env bash
# run_local_tunnel_server.sh
# Start Gunicorn with 1 gevent worker on port 8080 for local Cloudflare Tunnel testing.
# Avoids prewarm storm and multiple Neon pools.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Load .env
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Explicit overrides for local tunnel mode
export WEB_CONCURRENCY=1
export CHAIN_AUTH_EMAIL_OPTIONAL=1
export DB_POOL_MIN=1
export DB_POOL_MAX=5
export FLASK_ENV=production
export ENV=production
export CHAIN_FAST_LOCAL=1
export CHAIN_DISABLE_PREWARM=1
export CHAIN_DISABLE_DB_PING=1
export CHAIN_SOCKETIO_REDIS_MANAGER=0
export PORT="${PORT:-8080}"

echo "Starting Gunicorn (1 gevent-websocket worker) on 0.0.0.0:${PORT}..."
echo "  WEB_CONCURRENCY=${WEB_CONCURRENCY}"
echo "  CHAIN_AUTH_EMAIL_OPTIONAL=${CHAIN_AUTH_EMAIL_OPTIONAL}"
echo "  DB_POOL_MIN=${DB_POOL_MIN} DB_POOL_MAX=${DB_POOL_MAX}"
echo "  CHAIN_SOCKETIO_REDIS_MANAGER=0 (local in-process Socket.IO)"
echo "  Disable prewarm + DB ping for local tunnel"

exec gunicorn \
    --bind "0.0.0.0:${PORT}" \
    --workers 1 \
    --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
    --timeout 120 \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --limit-request-line 4094 \
    --limit-request-fields 100 \
    "app:app"
