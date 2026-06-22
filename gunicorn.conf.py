import multiprocessing
import os

# Gunicorn configuration for CHAIN Production

port = os.environ.get("PORT", "8080")
bind = f"0.0.0.0:{port}"
timeout = 60
keepalive = 5

worker_class = "geventwebsocket.gunicorn.workers.GeventWebSocketWorker"

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Performance
worker_connections = 1000
workers = 1  # Single worker required for WebSocket to work correctly
