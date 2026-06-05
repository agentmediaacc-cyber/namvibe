import unittest

from services.circuit_breaker import CircuitBreaker
from services.request_cache import build_request_key, request_memoize


class TestRequestDedupCircuitBreakers(unittest.TestCase):
    def test_request_memoize_outside_request_context(self):
        calls = {"count": 0}
        key = build_request_key("svc", "arg")
        def fn():
            calls["count"] += 1
            return "ok"
        self.assertEqual(request_memoize(key, fn), "ok")
        self.assertEqual(request_memoize(key, fn), "ok")
        self.assertEqual(calls["count"], 2)

    def test_circuit_breaker_transitions(self):
        breaker = CircuitBreaker("test", failure_threshold=2, recovery_seconds=0)
        self.assertTrue(breaker.allow())
        breaker.failure("one")
        breaker.failure("two")
        breaker.opened_at = 0
        self.assertTrue(breaker.allow())
        self.assertEqual(breaker.get_state(), "half_open")
        breaker.success()
        self.assertEqual(breaker.get_state(), "closed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
