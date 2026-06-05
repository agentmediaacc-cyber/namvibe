import multiprocessing
import os

# Gunicorn configuration for CHAIN Production

bind = "127.0.0.1:5055"
workers = multiprocessing.cpu_count() * 2 + 1
timeout = 60
keepalive = 5

# Logging
accesslog = "-" # Stdout
errorlog = "-"  # Stderr
loglevel = "info"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Performance
worker_connections = 1000

# Overrides for Realtime mode (can be passed via CLI)
# -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker
# -w 1
