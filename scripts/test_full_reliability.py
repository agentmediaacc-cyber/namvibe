import unittest

from app import create_app


class TestFullReliability(unittest.TestCase):
    def test_no_public_admin_link_and_health_safe(self):
        app = create_app()
        with app.test_client() as client:
            home = client.get("/")
            health = client.get("/healthz")
        self.assertEqual(health.status_code, 200)
        self.assertNotIn("/admin/metrics", home.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
