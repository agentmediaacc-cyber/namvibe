import time


class CircuitBreaker:
    def __init__(self, name, failure_threshold=3, recovery_seconds=30):
        self.name = name
        self.failure_threshold = max(int(failure_threshold), 1)
        self.recovery_seconds = max(int(recovery_seconds), 1)
        self.failures = 0
        self.opened_at = 0.0
        self.last_reason = None
        self.state = "closed"
        self._last_logged_state = None

    def _transition(self, state):
        self.state = state
        if self._last_logged_state != state:
            self._last_logged_state = state
            print(f"[circuit_breaker] {self.name} -> {state}")

    def allow(self):
        if self.state == "open":
            if time.monotonic() - self.opened_at >= self.recovery_seconds:
                self._transition("half_open")
                return True
            return False
        return True

    def success(self):
        self.failures = 0
        self.opened_at = 0.0
        self.last_reason = None
        self._transition("closed")

    def failure(self, reason=None):
        self.failures += 1
        self.last_reason = str(reason or "")[:240] or None
        if self.failures >= self.failure_threshold:
            self.opened_at = time.monotonic()
            self._transition("open")
        elif self.state == "half_open":
            self.opened_at = time.monotonic()
            self._transition("open")
        else:
            self._transition("closed")

    def get_state(self):
        if self.state == "open" and (time.monotonic() - self.opened_at) >= self.recovery_seconds:
            return "half_open"
        return self.state
