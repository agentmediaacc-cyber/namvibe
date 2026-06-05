import time
from collections import defaultdict, deque


_ROUTE_METRICS = defaultdict(lambda: deque(maxlen=200))
_ERROR_COUNTS = defaultdict(int)
_COUNTERS = defaultdict(int)


def observe_route(route, duration_ms, status_code):
    _ROUTE_METRICS[route].append(float(duration_ms))
    if int(status_code) >= 400:
        _ERROR_COUNTS[route] += 1


def increment(name, value=1):
    _COUNTERS[name] += int(value)


def set_gauge(name, value):
    _COUNTERS[name] = value


def _approx_percentile(values, percentile):
    if not values:
        return 0.0
    rows = sorted(values)
    index = min(len(rows) - 1, int((percentile / 100.0) * (len(rows) - 1)))
    return round(rows[index], 1)


def get_metrics_summary(extra=None):
    route_summary = {}
    for route, samples in _ROUTE_METRICS.items():
        values = list(samples)
        route_summary[route] = {
            "count": len(values),
            "p50_ms": _approx_percentile(values, 50),
            "p95_ms": _approx_percentile(values, 95),
            "errors": _ERROR_COUNTS.get(route, 0),
        }
    payload = {
        "routes": route_summary,
        "counters": dict(_COUNTERS),
        "generated_at": round(time.time(), 3),
    }
    if extra:
        payload.update(extra)
    return payload
