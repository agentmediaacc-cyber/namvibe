import os
import json
import logging
import time
from datetime import datetime

logger = logging.getLogger("chain_observability")
logger.setLevel(logging.INFO)

def init_observability(app):
    """Initializes Sentry and structured logging."""
    dsn = os.getenv("SENTRY_DSN")
    if dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration
            sentry_sdk.init(dsn=dsn, integrations=[FlaskIntegration()])
            print("[obs] Sentry initialized")
        except ImportError:
            pass

def log_event(event_type, payload):
    """Logs a structured event."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "payload": payload
    }
    logger.info(json.dumps(data))
    # In production, this could go to Redis or a log aggregator

def log_error(error, context=None):
    """Logs an error with context."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "error": str(error),
        "context": context
    }
    logger.error(json.dumps(data))
    
    # Send to Sentry if available
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(error)
    except:
        pass

def track_timing(name, ms, tags=None):
    """Tracks timing data for performance monitoring."""
    log_event("timing", {"name": name, "ms": ms, "tags": tags})
