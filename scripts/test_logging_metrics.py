import unittest

from app import create_app
from services.logging_service import mask_secrets
from services.metrics_service import get_metrics_summary, observe_route


class TestLoggingMetrics(unittest.TestCase):
    def test_mask_secrets(self):
        payload = mask_secrets({"database_url": "postgres://user:pass@host/db", "ok": "x"})
        self.assertIn(payload["database_url"], {"[masked]", "[masked-url]"})

    def test_request_id_header_and_metrics_route_protection(self):
        app = create_app()
        with app.test_client() as client:
            response = client.get("/healthz")
            protected = client.get("/admin/metrics")
        self.assertTrue(response.headers.get("X-Request-Id") is not None)
        self.assertIn(protected.status_code, {302, 403})

    def test_metrics_summary(self):
        observe_route("/healthz", 12, 200)
        summary = get_metrics_summary()
        self.assertIn("/healthz", summary["routes"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
