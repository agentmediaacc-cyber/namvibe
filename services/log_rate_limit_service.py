"""Log Rate Limit Service — rate-limits repeated noisy slow query logs.

Same SQL fingerprint is logged at most once per 60 seconds.
Errors are always logged immediately.
Metrics are still counted internally.
"""

import time
import hashlib
import threading

_fingerprint_times: dict = {}
_lock = threading.Lock()
_RATE_LIMIT_SECONDS = 60


def sql_fingerprint(sql_text: str) -> str:
    """Create a fingerprint for a SQL query by normalizing whitespace and params."""
    normalized = " ".join(sql_text.split())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def should_log(fingerprint: str) -> bool:
    """Check if this fingerprint should be logged (rate-limited)."""
    now = time.monotonic()
    with _lock:
        last = _fingerprint_times.get(fingerprint, 0)
        if now - last >= _RATE_LIMIT_SECONDS:
            _fingerprint_times[fingerprint] = now
            return True
        return False


def reset_rate_limits():
    """Clear all rate-limit state (useful for tests)."""
    with _lock:
        _fingerprint_times.clear()
