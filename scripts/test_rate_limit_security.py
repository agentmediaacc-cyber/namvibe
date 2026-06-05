import os
import unittest

from flask import Flask, jsonify

from services.rate_limit_service import init_rate_limiter, limiter


class TestRateLimits(unittest.TestCase):
    def test_rate_limit_disabled_in_tests(self):
        os.environ["CHAIN_DISABLE_RATE_LIMITS"] = "1"
        app = Flask(__name__)
        app.secret_key = "test"
        app.limiter = init_rate_limiter(app)
        self.assertFalse(app.limiter.enabled)

    def test_api_rate_limit_json_error_exists(self):
        os.environ["CHAIN_DISABLE_RATE_LIMITS"] = "0"
        app = Flask(__name__)
        app.secret_key = "test"
        app.limiter = init_rate_limiter(app)

        @app.route("/api/test-limit")
        @limiter.limit("1/minute")
        def test_limit():
            return jsonify({"ok": True})

        with app.test_client() as client:
            first = client.get("/api/test-limit")
            second = client.get("/api/test-limit")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.get_json()["error"], "rate_limited")


if __name__ == "__main__":
    unittest.main(verbosity=2)
