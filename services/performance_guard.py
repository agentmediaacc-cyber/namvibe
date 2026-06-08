import time
import os

_SLOW_LOG_ENABLED = os.getenv("PERFORMANCE_LOG", "0") == "1"
_DEFAULT_THRESHOLD_MS = 300

def timed_section(label):
    return _TimedSection(label)


class _TimedSection:
    def __init__(self, label):
        self.label = label
        self.start = None

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        elapsed_ms = (time.time() - self.start) * 1000
        log_if_slow(self.label, elapsed_ms)

    def elapsed_ms(self):
        if self.start is None:
            return 0
        return (time.time() - self.start) * 1000


def log_if_slow(label, ms, threshold_ms=None):
    if threshold_ms is None:
        threshold_ms = _DEFAULT_THRESHOLD_MS
    if ms >= threshold_ms or _SLOW_LOG_ENABLED:
        print(f"[perf] {label}: {ms:.1f}ms{' SLOW' if ms >= threshold_ms else ''}")
