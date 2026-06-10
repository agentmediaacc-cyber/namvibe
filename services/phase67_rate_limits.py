"""Phase 67 — API Rate Limiting configuration.

Extends Flask-Limiter with per-user limits for high-traffic features.
Safe fallback to in-memory when Redis unavailable.
"""

import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

try:
    from services.rate_limit_service import user_or_ip_key
except ImportError:
    def user_or_ip_key():
        return get_remote_address()

try:
    REDIS_URL = os.getenv('REDIS_URL') or os.getenv('CHAIN_REDIS_URL') or ''
except Exception:
    REDIS_URL = ''

RATE_LIMITS = {
    'auth_login':        '10/minute',
    'auth_register':     '5/minute',
    'auth_reset':        '3/hour',
    'messages_send':     '60/minute',
    'messages_create':   '30/minute',
    'wallet_transfer':   '30/minute',
    'wallet_deposit':    '10/minute',
    'wallet_payout':     '5/hour',
    'marketplace_create':'20/hour',
    'marketplace_purchase':'30/hour',
    'dating_like':       '60/minute',
    'dating_message':    '30/minute',
    'dating_report':     '10/hour',
    'ai_chat':           '30/minute',
    'ai_creator':        '20/minute',
    'ai_marketplace':    '20/minute',
    'ai_dating':         '20/minute',
    'ai_moderation':     '30/minute',
    'ai_messages':       '20/minute',
    'ai_captions':       '20/minute',
    'ai_search':         '30/minute',
}

def init_production_rate_limits(app):
    """Initialize production rate limiter with per-user limits."""
    storage_uri = REDIS_URL if REDIS_URL else 'memory://'
    limiter = Limiter(
        key_func=user_or_ip_key,
        storage_uri=storage_uri,
        app=app,
        default_limits=['200 per day', '50 per hour'],
        enabled=app.config.get('RATELIMIT_ENABLED', True),
    )
    return limiter

def get_rate_limit_config():
    """Return rate limit configuration for monitoring/audit."""
    return {
        'storage': 'redis' if REDIS_URL else 'memory',
        'limits': RATE_LIMITS,
    }
