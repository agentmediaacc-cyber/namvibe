import unittest

from flask import Flask

from services.request_cache import request_cached


class TestRequestDedupe(unittest.TestCase):
    def test_request_cached_runs_once_per_request(self):
        app = Flask(__name__)
        calls = {"count": 0}

        def fn():
            calls["count"] += 1
            return "ok"

        with app.test_request_context("/"):
            self.assertEqual(request_cached("k1", fn), "ok")
            self.assertEqual(request_cached("k1", fn), "ok")
        self.assertEqual(calls["count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
