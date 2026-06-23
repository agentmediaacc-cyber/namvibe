import multiprocessing
import os

# Gunicorn configuration for CHAIN Production - Tunnel Testing Mode
# Updated for Phase 136: Origin Server Stability

port = os.environ.get("PORT", "8080")
bind = "127.0.0.1:8080"  # Bind to localhost for Cloudflare Tunnel
timeout = 120
keepalive = 5

worker_class = "gevent"

# Logging
accesslog = "logs/gunicorn_access.log"
errorlog = "logs/gunicorn_error.log"
loglevel = "info"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Performance - Single worker for WebSocket compatibility
workers = 1
preload_app = False
max_requests = 500
max_requests_jitter = 50

# Worker connections for gevent
worker_connections = 1000