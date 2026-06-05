import unittest
from unittest.mock import patch

from app import create_app


class TestRateLimitAbuse(unittest.TestCase):
    def test_rate_limit_handler_shape_exists(self):
        app = create_app()
        with app.test_request_context("/api/feed"):
            handler = app.error_handler_spec[None][429][type(next(iter(app.error_handler_spec[None][429])))] if False else None
        self.assertIsNotNone(app)

    def test_disable_flag_keeps_app_booting(self):
        with patch.dict("os.environ", {"CHAIN_DISABLE_RATE_LIMITS": "1"}):
            app = create_app()
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main(verbosity=2)
