#!/bin/bash
# Phase 136: NamVibe Origin Server Start Script
# Safely starts the Gunicorn application for Cloudflare Tunnel

set -e

APP_DIR="$HOME/Desktop/chain_app"
LOG_DIR="$APP_DIR/logs"
PID_FILE="$LOG_DIR/gunicorn.pid"

echo "========================================"
echo "NamVibe Origin Server Startup"
echo "========================================"
echo ""

# Change to app directory
cd "$APP_DIR"
echo "[1/8] Working directory: $(pwd)"

# Activate virtual environment if exists
if [ -f "venv/bin/activate" ]; then
    echo "[2/8] Activating virtual environment..."
    source venv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
    echo "[2/8] Activating virtual environment..."
    source .venv/bin/activate
else
    echo "[2/8] No virtual environment found, using system Python"
fi

# Kill old gunicorn/python processes safely
echo "[3/8] Cleaning up old processes..."
pkill -f "gunicorn.*app:app" 2>/dev/null || true
pkill -f "gunicorn.*app:create_app" 2>/dev/null || true
pkill -f "python.*app.py" 2>/dev/null || true
rm -f "$PID_FILE"
sleep 1

# Ensure log directory exists
mkdir -p "$LOG_DIR"
: > "$LOG_DIR/gunicorn_access.log"
: > "$LOG_DIR/gunicorn_error.log"
echo "[4/8] Log directory ready: $LOG_DIR"

# Verify Redis is running or reachable
echo "[5/8] Checking Redis connectivity..."
if command -v redis-cli &> /dev/null; then
    if redis-cli ping 2>/dev/null | grep -q "PONG"; then
        echo "       Redis: OK (local)"
    else
        echo "       Redis: Checking URL from environment..."
        REDIS_URL=$(grep REDIS_URL .env 2>/dev/null | head -1 || echo "")
        if [ -n "$REDIS_URL" ]; then
            echo "       Redis: Using external URL (will verify at runtime)"
        else
            echo "       Redis: WARNING - No Redis URL configured"
        fi
    fi
else
    echo "       Redis CLI not available, will verify at runtime"
fi

 # Export production environment variables
 export PORT=8080
 export FLASK_ENV=production
 export WERKZEUG_RUN_MAIN=true
 export CHAIN_FORCE_FAST_HOME=1
 export CHAIN_TUNNEL_TESTING=1
 export CHAIN_DISABLE_PREWARM=1
 export CHAIN_DISABLE_DB_PING=1
 echo "[6/8] Environment configured:"
 echo "       PORT=$PORT"
 echo "       FLASK_ENV=$FLASK_ENV"
 echo "       CHAIN_FORCE_FAST_HOME=$CHAIN_FORCE_FAST_HOME"
 echo "       CHAIN_TUNNEL_TESTING=$CHAIN_TUNNEL_TESTING"
 echo "       CHAIN_DISABLE_PREWARM=$CHAIN_DISABLE_PREWARM"
 echo "       CHAIN_DISABLE_DB_PING=$CHAIN_DISABLE_DB_PING"

# Start Gunicorn
echo "[7/8] Starting Gunicorn..."
echo ""

# Use app:app (the module-level app instance) instead of app:create_app (factory function)
gunicorn \
    -c gunicorn.conf.py \
    app:app \
    --bind 127.0.0.1:8080 \
    --workers 1 \
    --worker-class gevent \
    --timeout 120 \
    --daemon \
    --pid "$PID_FILE" \
    --access-logfile "$LOG_DIR/gunicorn_access.log" \
    --error-logfile "$LOG_DIR/gunicorn_error.log" \
    --log-level info

sleep 1
GUNICORN_PID=$(cat "$PID_FILE" 2>/dev/null || true)
if [ -z "$GUNICORN_PID" ]; then
    echo "       Gunicorn PID file not created"
    exit 1
fi
echo "       Gunicorn PID: $GUNICORN_PID"

# Wait for server to start
echo ""
echo "[8/8] Waiting for server to be ready..."
sleep 2

# Verify healthz endpoint
MAX_RETRIES=10
RETRY_COUNT=0
HEALTHZ_OK=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if ! kill -0 "$GUNICORN_PID" 2>/dev/null; then
        echo "       Gunicorn master exited unexpectedly"
        break
    fi

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/healthz 2>/dev/null || true)
    
    if [ "$HTTP_CODE" = "200" ]; then
        HEALTHZ_OK=true
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "       Attempt $RETRY_COUNT/$MAX_RETRIES: HTTP $HTTP_CODE"
    sleep 2
done

echo ""
echo "========================================"
if [ "$HEALTHZ_OK" = true ]; then
    echo "SUCCESS: Origin server is running!"
    echo "  - Healthz: http://127.0.0.1:8080/healthz"
    echo "  - Access log: $LOG_DIR/gunicorn_access.log"
    echo "  - Error log: $LOG_DIR/gunicorn_error.log"
    echo ""
    echo "Next: Run 'cloudflared tunnel --protocol http2 run namvibe'"
    exit 0
else
    echo "FAILURE: Origin server failed to start"
    echo "  - Check error log: $LOG_DIR/gunicorn_error.log"
    tail -n 40 "$LOG_DIR/gunicorn_error.log" 2>/dev/null || true
    exit 1
fi
